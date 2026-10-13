"""Validate physical section units, exclusions, and safely embedded model data."""
import copy
import json
import unittest

from steel_viewer import build_scene, pipe_sections, script_json, viewer_html


def mgt(unit="MM", diameter="80", wall="4", shape="P"):
    return (f"*UNIT\nN, {unit}, J, C\n*SECTION\n"
            f"1, DBUSER, arbitrary-label, CC, 0, 0, 0, 0, 0, 0, YES, NO, {shape}, 2, {diameter}, {wall}\n").encode()


class SteelViewerTests(unittest.TestCase):
    def test_reads_numeric_dimensions_and_converts_all_supported_units(self):
        for unit, scale in (("MM", .001), ("CM", .01), ("M", 1.)):
            with self.subTest(unit=unit):
                result = pipe_sections(mgt(unit))[1]
                self.assertAlmostEqual(result["diameter_m"], 80 * scale)
                self.assertAlmostEqual(result["wall_m"], 4 * scale)

    def test_invalid_or_unsupported_sections_have_no_invented_radius(self):
        for raw in (mgt(diameter="nan"), mgt(diameter="0"), mgt(wall="40"),
                    mgt(wall="-1"), mgt(shape="H")):
            with self.subTest(raw=raw):
                self.assertEqual(pipe_sections(raw), {})

    def test_exclusions_and_hidden_selection_never_modify_source_geometry(self):
        model = {"nodes": {1: (0., 0., 0.), 2: (1., 0., 0.)},
                 "materials": {1: "Q235B", 17: "MAT_WIRE16_FC"}, "sections": {1: "pipe"}}
        members = [{"id": eid, "n1": 1, "n2": 2, "material": mid, "section": 1, "type": "BEAM"}
                   for eid, mid in ((10, 1), (11, 17))]
        before = copy.deepcopy((model, members))
        scene = build_scene(mgt(), model, members, "钢材质感", [(1, 0, 0)], ["S1"], ["detail"],
                            11, True, "model-id", diameter_scale=3)
        self.assertEqual([e[0] for e in scene["members"]], [10])
        self.assertEqual(scene["selected"], 0)
        self.assertEqual(scene["nodes"], model["nodes"])
        self.assertEqual(scene["sections"][1]["diameter_m"], .08)
        self.assertEqual((model, members), before)
        without_sensors = build_scene(mgt(), model, members, "材料", [(1, 0, 0)], ["S1"], ["detail"],
                                     10, False, "model-id")
        self.assertEqual(without_sensors["sensors"], [])
        self.assertEqual(without_sensors["selected"], 10)

    def test_uploaded_text_cannot_close_script_or_replace_template_tokens(self):
        hostile = '</script><script>alert(1)</script> __VIEWER_RUNTIME__ __BUNDLED_MODULES__'
        payload = {"label": hostile}
        encoded = script_json(payload)
        self.assertNotIn("</script>", encoded)
        self.assertEqual(json.loads(encoded), payload)
        html = viewer_html(payload, "model_view")
        embedded = html.split('<script id="steel-scene-data" type="application/json">', 1)[1].split('</script>', 1)[0]
        self.assertEqual(json.loads(embedded), payload)


if __name__ == "__main__":
    unittest.main()
