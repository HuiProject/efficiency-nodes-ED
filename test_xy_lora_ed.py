import unittest

from xy_lora_ed import (EDLoraPipe, EDLoraSweepPlan, EDLoraAxisValue,
                         combine_sweep_stacks, generate_sweep_values,
                         stack_fingerprint, normalize_sweep_rows)


class TestEDLoraSweep(unittest.TestCase):
    def setUp(self):
        self.stack = [
            ("Anima\\first.safetensors", 0.6, 0.6),
            ("Anima\\target.safetensors", 1.0, 1.0),
            ("Anima\\last.safetensors", 0.2, 0.3),
        ]
        self.pipe = EDLoraPipe(object(), object(), object(), object(), self.stack)

    def test_values_include_both_ends(self):
        self.assertEqual(generate_sweep_values(3, 0.5, 1.0), [0.5, 0.75, 1.0])

    def test_target_replaced_once_without_reordering(self):
        plan = EDLoraSweepPlan(self.pipe, "anima/target.safetensors", [0.5])
        resolved = plan.stack_for_value(0.5)
        self.assertEqual([item[0] for item in resolved], [item[0] for item in self.stack])
        self.assertEqual(resolved[1], ("Anima\\target.safetensors", 0.5, 0.5))
        self.assertEqual(sum(item[0].endswith("target.safetensors") for item in resolved), 1)

    def test_baseline_one_matches_power_loader_stack(self):
        plan = EDLoraSweepPlan(self.pipe, "Anima\\target.safetensors", [1.0])
        self.assertEqual(plan.stack_for_value(1.0), self.stack)
        self.assertEqual(stack_fingerprint(plan.stack_for_value(1.0)), self.pipe.fingerprint)

    def test_missing_target_is_rejected(self):
        with self.assertRaises(ValueError):
            EDLoraSweepPlan(self.pipe, "missing.safetensors", [1.0])

    def test_zero_strength_target_can_be_swept(self):
        zero_stack = [("Anima\\disabled-at-baseline.safetensors", 0.0, 0.0)]
        pipe = EDLoraPipe(object(), object(), object(), object(), zero_stack)
        plan = EDLoraSweepPlan(pipe, zero_stack[0][0], [0.0, 0.5, 1.0])
        self.assertEqual(plan.stack_for_value(0.0), zero_stack)
        self.assertEqual(plan.stack_for_value(0.5)[0][1:], (0.5, 0.5))

    def test_two_axes_combine_without_accumulation(self):
        x = EDLoraSweepPlan(self.pipe, "Anima\\first.safetensors", [0.5])
        y = EDLoraSweepPlan(self.pipe, "Anima\\target.safetensors", [0.25])
        combined = combine_sweep_stacks(self.pipe, x, 0.5, y, 0.25)
        self.assertEqual(combined, [
            ("Anima\\first.safetensors", 0.5, 0.5),
            ("Anima\\target.safetensors", 0.25, 0.25),
            ("Anima\\last.safetensors", 0.2, 0.3),
        ])

    def test_one_axis_can_override_multiple_loras(self):
        plan = EDLoraSweepPlan(self.pipe, ["Anima\\first.safetensors", "Anima\\target.safetensors"], [0.0, 1.0],
                               target_specs=[("Anima\\first.safetensors", 0.2, 0.6),
                                             ("Anima\\target.safetensors", 0.4, 0.8)])
        values = plan.axis_values()
        self.assertEqual(plan.stack_for_value(values[0].value), [
            ("Anima\\first.safetensors", 0.2, 0.2),
            ("Anima\\target.safetensors", 0.4, 0.4),
            ("Anima\\last.safetensors", 0.2, 0.3),
        ])
        self.assertEqual(plan.stack_for_value(values[1].value)[0:2], [
            ("Anima\\first.safetensors", 0.6, 0.6),
            ("Anima\\target.safetensors", 0.8, 0.8),
        ])

    def test_normalize_rows_ignores_rows_outside_count(self):
        count, rows = normalize_sweep_rows(1, {
            "scan_lora_name_1": "Anima\\first.safetensors",
            "scan_lora_1_toggle": True,
            "scan_lora_first_strength_1": 0.25,
            "scan_lora_last_strength_1": 0.75,
            "scan_lora_name_2": "Anima\\target.safetensors",
        })
        self.assertEqual(count, 1)
        self.assertEqual(rows, [("Anima\\first.safetensors", 0.25, 0.75)])

    def test_normalize_rows_skips_disabled_and_empty(self):
        count, rows = normalize_sweep_rows(3, {
            "scan_lora_name_1": "None",
            "scan_lora_name_2": "Anima\\target.safetensors",
            "scan_lora_2_toggle": False,
            "scan_lora_name_3": "Anima\\last.safetensors",
            "scan_lora_3_toggle": True,
        })
        self.assertEqual(count, 3)
        self.assertEqual(rows, [("Anima\\last.safetensors", 0.5, 1.0)])


if __name__ == "__main__":
    unittest.main()
