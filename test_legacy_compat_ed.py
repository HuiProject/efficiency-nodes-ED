import sys
from pathlib import Path
import unittest

# Allow the focused tests to run directly from the plugin folder while using
# the same ComfyUI checkout as the running application.
COMFY_ROOT = Path(__file__).resolve().parents[2]
if str(COMFY_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFY_ROOT))

from legacy_compat_ed import (
    _safe_eval,
    EvaluateIntegersED,
    EvaluateStringsED,
    LoRAStackToStringED,
    PackSDXLTupleED,
    UnpackSDXLTupleED,
)


class TestLegacyCompatED(unittest.TestCase):
    def test_safe_numeric_expression(self):
        self.assertEqual(_safe_eval("((a + b) - c) / 2", {"a": 10, "b": 4, "c": 2}), 6.0)

    def test_safe_string_expression_and_len(self):
        self.assertEqual(_safe_eval("a + b + c", {"a": "A", "b": "B", "c": "C"}), "ABC")
        self.assertEqual(_safe_eval("len(a) + 1", {"a": "AB"}), 3)

    def test_unsupported_expression_is_rejected(self):
        with self.assertRaises(ValueError):
            _safe_eval("__import__('os').getcwd()", {"a": 0, "b": 0, "c": 0})

    def test_legacy_output_contracts(self):
        self.assertEqual(EvaluateIntegersED().evaluate("a + b", "False", 2, 3, 0), (5, 5.0, "5"))
        self.assertEqual(EvaluateStringsED().evaluate("a + b", "False", "A", "B", ""), ("AB",))
        self.assertEqual(
            LoRAStackToStringED().convert([("Anima/style.safetensors", 0.5, 0.25)]),
            ("<lora:Anima/style.safetensors:0.5:0.25>",),
        )

    def test_sdxl_tuple_round_trip(self):
        values = tuple(range(8))
        packed = PackSDXLTupleED().pack_sdxl_tuple(*values)[0]
        self.assertEqual(UnpackSDXLTupleED().unpack_sdxl_tuple(packed), values)
        with self.assertRaises(ValueError):
            UnpackSDXLTupleED().unpack_sdxl_tuple((1, 2))


if __name__ == "__main__":
    unittest.main()
