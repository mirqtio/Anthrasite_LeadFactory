#!/usr/bin/env python3
"""Test script for the enhanced cost dashboard."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_enhanced_dashboard():
    """Test the enhanced dashboard functionality."""
    print("Testing Enhanced Cost Dashboard (Fixed API)...")

    try:
        from leadfactory.monitoring.enhanced_dashboard import EnhancedCostDashboard

        print("✅ Enhanced dashboard module imported successfully")

        # Test dashboard creation
        dashboard = EnhancedCostDashboard(host="127.0.0.1", port=5001)
        print("✅ Enhanced dashboard instance created")

        # Test some of the analytics methods
        cost_data = dashboard._get_enhanced_cost_data(days_back=7)
        print(f"✅ Cost data retrieval: success (type: {type(cost_data).__name__})")

        budget_status = dashboard._get_budget_status()
        status = budget_status.get("status", "unknown")
        print(f"✅ Budget status: {status}")

        optimization = dashboard._generate_optimization_insights()
        score = optimization.get("optimization_score", 0)
        print(f"✅ Optimization insights: {score} score")

        realtime = dashboard._get_realtime_cost_summary()
        today_total = realtime.get("today_total", 0)
        print(f"✅ Realtime summary: ${today_total:.2f} today")

        print("✅ Enhanced Cost Dashboard validation complete")
        return True

    except Exception as e:
        print(f"❌ Enhanced dashboard test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_enhanced_dashboard()
    sys.exit(0 if success else 1)
