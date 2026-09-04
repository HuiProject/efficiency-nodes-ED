import unittest

from xy_legacy_ed import LegacyXYLoraPlotED
from xy_lora_ed import EDLoraPipe, EDLoraAxisValue, combine_sweep_stacks
from xy_plot_ed import compose_xyplot_script


class TestEDLoraPlot(unittest.TestCase):
    def setUp(self):
        self.stack = [
            ("Anima\\first.safetensors", 0.6, 0.7),
            ("Anima\\second.safetensors", 0.2, 0.3),
        ]
        self.pipe = EDLoraPipe(object(), object(), object(), object(), self.stack)

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

    def test_two_selected_loras_build_model_and_clip_axes(self):
        x_axis, y_axis = LegacyXYLoraPlotED().xy_value(
            lora_count=2,
            X_batch_count=2, X_first_value=0.1, X_last_value=0.9,
            Y_batch_count=2, Y_first_value=0.2, Y_last_value=0.8,
            lora_pipe=self.pipe,
            scan_lora_name_1=self.stack[0][0], scan_lora_1_toggle=True,
            scan_lora_name_2=self.stack[1][0], scan_lora_2_toggle=True,
        )
        self.assertEqual(x_axis[0], "ED_LORA_SWEEP_X")
        self.assertEqual(y_axis[0], "ED_LORA_SWEEP_Y")
        self.assertTrue(all(isinstance(value, EDLoraAxisValue) for value in x_axis[1]))
        self.assertEqual(x_axis[1][0].plan.axis_mode, "model")
        self.assertEqual(y_axis[1][0].plan.axis_mode, "clip")
        self.assertEqual(x_axis[1][0].value, {
            "anima\\first.safetensors": 0.1,
            "anima\\second.safetensors": 0.1,
        })

    def test_model_and_clip_axes_combine_on_same_target(self):
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
        combined = combine_sweep_stacks(
            self.pipe, x_axis[1][0].plan, x_axis[1][0].value,
            y_axis[1][0].plan, y_axis[1][0].value,
        )
        self.assertEqual(combined[0], ("Anima\\first.safetensors", 0.4, 0.7))

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
