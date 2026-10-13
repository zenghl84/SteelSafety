"""Numerical/software checks. Synthetic cases are NOT MIDAS validation data."""
from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prepare_cases import scaled_copy, CASES, decode_mgt
from stress_io import read_stress
from rom import fit_pod, predict_field, train, load_model


class NumericalTests(unittest.TestCase):
    def test_linear_load_law_at_unseen_value(self):
        p = np.array([.8, 1., 1.2])
        base = np.array([12., -8., 3., 5.])
        slope = np.array([4., 7., -3., 11.])
        fields = base[:, None] + slope[:, None] * p
        model = fit_pod(p, fields)
        self.assertEqual(model['retained_rank'], 1)
        np.testing.assert_allclose(predict_field(model, 1.07), base + slope * 1.07, atol=1e-12)
        with self.assertRaises(ValueError):
            predict_field(model, 1.21)
        with self.assertRaises(ValueError):
            predict_field(model, np.nan)

    def test_no_false_parametric_model_from_identical_exports(self):
        with self.assertRaisesRegex(ValueError, '几乎完全相同'):
            fit_pod([.8, 1., 1.2], np.ones((6, 3)))

    def test_end_to_end_validation_is_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source').mkdir()
            (root / 'results').mkdir()
            (root / 'source/model.mgt').write_text('synthetic test model', encoding='utf-8')
            mapping = pd.DataFrame({'element': [1, 1, 2, 2], 'position': ['I', 'J', 'I', 'J'],
                                    'active_CS13': [True] * 4, 'active_CS18': [True] * 4,
                                    'e_mpa': [206000.] * 4})
            mapping.to_csv(root / 'source/end_mapping.csv', index=False)
            reference = mapping[['element', 'position']].copy()
            reference['axial_stress_mpa'] = [100., 110., 120., 130.]
            reference['stage'], reference['load'], reference['step'] = 'CS13', '合计(CS)', '001(last)'
            reference.to_csv(root / 'results/CS13_reference.csv', index=False)
            cases = []
            baseline, delta_base, slope = np.array([100., 110., 120., 130.]), np.array([10., -20., 5., -8.]), np.array([5., -2., 3., 4.])
            for name, value, split in CASES:
                data = mapping.copy()
                data['axial_stress_mpa'] = baseline + delta_base + slope * value
                data['stage'], data['load'], data['step'] = 'CS18', '合计(CS)', '001(last)'
                data.sample(frac=1, random_state=3).to_csv(root / f'results/{name}_CS18.csv', index=False)
                cases.append(dict(case_id=name, lambda_value=value, split=split,
                                  result_base=f'results/{name}_CS18',reference_base='results/CS13_reference'))
            pd.DataFrame(cases).to_csv(root / 'cases.csv', index=False)
            with contextlib.redirect_stdout(io.StringIO()):
                model = train(root)
            self.assertLess(model['metadata']['validation'][0]['max_abs_error_mpa'], 1e-12)
            restored = load_model(root / 'trained/stress_rom.npz')
            np.testing.assert_allclose(predict_field(restored, 1.05), delta_base + slope * 1.05)
            expected_strain = (delta_base[0] + slope[0] * 1.05) / 206000. * 1e6
            out = __import__('rom').prediction_table(restored, 1.05)
            self.assertAlmostEqual(out.iloc[0].predicted_axial_delta_strain_microstrain, expected_strain)
            original_basis = model['basis'].copy()
            # Change only a held-out value: fitting must stay exactly unchanged.
            changed = pd.read_csv(root / 'results/case_090_CS18.csv')
            changed['axial_stress_mpa'] += 7.
            changed.to_csv(root / 'results/case_090_CS18.csv', index=False)
            with contextlib.redirect_stdout(io.StringIO()):
                updated = train(root)
            np.testing.assert_array_equal(updated['basis'], original_basis)
            self.assertAlmostEqual(updated['metadata']['validation'][0]['rmse_mpa'], 7.)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.mapping = pd.DataFrame({'element': [1, 1, 2, 2], 'position': ['I', 'J', 'I', 'J']})
        self.frame = self.mapping.copy()
        self.frame['axial_stress_mpa'] = [0., -12., 8., 4.]
        self.frame['stage'], self.frame['load'], self.frame['step'] = 'CS18', '合计(CS)', '001(last)'

    def tearDown(self):
        self.temp.cleanup()

    def test_id_alignment_and_real_zero(self):
        path = self.root / 'stress.csv'
        self.frame.iloc[::-1].to_csv(path, index=False)
        result, _ = read_stress(path, self.mapping)
        np.testing.assert_array_equal(result.axial_stress_mpa, [0., -12., 8., 4.])

    def test_missing_end_is_rejected(self):
        path = self.root / 'stress.csv'
        self.frame.iloc[:-1].to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, '缺少 1'):
            read_stress(path, self.mapping)

    def test_cs13_can_zero_fill_only_elements_inactive_in_mgt(self):
        path = self.root / 'stress.csv'
        expected = self.mapping.copy()
        expected['active_CS13'] = [True, True, False, False]
        self.frame.iloc[:2].assign(stage='CS13').to_csv(path, index=False)
        got, audit = read_stress(path, expected, stage='CS13')
        np.testing.assert_array_equal(got.axial_stress_mpa, [0., -12., 0., 0.])
        self.assertEqual(audit['inactive_endpoints_zero_filled'], 2)

    def test_cs13_missing_active_element_is_not_zero_filled(self):
        path = self.root / 'stress.csv'
        expected = self.mapping.copy()
        expected['active_CS13'] = [True, True, False, False]
        self.frame.iloc[1:2].assign(stage='CS13').to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, 'CS13 有效梁端'):
            read_stress(path, expected, stage='CS13')

    def test_wrong_stage_is_rejected(self):
        path = self.root / 'stress.csv'
        self.frame.assign(stage='CS13').to_csv(path, index=False)
        with self.assertRaises(ValueError):
            read_stress(path, self.mapping)

    def test_axial_force_not_mistaken_for_stress(self):
        path = self.root / 'force.csv'
        self.frame.rename(columns={'axial_stress_mpa': 'Axial (N)'}).to_csv(path, index=False)
        with self.assertRaises(ValueError):
            read_stress(path, self.mapping)

    def test_conflicting_duplicate_is_rejected(self):
        path = self.root / 'stress.csv'
        wrong = self.frame.iloc[[0]].assign(axial_stress_mpa=99.)
        pd.concat([self.frame, wrong]).to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, '存在不同应力'):
            read_stress(path, self.mapping)

    def test_midas_headers_multiple_sheets_and_part_labels(self):
        header = ['单元', '荷载', '阶段', '步骤', '位置', '成分', '轴向(N/mm^2)']
        rows = [[2, '合计(CS)', 'CS18', '001(last)', 'PartI', 'Pos-1', 8.],
                [2, '合计(CS)', 'CS18', '001(last)', 'PartJ', 'Pos-1', 4.],
                [1, '合计(CS)', 'CS18', '001(last)', 'PartJ', 'Pos-1', -12.],
                [1, '合计(CS)', 'CS18', '001(last)', 'PartI', 'Pos-1', 0.]]
        raw = {'梁单元应力': pd.DataFrame([['MIDAS Export'], header] + rows[:2]),
               '梁单元应力_2': pd.DataFrame([header] + rows[2:])}
        # Test sheet joining/header logic separately from pandas' Excel engine.
        with patch('stress_io.pd.read_excel', return_value=raw):
            result, audit = read_stress(self.root / 'export.xlsx', self.mapping)
        np.testing.assert_array_equal(result.axial_stress_mpa, [0., -12., 8., 4.])
        self.assertEqual(len(audit['sheets']), 2)


class ActualMGTTests(unittest.TestCase):
    def test_only_expected_load_rows_are_modified(self):
        raw = (ROOT / 'source/model.mgt').read_bytes()
        generated, records = scaled_copy(raw, .8)
        original_text, _ = decode_mgt(raw)
        modified_text, _ = decode_mgt(generated)
        original, modified = original_text.splitlines(), modified_text.splitlines()
        self.assertEqual(len(original), len(modified))
        changed_lines = [i + 1 for i, (a, b) in enumerate(zip(original, modified)) if a != b]
        self.assertEqual(changed_lines, [r['line'] for r in records])
        self.assertEqual(len(changed_lines), 83)
        for number in changed_lines:
            a, b = original[number - 1].split(','), modified[number - 1].split(',')
            self.assertEqual(a[0], b[0])
            self.assertEqual(a[7:], b[7:])
            self.assertEqual(a[7].strip(), '施工荷载组18')
            np.testing.assert_allclose(list(map(float, b[1:7])), np.array(list(map(float, a[1:7]))) * .8)
        self.assertEqual(scaled_copy(raw, 1.)[0], raw)
        self.assertAlmostEqual(sum(r['after'][2] for r in records), -410732.208, places=6)

    def test_baseline_has_every_expected_beam_end(self):
        mapping = pd.read_csv(ROOT / 'source/end_mapping.csv')
        result, audit = read_stress(ROOT / 'results/case_100_CS18.xlsx', mapping, stage='CS18')
        self.assertEqual(len(result), 23838)
        self.assertEqual(result.element.nunique(), 11919)
        self.assertEqual(audit['missing_metadata_columns'], [])
        ref, _ = read_stress(ROOT / 'results/CS13_reference.xlsx', mapping, stage='CS13')
        self.assertEqual(len(ref), 23838)
        self.assertTrue(mapping.active_CS13.any())


if __name__ == '__main__':
    unittest.main()
