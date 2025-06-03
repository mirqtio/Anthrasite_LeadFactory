"""
Mock modules for BDD testing.

This file creates mock objects for the leadfactory package and its submodules
to allow BDD tests to run without requiring a complete installation.
"""

import sys
from unittest.mock import MagicMock

# Create mock classes and functions for leadfactory.pipeline
mock_scrape = MagicMock()
mock_enrich = MagicMock()
mock_dedupe = MagicMock()
mock_score = MagicMock()
mock_email_queue = MagicMock()

# Create mock classes and functions for leadfactory.cost
mock_budget_gate = MagicMock()

# Create mock classes and functions for leadfactory.utils
mock_utils = MagicMock()

# Create the module structure
class MockModule(MagicMock):
    """A mock module that can have attributes added to it."""
    @classmethod
    def mock_module(cls, name):
        """Create a mock module with the given name."""
        mock = cls()
        sys.modules[name] = mock
        return mock

# Create the main leadfactory module
leadfactory = MockModule.mock_module("leadfactory")

# Create the pipeline submodule
pipeline = MockModule.mock_module("leadfactory.pipeline")
pipeline.scrape = mock_scrape
pipeline.enrich = mock_enrich
pipeline.dedupe = mock_dedupe
pipeline.score = mock_score
pipeline.email_queue = mock_email_queue
pipeline.budget_gate = mock_budget_gate

# Create the cost submodule
cost = MockModule.mock_module("leadfactory.cost")
cost.budget_gate = mock_budget_gate

# Create the utils submodule
utils = MockModule.mock_module("leadfactory.utils")
utils.db = MagicMock()
utils.metrics = MagicMock()
utils.logging = MagicMock()
