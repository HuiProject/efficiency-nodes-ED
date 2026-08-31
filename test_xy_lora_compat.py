import unittest

from xy_lora_compat import make_axis_value, make_stack_sweep, merge_partial_stack, merge_stack


class XYLoraCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.base_stack = [
            ("Anima\\shiny-skin.safetensors", 0.6, 0.6),
            ("Anima\\face.safetensors", 0.2, 0.2),
        ]
        self.target = "Anima\\target.safetensors"

    def test_missing_target_matches_lora_stacker_order(self):
        actual = merge_stack((self.target, 0.5, 1.0), self.base_stack)
        expected = [(self.target, 0.5, 1.0), *self.base_stack]
        self.assertEqual(expected, actual)

    def test_model_and_clip_axes_compose_per_cell(self):
        x_half = make_axis_value((self.target, 0.5, None), self.base_stack, 1.0, 1.0)
        x_full = make_axis_value((self.target, 1.0, None), self.base_stack, 1.0, 1.0)
        y_full = make_axis_value((self.target, None, 1.0), self.base_stack, 1.0, 1.0)

        half_cell = merge_partial_stack(y_full, merge_partial_stack(x_half))
        full_cell = merge_partial_stack(y_full, merge_partial_stack(x_full))

        self.assertEqual((self.target, 0.5, 1.0), half_cell[0])
        self.assertEqual((self.target, 1.0, 1.0), full_cell[0])
        self.assertNotEqual(half_cell, full_cell)

    def test_existing_target_is_replaced_without_duplication(self):
        base = [(self.target, 0.6, 0.6), *self.base_stack]
        actual = merge_stack((self.target, 1.0, 1.0), base)
        self.assertEqual((self.target, 1.0, 1.0), actual[0])
        self.assertEqual(1, sum(name == self.target for name, _, _ in actual))

    def test_connected_stack_sweep_matches_manual_strength_changes(self):
        base = [(self.target, 0.6, 0.6), *self.base_stack]
        sweep = make_stack_sweep(self.target, base, [0.0, 0.5, 1.0])
        resolved = [merge_partial_stack(value) for value in sweep]
        expected = [
            [(self.target, 0.0, 0.0), *self.base_stack],
            [(self.target, 0.5, 0.5), *self.base_stack],
            [(self.target, 1.0, 1.0), *self.base_stack],
        ]
        self.assertEqual(expected, resolved)

    def test_connected_stack_sweep_rejects_unlisted_target(self):
        with self.assertRaisesRegex(ValueError, "not enabled in the connected stack"):
            make_stack_sweep(self.target, self.base_stack, [0.5])


if __name__ == "__main__":
    unittest.main()
