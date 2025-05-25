import os
import unittest
import tempfile
import json
import subprocess
from unittest import mock
import yaml

class TestCIWorkflowIntegration(unittest.TestCase):
    """Tests for validating proper integration between CI workflows"""

    def setUp(self):
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.workflows_dir = os.path.join(self.root_dir, '.github', 'workflows')

    def test_large_scale_validation_workflow_exists(self):
        """Verify the large-scale validation workflow file exists"""
        workflow_path = os.path.join(self.workflows_dir, 'large-scale-validation.yml')
        self.assertTrue(os.path.exists(workflow_path),
                       f"large-scale-validation.yml not found at {workflow_path}")

    def test_unified_ci_workflow_exists(self):
        """Verify the unified CI workflow file exists"""
        workflow_path = os.path.join(self.workflows_dir, 'unified-ci.yml')
        self.assertTrue(os.path.exists(workflow_path),
                       f"unified-ci.yml not found at {workflow_path}")

    def test_large_scale_validation_workflow_content(self):
        """Verify the large-scale validation workflow has required components"""
        workflow_path = os.path.join(self.workflows_dir, 'large-scale-validation.yml')
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)

        # Check for required workflow structure
        self.assertIn('on', workflow, "Workflow missing 'on' section")
        self.assertIn('jobs', workflow, "Workflow missing 'jobs' section")

        # Verify workflow triggers
        triggers = workflow.get('on', {})
        self.assertIn('workflow_dispatch', triggers,
                     "Workflow should support manual triggering via workflow_dispatch")
        self.assertIn('schedule', triggers,
                     "Workflow should have scheduled runs")

        # Verify job configuration
        jobs = workflow.get('jobs', {})
        self.assertIn('large-scale-validation', jobs,
                     "Workflow should have a 'large-scale-validation' job")

        validation_job = jobs.get('large-scale-validation', {})
        self.assertIn('steps', validation_job,
                     "Validation job should have steps")

        # Verify presence of key steps
        steps = validation_job.get('steps', [])
        step_ids = [step.get('id', '') for step in steps]

        self.assertTrue(any('validation_tests' in step_id for step_id in step_ids),
                       "Validation job should have a validation tests step")

        # Verify success criteria verification
        step_contents = [str(step.get('run', '')) for step in steps]
        self.assertTrue(any('verify' in content.lower() and 'threshold' in content.lower()
                          for content in step_contents),
                       "Validation job should verify performance thresholds")

    def test_unified_ci_triggers_large_scale_validation(self):
        """Verify unified CI workflow properly triggers large-scale validation workflow"""
        unified_ci_path = os.path.join(self.workflows_dir, 'unified-ci.yml')
        with open(unified_ci_path, 'r') as f:
            workflow = yaml.safe_load(f)

        # Check for required job
        jobs = workflow.get('jobs', {})
        self.assertIn('trigger-large-scale-validation', jobs,
                     "Unified CI workflow should have a job to trigger large-scale validation")

        trigger_job = jobs.get('trigger-large-scale-validation', {})

        # Check job dependencies
        self.assertIn('needs', trigger_job,
                     "Trigger job should have dependencies")

        # Check conditional execution
        self.assertIn('if', trigger_job,
                     "Trigger job should have conditional execution")

        # Check that it targets the correct workflow
        steps = trigger_job.get('steps', [])
        workflow_script = None
        for step in steps:
            if 'script' in step.get('with', {}):
                script_content = step.get('with', {}).get('script', '')
                if 'workflow_id' in script_content and 'createWorkflowDispatch' in script_content:
                    workflow_script = script_content
                    break

        self.assertIsNotNone(workflow_script,
                            "Trigger job should have a step that dispatches a workflow")
        self.assertIn('large-scale-validation.yml', workflow_script,
                     "Trigger job should target the large-scale-validation workflow")

    def test_input_parameters_consistency(self):
        """Verify input parameters are consistent between workflows"""
        # Load large-scale validation workflow
        lsv_path = os.path.join(self.workflows_dir, 'large-scale-validation.yml')
        with open(lsv_path, 'r') as f:
            lsv_workflow = yaml.safe_load(f)

        # Load unified CI workflow
        unified_ci_path = os.path.join(self.workflows_dir, 'unified-ci.yml')
        with open(unified_ci_path, 'r') as f:
            unified_workflow = yaml.safe_load(f)

        # Get input parameters from large-scale validation workflow
        lsv_inputs = lsv_workflow.get('on', {}).get('workflow_dispatch', {}).get('inputs', {})
        lsv_input_names = set(lsv_inputs.keys())

        # Find trigger job in unified workflow
        trigger_job = unified_workflow.get('jobs', {}).get('trigger-large-scale-validation', {})

        # Extract input parameters from the script
        trigger_inputs = {}
        for step in trigger_job.get('steps', []):
            if 'script' in step.get('with', {}):
                script = step.get('with', {}).get('script', '')
                if 'inputs:' in script:
                    # Parse the inputs from the script
                    inputs_section = script.split('inputs:')[1].split('}')[0]
                    for line in inputs_section.strip().split('\n'):
                        if ':' in line:
                            key = line.split(':')[0].strip()
                            trigger_inputs[key] = True

        # Verify that the trigger job uses valid input parameters
        for input_name in trigger_inputs:
            self.assertIn(input_name, lsv_input_names,
                         f"Trigger job uses input parameter '{input_name}' that is not defined in the large-scale validation workflow")

if __name__ == '__main__':
    unittest.main()
