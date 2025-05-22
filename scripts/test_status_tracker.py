#!/usr/bin/env python3
"""
Test Status Tracker

This script analyzes the test suite, categorizes tests, and tracks their status
during the incremental re-enablement process.

Usage:
    python scripts/test_status_tracker.py [--run-tests] [--categorize] [--report]

Options:
    --run-tests    Run all tests and record their status
    --categorize   Analyze and categorize tests by type
    --report       Generate a status report
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

# Try to import visualization libraries, but don't fail if they're not available
try:
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_VISUALIZATION = True
except ImportError:
    HAS_VISUALIZATION = False

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Constants
TEST_DIR = project_root / "tests"
STATUS_FILE = project_root / "scripts" / "test_status.json"
HISTORY_FILE = project_root / "scripts" / "test_history.json"
VISUALIZATION_DIR = project_root / "test_results" / "visualizations"
CATEGORIES = [
    "core_utilities",
    "business_logic",
    "integration",
    "api",
    "database",
    "email",
    "metrics",
    "other"
]

# Test status enum
STATUS_DISABLED = "disabled"
STATUS_FAILING = "failing"
STATUS_PASSING = "passing"
STATUS_SKIPPED = "skipped"

class TestStatusTracker:
    def __init__(self):
        self.tests = {}
        self.history = self.load_history()
        self.load_status()
    
    def load_status(self):
        """Load existing test status from file"""
        if STATUS_FILE.exists():
            with open(STATUS_FILE, "r") as f:
                self.tests = json.load(f)
        else:
            self.discover_tests()
    
    def load_history(self):
        """Load test history from file"""
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        else:
            return {
                "runs": [],
                "status_history": {},
                "last_update": None
            }
    
    def save_status(self):
        """Save current test status to file"""
        with open(STATUS_FILE, "w") as f:
            json.dump(self.tests, f, indent=2)
    
    def save_history(self):
        """Save test history to file"""
        with open(HISTORY_FILE, "w") as f:
            json.dump(self.history, f, indent=2)
    
    def discover_tests(self):
        """Discover all tests in the test directory"""
        print("Discovering tests...")
        
        # Find all test files
        test_files = list(TEST_DIR.glob("test_*.py"))
        test_files.extend(TEST_DIR.glob("**/test_*.py"))
        
        # Extract test functions from files
        for test_file in test_files:
            rel_path = test_file.relative_to(project_root)
            with open(test_file, "r") as f:
                content = f.read()
            
            # Find test functions (def test_*)
            test_funcs = re.findall(r"def\s+(test_\w+)\s*\(", content)
            
            # Add each test to our dictionary
            for func in test_funcs:
                test_id = f"{rel_path}::{func}"
                if test_id not in self.tests:
                    self.tests[test_id] = {
                        "file": str(rel_path),
                        "function": func,
                        "status": STATUS_DISABLED,  # All tests are initially disabled in CI
                        "category": "uncategorized",
                        "last_run": None,
                        "error_message": None,
                        "notes": "",
                        "priority": 3  # Default medium priority
                    }
        
        print(f"Discovered {len(self.tests)} tests")
    
    def categorize_tests(self):
        """Categorize tests based on their file name and content"""
        print("Categorizing tests...")
        
        for test_id, test_info in self.tests.items():
            file_path = project_root / test_info["file"]
            
            # Categorize based on filename
            filename = file_path.name
            
            if "unit" in filename:
                test_info["category"] = "core_utilities"
                test_info["priority"] = 1  # High priority
            elif any(x in filename for x in ["dedupe", "enrich", "score"]):
                test_info["category"] = "business_logic"
                test_info["priority"] = 2  # Medium-high priority
            elif any(x in filename for x in ["email", "unsubscribe"]):
                test_info["category"] = "email"
                test_info["priority"] = 2
            elif any(x in filename for x in ["metrics", "prometheus"]):
                test_info["category"] = "metrics"
                test_info["priority"] = 2
            elif "database" in filename or "schema" in filename:
                test_info["category"] = "database"
                test_info["priority"] = 1
            elif "scraper" in filename:
                test_info["category"] = "integration"
                test_info["priority"] = 3  # Medium-low priority
            else:
                # Read file content to better categorize
                with open(file_path, "r") as f:
                    content = f.read()
                
                if "requests" in content or "api" in content.lower():
                    test_info["category"] = "api"
                    test_info["priority"] = 3
                elif "db" in content or "database" in content or "cursor" in content:
                    test_info["category"] = "database"
                    test_info["priority"] = 2
                else:
                    test_info["category"] = "other"
                    test_info["priority"] = 4  # Low priority
        
        self.save_status()
        print("Categorization complete")
    
    def run_tests(self, test_pattern=None, ci_mode=False):
        """Run tests and update their status
        
        Args:
            test_pattern: Optional pattern to filter tests (e.g., 'test_database*')
            ci_mode: If True, use CI-specific settings
        """
        print("Running tests...")
        
        # Create a temporary directory for test results
        os.makedirs(project_root / "test_results", exist_ok=True)
        
        # Build pytest command
        pytest_cmd = ["pytest", "--json-report", "--json-report-file=test_results/report.json"]
        
        # Add test pattern if provided
        if test_pattern:
            pytest_cmd.append(test_pattern)
        
        # Add CI-specific options
        if ci_mode:
            pytest_cmd.extend(["-v", "--tb=native"])
        
        # Track start time
        start_time = time.time()
        
        # Run pytest
        result = subprocess.run(
            pytest_cmd,
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Parse the JSON report
        report_path = project_root / "test_results" / "report.json"
        if report_path.exists():
            with open(report_path, "r") as f:
                report = json.load(f)
            
            # Create a new history entry
            run_id = datetime.now().isoformat()
            run_entry = {
                "id": run_id,
                "timestamp": run_id,
                "duration": duration,
                "exit_code": result.returncode,
                "test_pattern": test_pattern,
                "ci_mode": ci_mode,
                "results": {}
            }
            
            # Update test status based on report
            for test_id, test_info in report.get("tests", {}).items():
                if test_id in self.tests:
                    # Get previous status
                    prev_status = self.tests[test_id]["status"]
                    
                    # Update current status
                    if test_info.get("outcome") == "passed":
                        self.tests[test_id]["status"] = STATUS_PASSING
                    elif test_info.get("outcome") == "skipped":
                        self.tests[test_id]["status"] = STATUS_SKIPPED
                    else:
                        self.tests[test_id]["status"] = STATUS_FAILING
                        self.tests[test_id]["error_message"] = test_info.get("call", {}).get("longrepr", "")
                    
                    # Record test duration
                    self.tests[test_id]["duration"] = test_info.get("duration", 0)
                    self.tests[test_id]["last_run"] = run_id
                    
                    # Add to run results
                    run_entry["results"][test_id] = {
                        "status": self.tests[test_id]["status"],
                        "duration": self.tests[test_id]["duration"],
                        "previous_status": prev_status
                    }
                    
                    # Update status history
                    if test_id not in self.history["status_history"]:
                        self.history["status_history"][test_id] = []
                    
                    self.history["status_history"][test_id].append({
                        "timestamp": run_id,
                        "status": self.tests[test_id]["status"],
                        "duration": self.tests[test_id]["duration"]
                    })
            
            # Add run to history
            self.history["runs"].append(run_entry)
            self.history["last_update"] = run_id
            
            # Save history
            self.save_history()
        
        self.save_status()
        print(f"Test run complete. Exit code: {result.returncode}")
        print(f"Duration: {duration:.2f} seconds")
        
        return result.returncode
    
    def generate_report(self, output_file=None):
        """Generate a report of test status
        
        Args:
            output_file: Optional file path to write the report to
        """
        report_lines = ["\n===== TEST STATUS REPORT =====\n"]
        
        # Count tests by status and category
        status_counts = defaultdict(int)
        category_counts = defaultdict(lambda: defaultdict(int))
        
        for test_id, test_info in self.tests.items():
            status = test_info["status"]
            category = test_info["category"]
            
            status_counts[status] += 1
            category_counts[category][status] += 1
        
        # Add summary
        report_lines.append(f"Total tests: {len(self.tests)}")
        for status, count in status_counts.items():
            report_lines.append(f"  {status.upper()}: {count}")
        
        report_lines.append("\nTests by category:")
        for category in sorted(category_counts.keys()):
            cat_total = sum(category_counts[category].values())
            report_lines.append(f"  {category} ({cat_total}):")
            for status, count in category_counts[category].items():
                report_lines.append(f"    {status.upper()}: {count}")
        
        # Add tests by priority
        priority_tests = defaultdict(list)
        for test_id, test_info in self.tests.items():
            priority_tests[test_info["priority"]].append(test_id)
        
        report_lines.append("\nPriority 1 (Highest) tests to enable first:")
        for test_id in sorted(priority_tests[1]):
            test_info = self.tests[test_id]
            report_lines.append(f"  - {test_info['file']}::{test_info['function']} ({test_info['category']})")
        
        # Add next steps
        report_lines.append("\nRecommended next steps:")
        
        # Find disabled high priority tests
        high_priority_disabled = [
            test_id for test_id, test_info in self.tests.items()
            if test_info["status"] == STATUS_DISABLED and test_info["priority"] == 1
        ]
        
        if high_priority_disabled:
            report_lines.append(f"1. Enable these {len(high_priority_disabled)} high-priority tests first:")
            for test_id in sorted(high_priority_disabled)[:5]:  # Show top 5
                test_info = self.tests[test_id]
                report_lines.append(f"   - {test_info['file']}::{test_info['function']}")
            if len(high_priority_disabled) > 5:
                report_lines.append(f"   - ... and {len(high_priority_disabled) - 5} more")
        else:
            # Find medium priority tests
            medium_priority_disabled = [
                test_id for test_id, test_info in self.tests.items()
                if test_info["status"] == STATUS_DISABLED and test_info["priority"] == 2
            ]
            if medium_priority_disabled:
                report_lines.append(f"1. Enable these {len(medium_priority_disabled)} medium-priority tests:")
                for test_id in sorted(medium_priority_disabled)[:5]:  # Show top 5
                    test_info = self.tests[test_id]
                    report_lines.append(f"   - {test_info['file']}::{test_info['function']}")
                if len(medium_priority_disabled) > 5:
                    report_lines.append(f"   - ... and {len(medium_priority_disabled) - 5} more")
        
        # Add history summary if available
        if self.history["runs"]:
            report_lines.append("\nTest Run History:")
            for i, run in enumerate(reversed(self.history["runs"][-5:])):
                run_time = datetime.fromisoformat(run["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                passing = sum(1 for r in run["results"].values() if r["status"] == STATUS_PASSING)
                failing = sum(1 for r in run["results"].values() if r["status"] == STATUS_FAILING)
                skipped = sum(1 for r in run["results"].values() if r["status"] == STATUS_SKIPPED)
                total = len(run["results"])
                report_lines.append(f"  Run {len(self.history['runs']) - i}: {run_time} - "
                                  f"Passing: {passing}/{total}, Failing: {failing}, Skipped: {skipped}")
        
        # Add failing tests with error messages
        failing_tests = [
            (test_id, test_info) for test_id, test_info in self.tests.items()
            if test_info["status"] == STATUS_FAILING and test_info.get("error_message")
        ]
        
        if failing_tests:
            report_lines.append("\nFailing Tests:")
            for test_id, test_info in failing_tests[:5]:  # Show top 5
                report_lines.append(f"  - {test_info['file']}::{test_info['function']}")
                error_msg = test_info.get("error_message", "")
                if error_msg:
                    # Truncate and format error message
                    error_lines = error_msg.split("\n")[:3]  # First 3 lines
                    for line in error_lines:
                        report_lines.append(f"    {line[:100]}" + ("..." if len(line) > 100 else ""))
            if len(failing_tests) > 5:
                report_lines.append(f"    ... and {len(failing_tests) - 5} more failing tests")
        
        # Print report
        report_text = "\n".join(report_lines)
        print(report_text)
        
        # Write to file if requested
        if output_file:
            with open(output_file, "w") as f:
                f.write(report_text)
        
        return report_text
    
    def generate_visualizations(self):
        """Generate visualizations of test status and history"""
        if not HAS_VISUALIZATION:
            print("Visualization libraries not available. Install matplotlib and numpy.")
            return
        
        # Create visualization directory
        os.makedirs(VISUALIZATION_DIR, exist_ok=True)
        
        # 1. Status distribution pie chart
        self._create_status_pie_chart()
        
        # 2. Category status stacked bar chart
        self._create_category_bar_chart()
        
        # 3. Test status history line chart (if history available)
        if self.history["runs"]:
            self._create_history_line_chart()
        
        print(f"Visualizations saved to {VISUALIZATION_DIR}")
    
    def _create_status_pie_chart(self):
        """Create a pie chart of test status distribution"""
        status_counts = defaultdict(int)
        for test_info in self.tests.values():
            status_counts[test_info["status"]] += 1
        
        # Create pie chart
        plt.figure(figsize=(10, 6))
        labels = list(status_counts.keys())
        sizes = list(status_counts.values())
        colors = ['green', 'red', 'gray', 'orange']
        explode = [0.1 if s == STATUS_FAILING else 0 for s in labels]  # Explode failing slice
        
        plt.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
        plt.title('Test Status Distribution')
        plt.savefig(f"{VISUALIZATION_DIR}/status_pie_chart.png")
        plt.close()
    
    def _create_category_bar_chart(self):
        """Create a stacked bar chart of test status by category"""
        category_status = {}
        for category in CATEGORIES:
            category_status[category] = defaultdict(int)
        
        for test_info in self.tests.values():
            category = test_info["category"]
            status = test_info["status"]
            category_status[category][status] += 1
        
        # Filter out empty categories
        category_status = {k: v for k, v in category_status.items() if sum(v.values()) > 0}
        
        # Create stacked bar chart
        plt.figure(figsize=(12, 8))
        categories = list(category_status.keys())
        passing = [category_status[c][STATUS_PASSING] for c in categories]
        failing = [category_status[c][STATUS_FAILING] for c in categories]
        disabled = [category_status[c][STATUS_DISABLED] for c in categories]
        skipped = [category_status[c][STATUS_SKIPPED] for c in categories]
        
        bar_width = 0.6
        indices = np.arange(len(categories))
        
        p1 = plt.bar(indices, passing, bar_width, color='green', label=STATUS_PASSING)
        p2 = plt.bar(indices, failing, bar_width, bottom=passing, color='red', label=STATUS_FAILING)
        p3 = plt.bar(indices, disabled, bar_width, bottom=np.array(passing) + np.array(failing), 
                     color='gray', label=STATUS_DISABLED)
        p4 = plt.bar(indices, skipped, bar_width, 
                     bottom=np.array(passing) + np.array(failing) + np.array(disabled), 
                     color='orange', label=STATUS_SKIPPED)
        
        plt.xlabel('Category')
        plt.ylabel('Number of Tests')
        plt.title('Test Status by Category')
        plt.xticks(indices, categories, rotation=45, ha='right')
        plt.legend()
        plt.tight_layout()
        plt.savefig(f"{VISUALIZATION_DIR}/category_bar_chart.png")
        plt.close()
    
    def _create_history_line_chart(self):
        """Create a line chart of test status history"""
        if len(self.history["runs"]) < 2:
            return  # Need at least 2 runs for a line chart
        
        # Extract data from history
        run_dates = []
        passing_counts = []
        failing_counts = []
        skipped_counts = []
        
        for run in self.history["runs"]:
            run_time = datetime.fromisoformat(run["timestamp"])
            run_dates.append(run_time)
            
            # Count statuses
            passing = sum(1 for r in run["results"].values() if r["status"] == STATUS_PASSING)
            failing = sum(1 for r in run["results"].values() if r["status"] == STATUS_FAILING)
            skipped = sum(1 for r in run["results"].values() if r["status"] == STATUS_SKIPPED)
            
            passing_counts.append(passing)
            failing_counts.append(failing)
            skipped_counts.append(skipped)
        
        # Create line chart
        plt.figure(figsize=(12, 6))
        plt.plot(run_dates, passing_counts, 'g-', label='Passing')
        plt.plot(run_dates, failing_counts, 'r-', label='Failing')
        plt.plot(run_dates, skipped_counts, 'y-', label='Skipped')
        
        plt.xlabel('Date')
        plt.ylabel('Number of Tests')
        plt.title('Test Status History')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"{VISUALIZATION_DIR}/history_line_chart.png")
        plt.close()

def main():
    parser = argparse.ArgumentParser(description="Test Status Tracker")
    parser.add_argument("--run-tests", action="store_true", help="Run all tests and record their status")
    parser.add_argument("--test-pattern", type=str, help="Pattern to filter tests (e.g., 'test_database*')")
    parser.add_argument("--ci-mode", action="store_true", help="Run in CI mode with specific settings")
    parser.add_argument("--categorize", action="store_true", help="Analyze and categorize tests by type")
    parser.add_argument("--report", action="store_true", help="Generate a status report")
    parser.add_argument("--output", type=str, help="Output file for the report")
    parser.add_argument("--visualize", action="store_true", help="Generate visualizations of test status")
    
    args = parser.parse_args()
    
    tracker = TestStatusTracker()
    
    if args.categorize:
        tracker.categorize_tests()
    
    if args.run_tests:
        tracker.run_tests(test_pattern=args.test_pattern, ci_mode=args.ci_mode)
    
    if args.visualize and HAS_VISUALIZATION:
        tracker.generate_visualizations()
    elif args.visualize:
        print("Visualization libraries not available. Install matplotlib and numpy.")
    
    if args.report or (not args.run_tests and not args.categorize and not args.visualize):
        tracker.generate_report(output_file=args.output)

if __name__ == "__main__":
    main()
