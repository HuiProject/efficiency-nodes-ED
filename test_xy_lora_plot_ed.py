import unittest

from xy_legacy_ed import LegacyXYLoraPlotED
from xy_lora_ed import EDLoraPipe
from xy_lora_compat import LegacyOverlayAxisValue, get_axis_plan


class TestEDLoraPlot(unittest.TestCase):
    def setUp(self):
        self.stack = [
            ("Anima\\first.safetensors", 0.6, 0.7),
            ("Anima\\second.safetensors", 0.2, 0.3),
        ]
        self.pipe = EDLoraPipe(
            object(), object(), object(), object(), self.stack,
            available_loras=[item[0] for item in self.stack] + ["Anima\\overlay-only.safetensors"],
        )

    def test_single_axis_contract_and_order(self):
        names = set(LegacyXYLoraPlotED.INPUT_TYPES()["required"])
        self.assertEqual(list(LegacyXYLoraPlotED.INPUT_TYPES()["required"])[:3],
                         ["batch_count", "lora_count", "axis"])
        self.assertNotIn("X_batch_count", names)
        self.assertNotIn("Y_batch_count", names)
        self.assertIn("axis", names)
        self.assertEqual(LegacyXYLoraPlotED.RETURN_TYPES, ("XY",))
        self.assertEqual(LegacyXYLoraPlotED.RETURN_NAMES, ("XY_AXIS",))

    def test_axis_modes_select_one_direction_and_weight_field(self):
        common = dict(
            lora_count=1, batch_count=2,
            lora_pipe=self.pipe,
            scan_lora_name_1=self.stack[0][0], scan_lora_1_toggle=True,
            scan_lora_x_first_strength_1=0.2, scan_lora_x_last_strength_1=0.8,
            scan_lora_y_first_strength_1=0.3, scan_lora_y_last_strength_1=0.7,
        )
        x_clip, = LegacyXYLoraPlotED().xy_value(axis="X Clip", **common)
        self.assertEqual(x_clip[0], "ED_LORA_SWEEP_X")
        self.assertEqual(len(x_clip[1]), 2)
        self.assertEqual(x_clip[1][0].overrides["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", None, 0.2))

        y_model, = LegacyXYLoraPlotED().xy_value(axis="Y Model", **common)
        self.assertEqual(y_model[0], "ED_LORA_SWEEP_Y")
        self.assertEqual(len(y_model[1]), 2)
        self.assertEqual(y_model[1][-1].overrides["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", 0.7, None))

    def test_two_selected_loras_build_second_layer_model_and_clip_axes(self):
        x_axis, = LegacyXYLoraPlotED().xy_value(
            lora_count=2,
            batch_count=2, axis="X Model and Clip",
            lora_pipe=self.pipe,
            scan_lora_name_1=self.stack[0][0], scan_lora_1_toggle=True,
            scan_lora_x_first_strength_1=0.1, scan_lora_x_last_strength_1=0.9,
            scan_lora_y_first_strength_1=0.2, scan_lora_y_last_strength_1=0.8,
            scan_lora_name_2=self.stack[1][0], scan_lora_2_toggle=True,
            scan_lora_x_first_strength_2=0.4, scan_lora_x_last_strength_2=0.6,
            scan_lora_y_first_strength_2=0.3, scan_lora_y_last_strength_2=0.5,
        )
        self.assertEqual(x_axis[0], "ED_LORA_SWEEP_X")
        self.assertTrue(all(isinstance(value, LegacyOverlayAxisValue) for value in x_axis[1]))
        self.assertEqual(x_axis[1][0].overrides["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", 0.1, 0.2))
        self.assertEqual(x_axis[1][-1].overrides["anima\\second.safetensors"],
                         ("Anima\\second.safetensors", 0.6, 0.5))

    def test_each_selected_lora_uses_its_own_x_and_y_ranges(self):
        """Plot keeps one grid shape while interpolating each row separately."""
        x_axis, = LegacyXYLoraPlotED().xy_value(
            lora_count=2,
            batch_count=3, axis="X Model",
            lora_pipe=self.pipe,
            scan_lora_name_1=self.stack[0][0], scan_lora_1_toggle=True,
            scan_lora_x_first_strength_1=0.1, scan_lora_x_last_strength_1=0.9,
            scan_lora_y_first_strength_1=0.2, scan_lora_y_last_strength_1=0.8,
            scan_lora_name_2=self.stack[1][0], scan_lora_2_toggle=True,
            scan_lora_x_first_strength_2=0.4, scan_lora_x_last_strength_2=0.6,
            scan_lora_y_first_strength_2=0.3, scan_lora_y_last_strength_2=0.5,
        )
        first_x = x_axis[1][0].overrides
        middle_x = x_axis[1][1].overrides
        last_y = x_axis[1][-1].overrides
        self.assertEqual(first_x["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", 0.1, None))
        self.assertEqual(first_x["anima\\second.safetensors"],
                         ("Anima\\second.safetensors", 0.4, None))
        self.assertEqual(middle_x["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", 0.5, None))
        self.assertEqual(middle_x["anima\\second.safetensors"],
                         ("Anima\\second.safetensors", 0.5, None))
        self.assertEqual(last_y["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", 0.9, None))
        self.assertEqual(last_y["anima\\second.safetensors"],
                         ("Anima\\second.safetensors", 0.6, None))

    def test_model_and_clip_axes_are_retagged_for_legacy_overlay_sampler(self):
        x_axis, = LegacyXYLoraPlotED().xy_value(
            lora_count=1,
            batch_count=1, axis="X Model",
            lora_pipe=self.pipe,
            scan_lora_name_1=self.stack[0][0], scan_lora_1_toggle=True,
            scan_lora_x_first_strength_1=0.4,
            scan_lora_x_last_strength_1=0.4,
        )
        self.assertEqual(x_axis[1][0].overrides["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", 0.4, None))

    def test_disabled_power_loader_row_can_be_selected_as_overlay(self):
        x_axis, = LegacyXYLoraPlotED().xy_value(
            lora_count=1,
            batch_count=2, axis="X Model",
            lora_pipe=self.pipe,
            scan_lora_name_1="Anima\\overlay-only.safetensors",
            scan_lora_1_toggle=True,
        )
        self.assertEqual(x_axis[1][0].overrides["anima\\overlay-only.safetensors"],
                         ("Anima\\overlay-only.safetensors", 1.0, None))

    def test_legacy_overlay_axis_has_no_sweep_plan(self):
        """The sampler must not require .plan before the overlay branch."""
        overlay = LegacyOverlayAxisValue([
            ("Anima\\overlay-only.safetensors", 0.5, None),
        ])
        self.assertIsNone(get_axis_plan(overlay))

    def test_target_must_be_in_connected_stack(self):
        with self.assertRaises(ValueError):
            LegacyXYLoraPlotED().xy_value(
                lora_count=1,
                batch_count=2, axis="X Model",
                lora_pipe=self.pipe,
                scan_lora_name_1="loras\\not-in-stack.safetensors",
                scan_lora_1_toggle=True,
            )


if __name__ == "__main__":
    unittest.main()
