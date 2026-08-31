import unittest

from xy_lora_ed import EDLoraPipe, EDLoraSweepPlan, generate_sweep_values, stack_fingerprint


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


if __name__ == "__main__":
    unittest.main()
