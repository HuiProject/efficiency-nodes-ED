import unittest

from xy_legacy_ed import LegacyXYLoraED, LegacyXYLoraPlotED, LegacyXYAestheticScoreED
from xy_lora_compat import XYLoraAxisValue
from xy_plot_ed import compose_xyplot_script


class TestLegacyXYAdapters(unittest.TestCase):
    def test_lora_rows_preserve_stack_and_strengths(self):
        values = {
            "lora_name_1": "Anima\\base.safetensors",
            "model_str_1": 0.25,
            "clip_str_1": 0.5,
            "lora_name_2": "None",
        }
        result = LegacyXYLoraED().xy_value(
            "LoRA Names+Weights", "I:\\", False, "ascending", -1,
            2, 1.0, 1.0,
            lora_stack=[("Anima\\stack.safetensors", 0.6, 0.7)], **values,
        )
        axis_type, axes = result[0]
        self.assertEqual(axis_type, "LoRA")
        self.assertEqual(len(axes), 1)
        self.assertIsInstance(axes[0], XYLoraAxisValue)
        self.assertEqual(axes[0][0], ("Anima\\base.safetensors", 0.25, 0.5))
        self.assertEqual(axes[0][1], ("Anima\\stack.safetensors", 0.6, 0.7))

    def test_plot_connected_stack_uses_one_axis_contract(self):
        axis, lora_names = LegacyXYLoraPlotED().xy_value(
            batch_count=3, lora_count=1, axis="X Model", lora_pipe=None,
            lora_stack=[("Anima\\target.safetensors", 0.6, 0.6)],
            scan_lora_name_1="Anima\\target.safetensors",
            scan_lora_1_toggle=True,
            scan_lora_x_first_strength_1=0.0,
            scan_lora_x_last_strength_1=1.0,
        )
        self.assertEqual(lora_names, "target")
        self.assertEqual(axis[0], "ED_LORA_SWEEP_X")
        self.assertEqual([value.overrides["anima\\target.safetensors"][1]
                          for value in axis[1]], [0.0, 0.5, 1.0])

    def test_plot_composer_retags_legacy_axis_for_ed_sampler(self):
        axis = LegacyXYLoraED().xy_value(
            "LoRA Names", "I:\\", False, "ascending", -1,
            1, 1.0, 1.0,
            lora_stack=[("Anima\\stack.safetensors", 0.6, 0.6)],
            lora_name_1="Anima\\target.safetensors",
        )[0]
        script = compose_xyplot_script(0, "False", "Vertical", "False", "Plot", 1, X=axis)
        self.assertEqual(script["xyplot"][0], "ED_LORA_SWEEP_X")

    def test_aesthetic_score_contract(self):
        result = LegacyXYAestheticScoreED().xy_value("negative", 2, 2.0, 4.0)
        self.assertEqual(result, (("AScore-", [2.0, 4.0]),))

    def test_connected_stack_rejects_global_lora_selection(self):
        error = LegacyXYLoraED.VALIDATE_INPUTS(
            lora_count=1,
            lora_stack=[("Anima\\allowed.safetensors", 0.6, 0.6)],
            lora_name_1="Anima\\not-in-stack.safetensors",
        )
        self.assertIn("not in the connected Power Loader stack", error)


if __name__ == "__main__":
    unittest.main()
