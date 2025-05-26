"""
Centralized configuration module for Anthrasite Lead-Factory.

This module loads all environment variables used in the application consistently
and provides typed access to configuration values with appropriate defaults.

Note: This module is maintained for backward compatibility only.
New code should import directly from the `leadfactory.config` package.
"""

import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from leadfactory.config.loader import (
    get_boolean_env,
    get_config,
    get_env,
    get_float_env,
    get_int_env,
    load_config,
)

# Re-export everything from our new package structure
from leadfactory.config.settings import *

# For backward compatibility, ensure all modules can still access these functions
__all__ = [
    "load_config",
    "get_config",
    "get_env",
    "get_boolean_env",
    "get_int_env",
    "get_float_env",
]
