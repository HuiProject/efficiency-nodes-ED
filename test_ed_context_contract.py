import unittest

from ed_context_contract import build_context_io, context_to_tuple, new_context


CONTRACT = {
    "base_ctx": ("base_ctx", "RGTHREE_CONTEXT", "CONTEXT"),
    "model": ("model", "MODEL", "MODEL"),
    "steps": ("steps", "INT", "STEPS"),
    "scheduler": ("scheduler", ["normal"], "SCHEDULER"),
    "xy_raw_positive": ("xy_raw_positive", "STRING", "XY_RAW_POSITIVE"),
    "xy_raw_negative": ("xy_raw_negative", "STRING", "XY_RAW_NEGATIVE"),
    "lora_pipe": ("lora_pipe", "ED_LORA_PIPE", "LORA_PIPE"),
}


class TestEDContextContract(unittest.TestCase):
    def test_merge_preserves_ed_xy_fields(self):
        base = {
            "model": object(),
            "steps": 30,
            "scheduler": "normal",
            "xy_raw_positive": "positive prompt",
            "xy_raw_negative": "negative prompt",
            "lora_pipe": object(),
        }
        result = new_context(CONTRACT, base, steps=42)
        self.assertEqual(result["steps"], 42)
        self.assertEqual(result["xy_raw_positive"], "positive prompt")
        self.assertEqual(result["xy_raw_negative"], "negative prompt")
        self.assertIs(result["lora_pipe"], base["lora_pipe"])
        self.assertIsNot(result, base)

    def test_return_order_matches_stable_socket_contract(self):
        context = new_context(CONTRACT, None, steps=30, scheduler="normal")
        values = context_to_tuple(CONTRACT, context)
        self.assertIs(values[0], context)
        self.assertEqual(values[2], 30)
        self.assertEqual(values[3], "normal")
        self.assertEqual(len(values), 7)

    def test_metadata_keeps_combo_type_and_forced_input(self):
        optional, types, names = build_context_io(
            CONTRACT, force_input_types=("INT", "STRING", "FLOAT"),
            force_input_names=("scheduler",),
        )
        self.assertEqual(optional["scheduler"][0], ["normal"])
        self.assertTrue(optional["scheduler"][1]["forceInput"])
        self.assertEqual(types[0], "RGTHREE_CONTEXT")
        self.assertEqual(
            names,
            ("CONTEXT", "MODEL", "STEPS", "SCHEDULER", "XY_RAW_POSITIVE", "XY_RAW_NEGATIVE", "LORA_PIPE"),
        )


if __name__ == "__main__":
    unittest.main()
