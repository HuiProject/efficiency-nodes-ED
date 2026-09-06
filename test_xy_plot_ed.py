import unittest

from xy_plot_ed import compose_xyplot_script
from xy_inputs_ed import EDXYCFG, EDXYSteps, EDXYSamplerScheduler


class TestEDXYPlot(unittest.TestCase):
    def test_ed_axes_are_packed_without_external_plugin(self):
        script = compose_xyplot_script(
            0, "False", "Vertical", "False", "Plot", "42",
            X=("ED_LORA_SWEEP_X", ["x"]),
            Y=("ED_LORA_SWEEP_Y", ["y"]),
        )
        self.assertEqual(script["xyplot"][0:4], (
            "ED_LORA_SWEEP_X", ["x"], "ED_LORA_SWEEP_Y", ["y"],
        ))
        self.assertEqual(script["xyplot"][5], "Vertical")
        self.assertTrue(script["xyplot"][7])

    def test_flip_swaps_axes_and_values(self):
        script = compose_xyplot_script(
            0, "True", "Vertical", "False", "Images", "42",
            X=("ED_LORA_SWEEP_X", ["x"]),
            Y=("Nothing", [""]),
        )
        self.assertEqual(script["xyplot"][0:4], (
            "Nothing", [""], "ED_LORA_SWEEP_X", ["x"],
        ))

    def test_legacy_encoded_axis_requires_dependencies(self):
        script = compose_xyplot_script(
            0, "False", "Vertical", "False", "Images", "42",
            X=("Checkpoint", [1.0]), Y=("Nothing", [""]),
        )
        self.assertIsNone(script)

    def test_cfg_and_steps_emit_expected_axis_values(self):
        self.assertEqual(EDXYCFG().xy_value(3, 0.5, 1.0),
                         (("CFG Scale", [0.5, 0.75, 1.0]),))
        self.assertEqual(EDXYSteps().xy_value(
            "steps", 2, 10, 20, 0, 0, 0, 0, 0, 0
        ), (("Steps", [10, 20]),))

    def test_sampler_scheduler_payload_keeps_scheduler_name(self):
        payload = EDXYSamplerScheduler().xy_value(
            "scheduler", 2, sampler_1="euler", scheduler_1="normal",
            sampler_2="euler", scheduler_2="karras",
        )
        self.assertEqual(payload, (("Scheduler", ["normal", "karras"]),))

    def test_images_mode_is_encoded_as_non_plot(self):
        script = compose_xyplot_script(
            0, "False", "Vertical", "False", "Images", "42",
            X=("CFG Scale", [1.0]), Y=("Nothing", [""]), dependencies={}
        )
        self.assertFalse(script["xyplot"][7])

    def test_plot_plus_image_mode_is_preserved(self):
        script = compose_xyplot_script(
            0, "False", "Vertical", "False", "Plot+Image", "42",
            X=("CFG Scale", [1.0]), Y=("Nothing", [""]), dependencies={}
        )
        self.assertEqual(script["xyplot"][7], "Plot+Image")


if __name__ == "__main__":
    unittest.main()
