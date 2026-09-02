import sys
from pathlib import Path
import unittest

COMFY_ROOT = Path(__file__).resolve().parents[2]
if str(COMFY_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFY_ROOT))

from legacy_pipeline_ed import (  # noqa: E402
    _apply_common_axis,
    _parse_semicolon_values,
    build_legacy_xy_script,
)


class TestLegacyPipelineED(unittest.TestCase):
    def test_parse_common_legacy_axes(self):
        self.assertEqual(_parse_semicolon_values("Steps", "20;30;40;"), [20, 30, 40])
        self.assertEqual(_parse_semicolon_values("CFG Scale", "5;7.5"), [5.0, 7.5])
        self.assertEqual(_parse_semicolon_values("Seeds++ Batch", "3"), [0, 1, 2])
        self.assertEqual(
            _parse_semicolon_values("Sampler", "euler;k_euler,karras"),
            [("euler", None), ("k_euler", "karras")],
        )

    def test_legacy_xy_script_preserves_axis_order(self):
        script = build_legacy_xy_script("Steps", "20;30", "CFG Scale", "5;7", 10, "False")
        self.assertEqual(script["xyplot"][:5], ("Steps", [20, 30], "CFG Scale", [5.0, 7.0], 10))
        self.assertFalse(script["xyplot"][7])

    def test_legacy_xy_flip_swaps_axis_payloads(self):
        script = build_legacy_xy_script("Steps", "20", "Denoise", "0.5", 0, "True")
        self.assertEqual(script["xyplot"][:4], ("Denoise", [0.5], "Steps", [20]))

    def test_unsupported_axis_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not migrated"):
            build_legacy_xy_script("LoRA", "x", "Nothing", "", 0, "False")

    def test_apply_common_axis_does_not_accumulate_between_cells(self):
        state = {"seed": 100, "steps": 20, "cfg": 7.0, "sampler": "euler", "scheduler": "normal", "denoise": 1.0}
        _apply_common_axis("Seeds++ Batch", 2, state)
        _apply_common_axis("Sampler", ("heun", "karras"), state)
        self.assertEqual(state, {"seed": 102, "steps": 20, "cfg": 7.0, "sampler": "heun", "scheduler": "karras", "denoise": 1.0})


if __name__ == "__main__":
    unittest.main()
