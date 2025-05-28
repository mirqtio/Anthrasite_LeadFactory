#!/usr/bin/env python3
"""
Advanced Failure Analyzer and Resolution Module

This module provides sophisticated analysis of pipeline execution failures,
identifies patterns, and implements automatic resolution strategies.
"""

import os
import sys
import re
import json
import logging
import datetime
from typing import Dict, List, Any, Optional, Tuple, Union, Set
from pathlib import Path
from collections import Counter, defaultdict

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parent.parent.parent
if project_root not in sys.path:
    sys.path.append(str(project_root))

from scripts.e2e.execution_logger import ExecutionTracker


class FailurePattern:
    """Represents a recurring failure pattern with metadata and resolution steps."""

    def __init__(
        self,
        pattern_id: str,
        name: str,
        description: str,
        regex_pattern: str,
        category: str,
        stages: List[str],
        resolution_steps: List[str],
        auto_resolvable: bool = False,
        resolution_script: Optional[str] = None,
    ):
        """
        Initialize a FailurePattern.

        Args:
            pattern_id: Unique identifier for the pattern
            name: Human-readable name for the pattern
            description: Detailed description of the failure pattern
            regex_pattern: Regular expression to match against error messages
            category: Category of the failure (e.g., environment, database, network)
            stages: List of pipeline stages where this pattern can occur
            resolution_steps: List of steps to resolve the failure
            auto_resolvable: Whether this failure can be automatically resolved
            resolution_script: Path to a script that can resolve this failure
        """
        self.pattern_id = pattern_id
        self.name = name
        self.description = description
        self.regex_pattern = regex_pattern
        self.regex = re.compile(regex_pattern)
        self.category = category
        self.stages = stages
        self.resolution_steps = resolution_steps
        self.auto_resolvable = auto_resolvable
        self.resolution_script = resolution_script
        self.match_count = 0
        self.last_match_time = None

    def matches(self, error_message: str) -> bool:
        """
        Check if this pattern matches the given error message.

        Args:
            error_message: Error message to check

        Returns:
            True if the pattern matches, False otherwise
        """
        match = self.regex.search(error_message)
        if match:
            self.match_count += 1
            self.last_match_time = datetime.datetime.now()
            return True
        return False

    def get_match_groups(self, error_message: str) -> Optional[Dict[str, str]]:
        """
        Get named capture groups from the regex match.

        Args:
            error_message: Error message to match

        Returns:
            Dictionary of named capture groups, or None if no match
        """
        match = self.regex.search(error_message)
        if match:
            return match.groupdict()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the pattern to a dictionary.

        Returns:
            Dictionary representation of the pattern
        """
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "regex_pattern": self.regex_pattern,
            "category": self.category,
            "stages": self.stages,
            "resolution_steps": self.resolution_steps,
            "auto_resolvable": self.auto_resolvable,
            "resolution_script": self.resolution_script,
            "match_count": self.match_count,
            "last_match_time": (
                self.last_match_time.isoformat() if self.last_match_time else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailurePattern":
        """
        Create a FailurePattern from a dictionary.

        Args:
            data: Dictionary representation of a FailurePattern

        Returns:
            A new FailurePattern instance
        """
        pattern = cls(
            pattern_id=data["pattern_id"],
            name=data["name"],
            description=data["description"],
            regex_pattern=data["regex_pattern"],
            category=data["category"],
            stages=data["stages"],
            resolution_steps=data["resolution_steps"],
            auto_resolvable=data.get("auto_resolvable", False),
            resolution_script=data.get("resolution_script"),
        )

        pattern.match_count = data.get("match_count", 0)
        if data.get("last_match_time"):
            pattern.last_match_time = datetime.datetime.fromisoformat(
                data["last_match_time"]
            )

        return pattern


class FailureAnalyzer:
    """
    Analyzes pipeline execution failures to identify patterns and suggest resolutions.
    """

    def __init__(self, patterns_file: Optional[str] = None):
        """
        Initialize the FailureAnalyzer.

        Args:
            patterns_file: Path to a JSON file containing failure patterns
        """
        # Set up logger first
        self.logger = logging.getLogger("failure_analyzer")
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)

            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

            # File handler
            log_file = project_root / "logs" / "failure_analyzer.log"
            log_file.parent.mkdir(exist_ok=True)

            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

        self.patterns_file = patterns_file or str(
            project_root / "scripts" / "e2e" / "failure_patterns.json"
        )
        self.patterns = self._load_patterns()
        self.tracker = ExecutionTracker()

    def _load_patterns(self) -> List[FailurePattern]:
        """
        Load failure patterns from the patterns file.

        Returns:
            List of FailurePattern objects
        """
        patterns = []

        # If file doesn't exist, create it with default patterns
        if not os.path.exists(self.patterns_file):
            self.logger.info(
                f"Creating default failure patterns file at {self.patterns_file}"
            )
            patterns = self._create_default_patterns()
            self._save_patterns(patterns)
        else:
            try:
                with open(self.patterns_file, "r") as f:
                    patterns_data = json.load(f)

                    for pattern_data in patterns_data:
                        patterns.append(FailurePattern.from_dict(pattern_data))

                self.logger.info(
                    f"Loaded {len(patterns)} failure patterns from {self.patterns_file}"
                )
            except (json.JSONDecodeError, OSError) as e:
                self.logger.error(f"Failed to load failure patterns: {e}")
                patterns = self._create_default_patterns()
                self._save_patterns(patterns)

        return patterns

    def _save_patterns(self, patterns: List[FailurePattern]) -> None:
        """
        Save failure patterns to the patterns file.

        Args:
            patterns: List of FailurePattern objects to save
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.patterns_file), exist_ok=True)

            with open(self.patterns_file, "w") as f:
                patterns_data = [pattern.to_dict() for pattern in patterns]
                json.dump(patterns_data, f, indent=2)

            self.logger.info(
                f"Saved {len(patterns)} failure patterns to {self.patterns_file}"
            )
        except OSError as e:
            self.logger.error(f"Failed to save failure patterns: {e}")

    def _create_default_patterns(self) -> List[FailurePattern]:
        """
        Create default failure patterns.

        Returns:
            List of default FailurePattern objects
        """
        default_patterns = (
            FailurePattern(
                pattern_id="ENV001",
                name="Missing Environment Variable",
                description="An environment variable required by the pipeline is missing",
                regex_pattern=r"Missing required variable: (?P<variable>\w+)",
                category="environment",
                stages=["preflight"],
                resolution_steps=[
                    "Check .env.e2e file for the missing variable",
                    "Add the variable to .env.e2e with the appropriate value",
                    "Re-run the pipeline",
                ],
                auto_resolvable=True,
                resolution_script="scripts/e2e/resolutions/fix_missing_env_var.py",
            ),
            FailurePattern(
                pattern_id="ENV002",
                name="Invalid API Key Format",
                description="An API key has an invalid format",
                regex_pattern=r"(?P<key>\w+) has invalid format: '(?P<value>.+)'",
                category="environment",
                stages=["preflight"],
                resolution_steps=[
                    "Check the format of the API key in .env.e2e",
                    "Update the API key with a valid format",
                    "Re-run the pipeline",
                ],
            ),
            FailurePattern(
                pattern_id="DB001",
                name="Database Connection Failed",
                description="Failed to connect to the database",
                regex_pattern=r"(?:Could not connect to database|Connection refused|Database connection failed): (?P<error>.+)",
                category="database",
                stages=["preflight", "scrape"],
                resolution_steps=[
                    "Check that the database is running",
                    "Verify DATABASE_URL in .env.e2e",
                    "Ensure network connectivity to the database",
                    "Re-run the pipeline",
                ],
            ),
            FailurePattern(
                pattern_id="DB002",
                name="Missing Database Table",
                description="A required database table is missing",
                regex_pattern=r"(?:Table|Relation) ['\"]?(?P<table>\w+)['\"]? does not exist",
                category="database",
                stages=["preflight", "scrape", "email"],
                resolution_steps=[
                    "Run database migrations to create the missing table",
                    "Check database schema setup script",
                    "Re-run the pipeline",
                ],
            ),
            FailurePattern(
                pattern_id="API001",
                name="API Authentication Failed",
                description="Authentication to an external API failed",
                regex_pattern=r"(?P<api>\w+) API (?:returned|failed with) (?:status code )?(?:401|403|Unauthorized|Authentication failed)",
                category="api",
                stages=["preflight", "scrape", "screenshot", "mockup", "email"],
                resolution_steps=[
                    "Check API key in .env.e2e",
                    "Verify API key is valid and not expired",
                    "Update API key if necessary",
                    "Re-run the pipeline",
                ],
            ),
            FailurePattern(
                pattern_id="API002",
                name="API Rate Limit Exceeded",
                description="Rate limit exceeded for an external API",
                regex_pattern=r"(?P<api>\w+) API (?:returned|failed with) (?:status code )?(?:429|Too Many Requests|Rate limit exceeded)",
                category="api",
                stages=["scrape", "screenshot", "mockup", "email"],
                resolution_steps=[
                    "Wait for rate limit to reset",
                    "Reduce request frequency",
                    "Consider upgrading API plan",
                    "Re-run the pipeline",
                ],
            ),
            FailurePattern(
                pattern_id="NET001",
                name="Network Timeout",
                description="A network request timed out",
                regex_pattern=r"(?:Timeout|timed out|Connection timed out|Read timed out) (?:connecting to|while connecting to|during request to) (?P<endpoint>.+)",
                category="network",
                stages=["scrape", "screenshot", "mockup", "email"],
                resolution_steps=[
                    "Check network connectivity",
                    "Verify the endpoint is available",
                    "Consider increasing timeout values",
                    "Re-run the pipeline",
                ],
            ),
            FailurePattern(
                pattern_id="IO001",
                name="File IO Error",
                description="Failed to read or write a file",
                regex_pattern=r"(?:No such file or directory|Permission denied|Cannot (?:read|write) file): (?P<path>.+)",
                category="io",
                stages=[
                    "scrape",
                    "screenshot",
                    "mockup",
                    "personalize",
                    "render",
                    "email",
                ],
                resolution_steps=[
                    "Check that the directory exists",
                    "Verify file permissions",
                    "Create parent directories if needed",
                    "Re-run the pipeline",
                ],
                auto_resolvable=True,
                resolution_script="scripts/e2e/resolutions/fix_io_error.py",
            ),
        )

        self.logger.info(f"Created {len(default_patterns)} default failure patterns")
        return default_patterns

    def add_pattern(self, pattern: FailurePattern) -> None:
        """
        Add a new failure pattern.

        Args:
            pattern: FailurePattern to add
        """
        # Check if a pattern with this ID already exists
        for i, existing in enumerate(self.patterns):
            if existing.pattern_id == pattern.pattern_id:
                self.patterns[i] = pattern
                self.logger.info(f"Updated existing pattern: {pattern.name}")
                self._save_patterns(self.patterns)
                return

        # Add new pattern
        self.patterns.append(pattern)
        self.logger.info(f"Added new pattern: {pattern.name}")
        self._save_patterns(self.patterns)

    def remove_pattern(self, pattern_id: str) -> bool:
        """
        Remove a failure pattern.

        Args:
            pattern_id: ID of the pattern to remove

        Returns:
            True if the pattern was removed, False otherwise
        """
        for i, pattern in enumerate(self.patterns):
            if pattern.pattern_id == pattern_id:
                del self.patterns[i]
                self.logger.info(f"Removed pattern: {pattern_id}")
                self._save_patterns(self.patterns)
                return True

        self.logger.warning(f"Pattern not found: {pattern_id}")
        return False

    def analyze_failure(
        self, stage: str, error_message: str
    ) -> Tuple[List[FailurePattern], Dict[str, Any]]:
        """
        Analyze a failure message to identify matching patterns.

        Args:
            stage: Pipeline stage where the failure occurred
            error_message: Error message to analyze

        Returns:
            List of matching FailurePattern objects and a context dictionary with match details
        """
        matching_patterns = []
        context = {
            "stage": stage,
            "error_message": error_message,
            "matches": [],
            "primary_pattern_id": None,
        }

        for pattern in self.patterns:
            if pattern.matches(error_message):
                # Check if this pattern applies to this stage
                if stage in pattern.stages:
                    matching_patterns.append(pattern)

                    # Get match details
                    match_groups = pattern.get_match_groups(error_message)
                    context["matches"].append(
                        {
                            "pattern_id": pattern.pattern_id,
                            "name": pattern.name,
                            "category": pattern.category,
                            "match_groups": match_groups,
                            "auto_resolvable": pattern.auto_resolvable,
                        }
                    )

        # Sort matching patterns by specificity (more stages = less specific)
        matching_patterns.sort(key=lambda p: (len(p.stages), -p.match_count))

        # Set primary pattern ID if we have matches
        if matching_patterns:
            context["primary_pattern_id"] = matching_patterns[0].pattern_id

        return matching_patterns, context

    def get_resolution_steps(
        self, pattern_id: str, context: Dict[str, Any] = None
    ) -> List[str]:
        """
        Get resolution steps for a failure pattern, with variables replaced from context.

        Args:
            pattern_id: ID of the pattern
            context: Context dictionary with variables to replace

        Returns:
            List of resolution steps with variables replaced
        """
        for pattern in self.patterns:
            if pattern.pattern_id == pattern_id:
                if not context:
                    return pattern.resolution_steps

                # Replace variables in resolution steps
                steps = []
                match_context = {}

                # Find the match for this pattern
                for match in context.get("matches", []):
                    if match["pattern_id"] == pattern_id:
                        match_context = match.get("match_groups", {})
                        break

                for step in pattern.resolution_steps:
                    # Replace variables like {variable} with values from context
                    for key, value in match_context.items():
                        step = step.replace(f"{{{key}}}", value)

                    steps.append(step)

                return steps

        return []

    def is_auto_resolvable(self, pattern_id: str) -> bool:
        """
        Check if a failure pattern is auto-resolvable.

        Args:
            pattern_id: ID of the pattern

        Returns:
            True if the pattern is auto-resolvable, False otherwise
        """
        for pattern in self.patterns:
            if pattern.pattern_id == pattern_id:
                return pattern.auto_resolvable

        return False

    def get_resolution_script(self, pattern_id: str) -> Optional[str]:
        """
        Get the resolution script for a failure pattern.

        Args:
            pattern_id: ID of the pattern

        Returns:
            Path to the resolution script, or None if not available
        """
        for pattern in self.patterns:
            if pattern.pattern_id == pattern_id:
                return pattern.resolution_script

        return None

    def analyze_execution_history(self, num_executions: int = 10) -> Dict[str, Any]:
        """
        Analyze execution history to identify recurring failure patterns.

        Args:
            num_executions: Number of recent executions to analyze

        Returns:
            Analysis results as a dictionary
        """
        recent_executions = self.tracker.get_recent_executions(num_executions)

        if not recent_executions:
            return {
                "executions_analyzed": 0,
                "failure_count": 0,
                "success_rate": 0,
                "frequent_failures": [],
                "recurring_patterns": [],
                "stage_reliability": {},
            }

        # Count executions by status
        status_counts = Counter()
        for execution in recent_executions:
            status_counts[execution.get("status", "unknown")] += 1

        # Count failures by stage and category
        failures_by_stage = defaultdict(int)
        failures_by_category = defaultdict(int)
        failure_messages = defaultdict(list)

        # Count stage failures
        stage_runs = defaultdict(int)
        stage_successes = defaultdict(int)

        for execution in recent_executions:
            for stage_name, stage in execution.get("stages", {}).items():
                stage_runs[stage_name] += 1
                if stage.get("status") == "success":
                    stage_successes[stage_name] += 1

            for failure in execution.get("failures", []):
                stage = failure.get("stage", "unknown")
                category = failure.get("category", "unknown")
                message = failure.get("message", "")

                failures_by_stage[stage] += 1
                failures_by_category[category] += 1
                failure_messages[(stage, category)].append(message)

        # Calculate success rate
        success_count = status_counts.get("success", 0)
        success_rate = (success_count / len(recent_executions)) * 100

        # Identify recurring patterns
        recurring_patterns = []

        for (stage, category), messages in failure_messages.items():
            # Skip if only one occurrence
            if len(messages) <= 1:
                continue

            # Sample up to 5 messages
            sample_messages = messages[:5]

            # Try to match patterns
            pattern_matches = defaultdict(int)
            for message in sample_messages:
                matching_patterns, _ = self.analyze_failure(stage, message)
                for pattern in matching_patterns:
                    pattern_matches[pattern.pattern_id] += 1

            # Add patterns that match multiple messages
            for pattern_id, count in pattern_matches.items():
                if count > 1:
                    for pattern in self.patterns:
                        if pattern.pattern_id == pattern_id:
                            recurring_patterns.append(
                                {
                                    "pattern_id": pattern_id,
                                    "name": pattern.name,
                                    "stage": stage,
                                    "category": category,
                                    "occurrences": count,
                                    "resolution_steps": pattern.resolution_steps,
                                    "auto_resolvable": pattern.auto_resolvable,
                                }
                            )

        # Calculate stage reliability
        stage_reliability = {}
        for stage_name, runs in stage_runs.items():
            successes = stage_successes[stage_name]
            reliability = (successes / runs) * 100 if runs > 0 else 0
            stage_reliability[stage_name] = {
                "runs": runs,
                "successes": successes,
                "failures": runs - successes,
                "reliability": reliability,
            }

        # Sort frequent failures by count
        frequent_failures = [
            {
                "stage": stage,
                "count": count,
                "percentage": (count / len(recent_executions)) * 100,
            }
            for stage, count in failures_by_stage.items()
        ]
        frequent_failures.sort(key=lambda x: x["count"], reverse=True)

        # Sort recurring patterns by occurrences
        recurring_patterns.sort(key=lambda x: x["occurrences"], reverse=True)

        return {
            "executions_analyzed": len(recent_executions),
            "failure_count": len(recent_executions) - success_count,
            "success_rate": success_rate,
            "frequent_failures": frequent_failures,
            "recurring_patterns": recurring_patterns,
            "stage_reliability": stage_reliability,
        }

    def generate_dashboard_data(self) -> Dict[str, Any]:
        """
        Generate data for a failure analysis dashboard.

        Returns:
            Dashboard data as a dictionary
        """
        # Analyze past executions
        history_analysis = self.analyze_execution_history(50)

        # Get statistics on patterns
        pattern_stats = []
        for pattern in self.patterns:
            pattern_stats.append(
                {
                    "pattern_id": pattern.pattern_id,
                    "name": pattern.name,
                    "category": pattern.category,
                    "match_count": pattern.match_count,
                    "last_match_time": (
                        pattern.last_match_time.isoformat()
                        if pattern.last_match_time
                        else None
                    ),
                    "auto_resolvable": pattern.auto_resolvable,
                }
            )

        # Sort by match count
        pattern_stats.sort(key=lambda x: x["match_count"], reverse=True)

        # Get recent executions summary
        recent_executions = self.tracker.get_recent_executions(10)
        execution_summary = []

        for execution in recent_executions:
            execution_id = execution.get("execution_id", "unknown")
            status = execution.get("status", "unknown")
            start_time = execution.get("start_time")
            duration = execution.get("duration", 0)
            failure_count = len(execution.get("failures", []))

            execution_summary.append(
                {
                    "execution_id": execution_id,
                    "status": status,
                    "start_time": start_time,
                    "duration": duration,
                    "failure_count": failure_count,
                }
            )

        return {
            "history_analysis": history_analysis,
            "pattern_stats": pattern_stats,
            "execution_summary": execution_summary,
            "last_updated": datetime.datetime.now().isoformat(),
        }


def main():
    """Main entry point for the failure analyzer."""
    import argparse

    parser = argparse.ArgumentParser(description="E2E Pipeline Failure Analyzer")
    parser.add_argument("--analyze-execution", help="Analyze a specific execution ID")
    parser.add_argument(
        "--history", action="store_true", help="Analyze execution history"
    )
    parser.add_argument(
        "--dashboard", action="store_true", help="Generate dashboard data"
    )
    parser.add_argument("--output", "-o", help="Output file for analysis results")

    args = parser.parse_args()

    analyzer = FailureAnalyzer()

    if args.analyze_execution:
        # Get execution data
        tracker = ExecutionTracker()
        execution = tracker.get_execution(args.analyze_execution)

        if not execution:
            print(f"Execution not found: {args.analyze_execution}")
            return 1

        # Analyze failures
        results = {"execution_id": args.analyze_execution, "failures": []}

        for failure in execution.get("failures", []):
            stage = failure.get("stage", "unknown")
            message = failure.get("message", "")

            matching_patterns, context = analyzer.analyze_failure(stage, message)

            if matching_patterns:
                pattern = matching_patterns[0]
                resolution_steps = analyzer.get_resolution_steps(
                    pattern.pattern_id, context
                )

                results["failures"].append(
                    {
                        "stage": stage,
                        "message": message,
                        "pattern": {
                            "pattern_id": pattern.pattern_id,
                            "name": pattern.name,
                            "category": pattern.category,
                        },
                        "resolution_steps": resolution_steps,
                        "auto_resolvable": pattern.auto_resolvable,
                    }
                )
            else:
                results["failures"].append(
                    {
                        "stage": stage,
                        "message": message,
                        "pattern": None,
                        "resolution_steps": [],
                        "auto_resolvable": False,
                    }
                )

        # Output results
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"Analysis results saved to {args.output}")
        else:
            print(json.dumps(results, indent=2))

    elif args.history:
        results = analyzer.analyze_execution_history()

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"History analysis saved to {args.output}")
        else:
            print(json.dumps(results, indent=2))

    elif args.dashboard:
        results = analyzer.generate_dashboard_data()

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"Dashboard data saved to {args.output}")
        else:
            print(json.dumps(results, indent=2))

    else:
        print(
            "No action specified. Use --analyze-execution, --history, or --dashboard."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
