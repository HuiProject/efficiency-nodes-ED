import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parent / "tools" / "migrate_legacy_efficiency_workflow.py"
SPEC = importlib.util.spec_from_file_location("ed_legacy_migrator", MODULE_PATH)
MIGRATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATOR)


class TestLegacyWorkflowMigration(unittest.TestCase):
    def test_historical_three_node_pipeline_is_migrated(self):
        document = {"nodes": [
            {"id": 1, "type": "Efficient Loader", "widgets_values": ["model", "Baked VAE", -2, "p", "n", 512, 512, 1]},
            {"id": 2, "type": "KSampler (Efficient)", "widgets_values": ["Script", 0, 99, False, 20, 7, "euler", "normal", 1, "Enabled"]},
            {"id": 3, "type": "XY Plot", "widgets_values": ["Steps", "20;30", "CFG Scale", "5;7", 0, "False"]},
        ]}
        migrated, changed, unsupported = MIGRATOR.migrate_document(document)
        self.assertEqual(len(changed), 3)
        self.assertEqual(unsupported, [])
        self.assertEqual(migrated["nodes"][0]["type"], "Efficient Loader 💬ED (Legacy Compat)")
        self.assertEqual(migrated["nodes"][0]["widgets_values"][3:6], ["None", 1.0, 1.0])
        self.assertEqual(migrated["nodes"][1]["widgets_values"][:6], [99, 20, 7, "euler", "normal", 1])
        self.assertEqual(migrated["nodes"][2]["widgets_values"], ["Steps", "20;30", "CFG Scale", "5;7", 0, "False", "Vertical", "Images"])

    def test_unsupported_legacy_nodes_are_reported(self):
        document = {"nodes": [{"id": 9, "type": "XY Input: LoRA", "widgets_values": []}]}
        _, changed, unsupported = MIGRATOR.migrate_document(document)
        self.assertEqual(changed, [])
        self.assertEqual(unsupported, ["node 9: XY Input: LoRA"])


if __name__ == "__main__":
    unittest.main()
