#!/usr/bin/env python3
"""
Import Validation Script for LeadFactory.

This script validates that the new import structure works correctly by importing
modules from the new package structure.
"""

import importlib
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

# Add the parent directory to the path so we can import from leadfactory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Modules to validate
MODULES_TO_VALIDATE = [
    # Pipeline modules
    "leadfactory.pipeline.scrape",
    "leadfactory.pipeline.enrich",
    "leadfactory.pipeline.dedupe",
    "leadfactory.pipeline.score",
    "leadfactory.pipeline.email_queue",
    "leadfactory.pipeline.mockup",
    # Utility modules
    "leadfactory.utils.string_utils",
    "leadfactory.utils.metrics",
    "leadfactory.utils.batch_completion_monitor",
    # Cost tracking modules
    "leadfactory.cost.budget_gate",
    "leadfactory.cost.cost_tracking",
    "leadfactory.cost.budget_audit",
    # Configuration
    "leadfactory.config",
]


def validate_import(module_name: str) -> Tuple[bool, Optional[Exception]]:
    """Validate that a module can be imported.

    Args:
        module_name: Name of the module to import

    Returns:
        Tuple of (success, exception)
    """
    try:
        module = importlib.import_module(module_name)
        return True, None
    except Exception as e:
        return False, e


def validate_all_imports() -> Dict[str, Tuple[bool, Optional[Exception]]]:
    """Validate all imports.

    Returns:
        Dictionary mapping module names to validation results
    """
    results = {}

    for module_name in MODULES_TO_VALIDATE:
        success, exception = validate_import(module_name)
        results[module_name] = (success, exception)

    return results


def main():
    """Main entry point for the script."""
    print("Validating imports...")
    results = validate_all_imports()

    # Count successes and failures
    successes = sum(1 for success, _ in results.values() if success)
    failures = len(results) - successes

    print(f"Results: {successes} successes, {failures} failures\n")

    # Print detailed results
    for module_name, (success, exception) in sorted(results.items()):
        if success:
            print(f"✅ {module_name}")
        else:
            print(f"❌ {module_name}: {exception}")

    # Exit with non-zero status if any imports failed
    sys.exit(1 if failures > 0 else 0)


if __name__ == "__main__":
    main()
