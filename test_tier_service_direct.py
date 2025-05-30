#!/usr/bin/env python3

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Now try to import and test the tier service
try:
    from leadfactory.config.tier_config import TierLevel
    from leadfactory.services.tier_service import (
        APICallResult,
        TierService,
        get_tier_service,
    )

    print("✅ All imports successful!")

    # Test basic functionality
    tier_service = get_tier_service()
    print(f"✅ TierService instance created: {type(tier_service)}")

    # Test API call result with correct parameters
    result = APICallResult(
        success=True, data={"test": "data"}, api_name="test_api", tier_limited=False
    )
    print(f"✅ APICallResult created: {result.success}")

    print("✅ All basic tests passed!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
