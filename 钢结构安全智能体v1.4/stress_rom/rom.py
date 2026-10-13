"""CS18 axial-stress POD + one-parameter interpolation surrogate.

No Galerkin stiffness projection is performed. No MIDAS solver is embedded.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import sys
import time
import numpy as np
import pandas as pd
if __package__:
    from .stress_io import find_result, read_stress
else:
    from stress_io import find_result, read_stress

ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cases(root):
    cases = pd.read_csv(Path(root) / 'cases.csv', encoding='utf-8-sig')
    required = {'case_id', 'lambda_value', 'split', 'result_base'}
    if not required.issubset(cases.columns):
        raise ValueError('cases.csv 缺少必要列。')
    if cases.case_id.duplicated().any() or cases.lambda_value.duplicated().any():
        raise ValueError('样本编号或荷载倍率重复。')
    if not set(cases.split).issubset({'train', 'test'}):
        raise ValueError('split 只能为 train 或 test。')
    if not np.isfinite(cases.lambda_value.to_numpy(dtype=float)).all():
        raise ValueError('荷载倍率必须是有限数值。')
    if (cases.split == 'train').sum() < 3 or (cases.split == 'test').sum() < 1:
        raise ValueError('至少需要 3 个训练工况及 1 个独立检验工况。')
    return cases


def status(root=ROOT):
    root = Path(root)
    rows = []
    for row in load_cases(root).itertuples(index=False):
        path = find_result(root, row.result_base)
        reference = find_result(root, row.reference_base)
        rows.append(dict(case_id=row.case_id, lambda_value=row.lambda_value,
                         split=row.split, CS18=path.name if path else '待 MIDAS 导出',
                         CS13_reference=reference.name if reference else '待导出一次'))
    return pd.DataFrame(rows)


def fit_pod(parameters, fields, energy=.999):
    parameters = np.asarray(parameters, dtype=float)
    fields = np.asarray(fields, dtype=float)
    if fields.ndim != 2 or len(parameters) != fields.shape[1]:
        raise ValueError('训练矩阵必须为 梁端数×工况数。')
    if not np.isfinite(fields).all() or not np.isfinite(parameters).all():
        raise ValueError('训练数据必须为有限数值。')
    if len(parameters) < 3 or len(np.unique(parameters)) != len(parameters):
        raise ValueError('需要至少三个互异的训练倍率。')
    if not 0 < energy <= 1:
        raise ValueError('能量比例必须位于 (0, 1]。')
    order = np.argsort(parameters)
    parameters, fields = parameters[order], fields[:, order]
    mean = fields.mean(axis=1)
    centered = fields - mean[:, None]
    if np.linalg.norm(centered) <= 1e-12 * max(np.linalg.norm(fields), 1.):
        raise ValueError('训练应力几乎完全相同，请检查荷载是否修改、是否重新分析或重复导出。')
    u, singular, _ = np.linalg.svd(centered, full_matrices=False)
    tolerance = max(centered.shape) * np.finfo(float).eps * singular[0]
    numerical_rank = int(np.sum(singular > tolerance))
    cumulative = np.cumsum(singular ** 2) / np.sum(singular ** 2)
    rank = min(int(np.searchsorted(cumulative, energy)) + 1, numerical_rank)
    basis = u[:, :rank]
    coefficients = (basis.T @ centered).T
    return dict(mean=mean, basis=basis, parameters=parameters,
                coefficients=coefficients, singular_values=singular,
                cumulative_energy=cumulative, retained_rank=rank,
                numerical_rank=numerical_rank, requested_energy=energy)


def predict_field(model, parameter):
    parameter = float(parameter)
    values = model['parameters']
    if not np.isfinite(parameter) or parameter < values[0] or parameter > values[-1]:
        raise ValueError(f'倍率只能在已训练区间 [{values[0]:g}, {values[-1]:g}] 内。')
    weights = np.array([np.interp(parameter, values, c)
                        for c in model['coefficients'].T])
    return model['mean'] + model['basis'] @ weights


def _relative(numerator, denominator):
    return float(numerator / denominator) if denominator > 1e-12 else None


def error_metrics(actual, predicted, mapping, baseline=None):
    error = predicted - actual
    absolute = np.abs(error)
    true_peak = int(np.argmax(np.abs(actual)))
    pred_peak = int(np.argmax(np.abs(predicted)))
    worst = int(np.argmax(absolute))
    def end(index):
        row = mapping.iloc[index]
        return f'{int(row.element)}_{row.position}'
    k = min(10, len(actual))
    true_top = set(np.argsort(np.abs(actual))[-k:])
    pred_top = set(np.argsort(np.abs(predicted))[-k:])
    result = dict(rmse_mpa=float(np.sqrt(np.mean(error ** 2))),
                  relative_l2=_relative(np.linalg.norm(error), np.linalg.norm(actual)),
                  max_abs_error_mpa=float(absolute[worst]), worst_error_end=end(worst),
                  actual_min_mpa=float(np.min(actual)), actual_max_mpa=float(np.max(actual)),
                  predicted_min_mpa=float(np.min(predicted)), predicted_max_mpa=float(np.max(predicted)),
                  actual_peak_end=end(true_peak), predicted_peak_end=end(pred_peak),
                  actual_abs_peak_mpa=float(abs(actual[true_peak])),
                  predicted_abs_peak_mpa=float(abs(predicted[pred_peak])),
                  top10_end_overlap=len(true_top & pred_top) / k)
    if baseline is not None:
        result['load_effect_relative_l2'] = _relative(
            np.linalg.norm(error), np.linalg.norm(actual - baseline))
    return result


def train(root=ROOT, energy=.999):
    root = Path(root)
    cases = load_cases(root)
    paths = {r.case_id: find_result(root, r.result_base)
             for r in cases.itertuples(index=False)}
    missing = [name for name, path in paths.items() if path is None]
    if missing:
        raise ValueError('缺少 MIDAS 应力结果：' + ', '.join(missing) +
                         '。请放入 results，再训练；当前没有生成训练模型。')
    mapping = pd.read_csv(root / 'source/end_mapping.csv')
    if mapping.duplicated(['element', 'position']).any():
        raise ValueError('梁端映射重复。')
    if not {'active_CS13', 'active_CS18', 'e_mpa'}.issubset(mapping.columns):
        raise ValueError('梁端映射缺少 CS13/CS18 激活状态或杆件弹性模量。请基于 source/model.mgt 重建映射。')
    sensor_path = root / 'source/sensor_mapping.csv'
    if sensor_path.exists():
        sensors = pd.read_csv(sensor_path, encoding='utf-8-sig')
        for sensor in sensors.itertuples(index=False):
            ends = mapping.loc[mapping.element == int(sensor.element)]
            if ends.empty or not ends.active_CS13.astype(bool).all():
                raise ValueError(f'{sensor.sensor_id} 对应杆件在 CS13 未激活，无法采用 CS13 作为该测点基线。')
    reference_path = find_result(root, 'results/CS13_reference')
    if reference_path is None:
        raise ValueError('缺少 CS13_reference：请先导出一次 CS13 / 合计(CS) / 最后一步的梁端轴向应力。')
    reference, reference_audit = read_stress(reference_path, expected=mapping, stage='CS13')
    reference_values = reference.axial_stress_mpa.to_numpy(dtype=float)
    arrays, audits = {}, []
    reference_audit.update(sha256=sha256(reference_path), role='所有倍率共用的 CS13 应力参考')
    audits.append(reference_audit)
    for case in cases.itertuples(index=False):
        frame, audit = read_stress(paths[case.case_id], expected=mapping, stage='CS18')
        arrays[case.case_id] = frame.axial_stress_mpa.to_numpy(dtype=float) - reference_values
        audit.update(case_id=case.case_id, sha256=sha256(paths[case.case_id]),
                     lambda_value=float(case.lambda_value), split=case.split)
        audits.append(audit)
    train_cases = cases.loc[cases.split == 'train'].sort_values('lambda_value')
    fields = np.column_stack([arrays[c] for c in train_cases.case_id])
    start = time.perf_counter()
    model = fit_pod(train_cases.lambda_value, fields, energy)
    train_seconds = time.perf_counter() - start
    base_cases = cases.loc[np.isclose(cases.lambda_value, 1.)]
    baseline = arrays[base_cases.iloc[0].case_id] if len(base_cases) else None
    validation = []
    for row in cases.loc[cases.split == 'test'].itertuples(index=False):
        predicted = predict_field(model, row.lambda_value)
        metrics = error_metrics(arrays[row.case_id], predicted, mapping, baseline)
        metrics.update(case_id=row.case_id, lambda_value=float(row.lambda_value))
        validation.append(metrics)
    projection = []
    for i, row in enumerate(train_cases.itertuples(index=False)):
        projected = model['mean'] + model['basis'] @ model['coefficients'][i]
        metrics = error_metrics(fields[:, i], projected, mapping)
        metrics['case_id'] = row.case_id
        projection.append(metrics)
    model['elements'] = mapping.element.to_numpy(dtype=np.int64)
    model['positions'] = mapping.position.to_numpy(dtype='U1')
    model['modulus_mpa'] = mapping.e_mpa.to_numpy(dtype=float)
    # Measure only surrogate evaluation; no invented MIDAS timing/speedup.
    timings = []
    for _ in range(10):
        start = time.perf_counter()
        predict_field(model, float(np.mean(model['parameters'])))
        timings.append(time.perf_counter() - start)
    metadata = dict(schema_version=2, method='应力增量 POD + 一维分段线性插值（非 Galerkin）',
                    reference_stage='CS13', stage='CS18', load='合计(CS)', step='001(last)', stress_unit='MPa',
                    output='同一工况下 CS18 − CS13 的梁端轴向应力增量 Δσ',
                    strain_conversion='轴向测点估算 Δε(με)=Δσ(MPa)/E(MPa)×10^6',
                    parameter='施工活荷载 / 施工荷载组18 / 节点荷载倍率',
                    applicable_interval=[float(model['parameters'][0]), float(model['parameters'][-1])],
                    retained_rank=model['retained_rank'], numerical_rank=model['numerical_rank'],
                    captured_training_variation_energy=float(model['cumulative_energy'][model['retained_rank'] - 1]),
                    train_cases=train_cases.case_id.tolist(), test_cases=cases.loc[cases.split == 'test', 'case_id'].tolist(),
                    rows=len(mapping), created_at=datetime.now(timezone.utc).isoformat(),
                    pod_fit_seconds=train_seconds, predict_median_seconds=float(np.median(timings)),
                    source_mgt_sha256=sha256(root / 'source/model.mgt'),
                    training_projection=projection, validation=validation, inputs=audits,
                    limitations=['固定 CS13 基线和 CS18 施工历史；不是跨施工阶段的通用模型。',
                                 '只预测 CS18−CS13 的轴向应力变化，且只覆盖已采样荷载倍率。',
                                 '独立检验只覆盖列出的工况，不能据此自动确认结构安全。',
                                 '34 个仅受拉单元保留在 MIDAS 分析内，其应力不属于本梁端输出。',
                                 'S7/S8 的映射标为弯曲测点，轴向应力除以 E 不能代表其弯曲表面应变。'])
    provenance = root / 'source/baseline_provenance.json'
    if provenance.exists():
        metadata['bundled_historical_baseline_provenance'] = json.loads(provenance.read_text(encoding='utf-8'))
    model['metadata'] = metadata
    output = root / 'trained'
    output.mkdir(exist_ok=True)
    target = output / 'stress_rom.npz'
    with (output / 'stress_rom.tmp').open('wb') as f:
        np.savez_compressed(f, mean=model['mean'], basis=model['basis'],
                            parameters=model['parameters'], coefficients=model['coefficients'],
                            elements=model['elements'], positions=model['positions'],
                            modulus_mpa=model['modulus_mpa'],
                            metadata=np.array(json.dumps(metadata, ensure_ascii=False)))
    os.replace(output / 'stress_rom.tmp', target)
    (output / 'validation_report.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    pd.DataFrame(validation).to_csv(output / 'validation_metrics.csv', index=False, encoding='utf-8-sig')
    energy_frame = pd.DataFrame({'mode': np.arange(1, len(model['singular_values']) + 1),
                                 'singular_value': model['singular_values'],
                                 'cumulative_squared_energy': model['cumulative_energy']})
    energy_frame.to_csv(output / 'pod_energy.csv', index=False, encoding='utf-8-sig')
    # Keep the user's baseline available for signed increments in downstream views.
    if baseline is not None:
        table = mapping[['element', 'position']].copy()
        table['delta_stress_mpa'] = baseline
        table.to_csv(output / 'baseline.csv', index=False, encoding='utf-8-sig')
    print(f'训练完成：{len(mapping)} 个梁端，保留 {model["retained_rank"]} 阶。')
    print(pd.DataFrame(validation)[['case_id', 'rmse_mpa', 'relative_l2', 'max_abs_error_mpa']].to_string(index=False))
    print('独立工况误差已输出；是否满足用途需依据上述误差判断。')
    return model


def load_model(path):
    with np.load(path, allow_pickle=False) as z:
        model = {key: z[key].copy() for key in ('mean', 'basis', 'parameters', 'coefficients', 'elements', 'positions', 'modulus_mpa')}
        model['metadata'] = json.loads(str(z['metadata'].item()))
    n, r = model['basis'].shape
    if model['mean'].shape != (n,) or model['coefficients'].shape != (len(model['parameters']), r):
        raise ValueError('模型数组尺寸不一致。')
    if any(len(model[k]) != n for k in ('elements', 'positions', 'modulus_mpa')):
        raise ValueError('模型梁端编号尺寸不一致。')
    for name in ('mean', 'basis', 'parameters', 'coefficients', 'modulus_mpa'):
        if not np.isfinite(model[name]).all():
            raise ValueError('模型含非有限数值。')
    if np.any(np.diff(model['parameters']) <= 0):
        raise ValueError('模型训练倍率顺序错误。')
    return model


def prediction_table(model, parameter):
    values = predict_field(model, parameter)
    return pd.DataFrame(dict(element=model['elements'], position=model['positions'],
                             delta_stress_mpa=values,
                             predicted_axial_delta_strain_microstrain=values / model['modulus_mpa'] * 1e6,
                             lambda_value=float(parameter), reference_stage='CS13', stage='CS18',
                             load='合计(CS)', step='001(last)'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'train', 'predict'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--energy', type=float, default=.999)
    parser.add_argument('--lambda-value', type=float, default=1.05)
    args = parser.parse_args()
    try:
        if args.command == 'status':
            print(status(args.root).to_string(index=False))
        elif args.command == 'train':
            train(args.root, args.energy)
        else:
            model = load_model(args.root / 'trained/stress_rom.npz')
            table = prediction_table(model, args.lambda_value)
            out = args.root / 'predictions'
            out.mkdir(exist_ok=True)
            path = out / f'delta_stress_{args.lambda_value:.4f}.csv'
            table.to_csv(path, index=False, encoding='utf-8-sig')
            print('预测已保存：', path)
    except (ValueError, FileNotFoundError, ImportError) as exc:
        print(f'\n尚未完成：{exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
