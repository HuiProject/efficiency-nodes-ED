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

    def test_single_cell_uses_configured_strength_not_normalized_index(self):
        plan = EDLoraSweepPlan(
            self.pipe, "Anima\\target.safetensors", [0.0],
            target_specs=[("Anima\\target.safetensors", 1.0, 1.0)],
        )
        axes = plan.axis_values()
        self.assertEqual(axes[0].value, {"anima\\target.safetensors": 1.0})
        self.assertEqual(plan.stack_for_value(axes[0].value)[1],
                         ("Anima\\target.safetensors", 1.0, 1.0))

    def test_descending_range_preserves_user_order(self):
        plan = EDLoraSweepPlan(
            self.pipe, "Anima\\target.safetensors", [0.0, 1.0],
            target_specs=[("Anima\\target.safetensors", 1.0, 0.0)],
        )
        self.assertEqual(
            [axis.value["anima\\target.safetensors"] for axis in plan.axis_values()],
            [1.0, 0.0],
        )

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

    def test_model_axis_changes_model_only(self):
        plan = EDLoraSweepPlan(
            self.pipe, "Anima\\target.safetensors", [0.0, 1.0],
            target_specs=[("Anima\\target.safetensors", 0.2, 0.8, 0.3, 0.7)],
            axis_mode="model",
        )
        axes = plan.axis_values()
        self.assertEqual([v.value["anima\\target.safetensors"] for v in axes], [0.2, 0.8])
        self.assertEqual(plan.stack_for_value(axes[0].value)[1],
                         ("Anima\\target.safetensors", 0.2, 1.0))
        self.assertEqual(plan.stack_for_value(axes[1].value)[1],
                         ("Anima\\target.safetensors", 0.8, 1.0))

    def test_clip_axis_changes_clip_only(self):
        plan = EDLoraSweepPlan(
            self.pipe, "Anima\\target.safetensors", [0.0, 1.0],
            target_specs=[("Anima\\target.safetensors", 0.2, 0.8, 0.3, 0.7)],
            axis_mode="clip",
        )
        axes = plan.axis_values()
        self.assertEqual([v.value["anima\\target.safetensors"] for v in axes], [0.3, 0.7])
        self.assertEqual(plan.stack_for_value(axes[0].value)[1],
                         ("Anima\\target.safetensors", 1.0, 0.3))
        self.assertEqual(plan.stack_for_value(axes[1].value)[1],
                         ("Anima\\target.safetensors", 1.0, 0.7))

    def test_model_and_clip_axes_combine_on_same_target(self):
        x = EDLoraSweepPlan(
            self.pipe, "Anima\\target.safetensors", [0.0, 1.0],
            target_specs=[("Anima\\target.safetensors", 0.2, 0.8, 0.3, 0.7)],
            axis_mode="model",
        )
        y = EDLoraSweepPlan(
            self.pipe, "Anima\\target.safetensors", [0.0, 1.0],
            target_specs=[("Anima\\target.safetensors", 0.2, 0.8, 0.3, 0.7)],
            axis_mode="clip",
        )
        combined = combine_sweep_stacks(self.pipe, x, x.axis_values()[0].value,
                                        y, y.axis_values()[1].value)
        self.assertEqual(combined[1], ("Anima\\target.safetensors", 0.2, 0.7))

    def test_missing_clip_range_falls_back_to_model_range(self):
        plan = EDLoraSweepPlan(
            self.pipe, "Anima\\target.safetensors", [0.0, 1.0],
            target_specs=[("Anima\\target.safetensors", 0.25, 0.75)],
            axis_mode="clip",
        )
        self.assertEqual([v.value["anima\\target.safetensors"] for v in plan.axis_values()],
                         [0.25, 0.75])

    def test_normalize_rows_ignores_rows_outside_count(self):
        count, rows = normalize_sweep_rows(1, {
            "scan_lora_name_1": "Anima\\first.safetensors",
            "scan_lora_1_toggle": True,
            "scan_lora_first_strength_1": 0.25,
            "scan_lora_last_strength_1": 0.75,
            "scan_lora_name_2": "Anima\\target.safetensors",
        })
        self.assertEqual(count, 1)
        self.assertEqual(rows, [("Anima\\first.safetensors", 0.25, 0.75, 0.25, 0.75)])

    def test_normalize_rows_skips_disabled_and_empty(self):
        count, rows = normalize_sweep_rows(3, {
            "scan_lora_name_1": "None",
            "scan_lora_name_2": "Anima\\target.safetensors",
            "scan_lora_2_toggle": False,
            "scan_lora_name_3": "Anima\\last.safetensors",
            "scan_lora_3_toggle": True,
        })
        self.assertEqual(count, 3)
        self.assertEqual(rows, [("Anima\\last.safetensors", 0.5, 1.0, 0.5, 1.0)])

    def test_normalize_rows_reads_independent_clip_range_and_alias(self):
        _, rows = normalize_sweep_rows(2, {
            "scan_lora_name_1": "Anima\\first.safetensors",
            "scan_lora_1_toggle": True,
            "scan_lora_first_strength_1": 0.2,
            "scan_lora_last_strength_1": 0.8,
            "scan_lora_clip_first_strength_1": 0.3,
            "scan_lora_clip_last_strength_1": 0.7,
            "scan_lora_name_2": "Anima\\target.safetensors",
            "scan_lora_2_toggle": True,
            "scan_lora_first_strength_2": 0.4,
            "scan_lora_last_strength_2": 0.6,
            "scan_lora_y_first_strength_2": 0.1,
            "scan_lora_y_last_strength_2": 0.9,
        })
        self.assertEqual(rows, [
            ("Anima\\first.safetensors", 0.2, 0.8, 0.3, 0.7),
            ("Anima\\target.safetensors", 0.4, 0.6, 0.1, 0.9),
        ])


if __name__ == "__main__":
    unittest.main()
