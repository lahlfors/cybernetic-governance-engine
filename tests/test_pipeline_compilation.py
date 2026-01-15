import unittest
import os
import json
from src.pipelines.green_stack_pipeline import governance_pipeline
from kfp import compiler

class TestPipelineCompilation(unittest.TestCase):
    def test_pipeline_compiles(self):
        """Verify the KFP pipeline compiles to a valid JSON spec."""
        output_file = "test_pipeline.json"
        try:
            compiler.Compiler().compile(
                pipeline_func=governance_pipeline,
                package_path=output_file
            )
            self.assertTrue(os.path.exists(output_file))

            with open(output_file, 'r') as f:
                pipeline_spec = json.load(f)
                # Check for KFP v2 spec keys
                self.assertIn("pipelineInfo", pipeline_spec)
                self.assertIn("root", pipeline_spec)
                self.assertEqual(pipeline_spec["pipelineInfo"]["name"], "green-stack-governance-loop")
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

if __name__ == "__main__":
    unittest.main()
