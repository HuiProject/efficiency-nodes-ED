import unittest

from xy_legacy_ed import LegacyXYLoraPlotED
from xy_lora_ed import EDLoraPipe
from xy_lora_compat import LegacyOverlayAxisValue, get_axis_plan
from xy_plot_ed import compose_xyplot_script


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

    def test_compact_contract_drops_legacy_path_and_strength_widgets(self):
        names = set(LegacyXYLoraPlotED.INPUT_TYPES()["required"])
        self.assertNotIn("X_batch_path", names)
        self.assertNotIn("X_subdirectories", names)
        self.assertNotIn("model_strength", names)
        self.assertNotIn("clip_strength", names)
        self.assertEqual(
            names & {"X_first_value", "X_last_value", "Y_first_value", "Y_last_value"},
            {"X_first_value", "X_last_value", "Y_first_value", "Y_last_value"},
        )

    def test_two_selected_loras_build_second_layer_model_and_clip_axes(self):
        x_axis, y_axis = LegacyXYLoraPlotED().xy_value(
            lora_count=2,
            X_batch_count=2, X_first_value=0.1, X_last_value=0.9,
            Y_batch_count=2, Y_first_value=0.2, Y_last_value=0.8,
            lora_pipe=self.pipe,
            scan_lora_name_1=self.stack[0][0], scan_lora_1_toggle=True,
            scan_lora_name_2=self.stack[1][0], scan_lora_2_toggle=True,
        )
        self.assertEqual(x_axis[0], "LoRA MStr")
        self.assertEqual(y_axis[0], "LoRA CStr")
        self.assertTrue(all(isinstance(value, LegacyOverlayAxisValue) for value in x_axis[1]))
        self.assertEqual(x_axis[1][0].overrides["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", 0.1, None))
        self.assertEqual(y_axis[1][-1].overrides["anima\\second.safetensors"],
                         ("Anima\\second.safetensors", None, 0.8))

    def test_each_selected_lora_uses_its_own_x_and_y_ranges(self):
        """Plot keeps one grid shape while interpolating each row separately."""
        x_axis, y_axis = LegacyXYLoraPlotED().xy_value(
            lora_count=2,
            X_batch_count=3, X_first_value=-9.0, X_last_value=-8.0,
            Y_batch_count=3, Y_first_value=-7.0, Y_last_value=-6.0,
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
        last_y = y_axis[1][-1].overrides
        self.assertEqual(first_x["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", 0.1, None))
        self.assertEqual(first_x["anima\\second.safetensors"],
                         ("Anima\\second.safetensors", 0.4, None))
        self.assertEqual(middle_x["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", 0.5, None))
        self.assertEqual(middle_x["anima\\second.safetensors"],
                         ("Anima\\second.safetensors", 0.5, None))
        self.assertEqual(last_y["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", None, 0.8))
        self.assertEqual(last_y["anima\\second.safetensors"],
                         ("Anima\\second.safetensors", None, 0.5))

    def test_model_and_clip_axes_are_retagged_for_legacy_overlay_sampler(self):
        x_axis, y_axis = LegacyXYLoraPlotED().xy_value(
            lora_count=1,
            X_batch_count=1, X_first_value=0.4, X_last_value=0.4,
            Y_batch_count=1, Y_first_value=0.7, Y_last_value=0.7,
            lora_pipe=self.pipe,
            scan_lora_name_1=self.stack[0][0], scan_lora_1_toggle=True,
        )
        script = compose_xyplot_script(
            0, "False", "Vertical", "False", "Images", "1",
            dependencies=("loader",), X=x_axis, Y=y_axis,
        )
        self.assertEqual(script["xyplot"][0:4], (
            "ED_LORA_SWEEP_X", x_axis[1], "ED_LORA_SWEEP_Y", y_axis[1]
        ))
        self.assertEqual(x_axis[1][0].overrides["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", 0.4, None))
        self.assertEqual(y_axis[1][0].overrides["anima\\first.safetensors"],
                         ("Anima\\first.safetensors", None, 0.7))

    def test_disabled_power_loader_row_can_be_selected_as_overlay(self):
        x_axis, y_axis = LegacyXYLoraPlotED().xy_value(
            lora_count=1,
            X_batch_count=2, X_first_value=0.5, X_last_value=1.0,
            Y_batch_count=1, Y_first_value=1.0, Y_last_value=1.0,
            lora_pipe=self.pipe,
            scan_lora_name_1="Anima\\overlay-only.safetensors",
            scan_lora_1_toggle=True,
        )
        self.assertEqual(x_axis[1][0].overrides["anima\\overlay-only.safetensors"],
                         ("Anima\\overlay-only.safetensors", 0.5, None))
        self.assertEqual(y_axis[1][0].overrides["anima\\overlay-only.safetensors"],
                         ("Anima\\overlay-only.safetensors", None, 1.0))

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
                X_batch_count=2, X_first_value=0.0, X_last_value=1.0,
                Y_batch_count=2, Y_first_value=0.0, Y_last_value=1.0,
                lora_pipe=self.pipe,
                scan_lora_name_1="loras\\not-in-stack.safetensors",
                scan_lora_1_toggle=True,
            )


if __name__ == "__main__":
    unittest.main()
