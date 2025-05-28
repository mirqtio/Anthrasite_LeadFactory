#!/usr/bin/env python3
"""
Script to analyze deduplication logs and generate insights.

This script reads dedupe logs and provides analysis on:
- Merge patterns and success rates
- Performance metrics
- Common conflict types
- Error patterns
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Add project root to path
sys.path.insert(0, "/Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory")

from leadfactory.pipeline.dedupe_logging import DedupeLogAnalyzer


class EnhancedDedupeLogAnalyzer(DedupeLogAnalyzer):
    """Enhanced analyzer with additional analysis capabilities."""

    def __init__(self, log_file: Optional[str] = None):
        super().__init__(log_file)

    def load_logs_from_file(
        self,
        file_path: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict]:
        """Load logs from a JSON lines file."""
        logs = []

        try:
            with open(file_path, "r") as f:
                for line in f:
                    try:
                        log = json.loads(line.strip())

                        # Parse timestamp
                        if "timestamp" in log:
                            log_time = datetime.fromisoformat(
                                log["timestamp"].replace("Z", "+00:00")
                            )

                            # Filter by time range if specified
                            if start_time and log_time < start_time:
                                continue
                            if end_time and log_time > end_time:
                                continue

                        logs.append(log)
                    except json.JSONDecodeError:
                        continue

        except FileNotFoundError:
            print(f"Log file not found: {file_path}")
            return []

        self.logs = logs
        return logs

    def analyze_conflicts(self) -> Dict[str, Any]:
        """Analyze field conflicts from logs."""
        conflict_logs = [
            log for log in self.logs if log.get("event_type") == "field_conflict"
        ]

        if not conflict_logs:
            return {"message": "No conflict logs found"}

        # Analyze conflicts by field
        conflicts_by_field = defaultdict(list)
        resolution_strategies = defaultdict(int)

        for log in conflict_logs:
            field = log.get("field", "unknown")
            strategy = log.get("resolution_strategy", "unknown")

            conflicts_by_field[field].append(
                {
                    "primary": log.get("primary_value"),
                    "secondary": log.get("secondary_value"),
                    "resolved": log.get("resolved_value"),
                    "strategy": strategy,
                }
            )

            resolution_strategies[strategy] += 1

        # Calculate statistics
        field_stats = {}
        for field, conflicts in conflicts_by_field.items():
            field_stats[field] = {
                "count": len(conflicts),
                "sample_conflicts": conflicts[:5],  # Show first 5 examples
            }

        return {
            "total_conflicts": len(conflict_logs),
            "fields_with_conflicts": len(conflicts_by_field),
            "resolution_strategies": dict(resolution_strategies),
            "field_statistics": field_stats,
        }

    def analyze_duplicate_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in duplicate detection."""
        duplicate_logs = [
            log for log in self.logs if log.get("event_type") == "duplicate_found"
        ]

        if not duplicate_logs:
            return {"message": "No duplicate detection logs found"}

        # Analyze by match type
        match_types = defaultdict(int)
        similarity_scores = []

        for log in duplicate_logs:
            match_type = log.get("match_type", "unknown")
            match_types[match_type] += 1

            if "similarity_score" in log:
                similarity_scores.append(log["similarity_score"])

        # Calculate similarity statistics
        similarity_stats = {}
        if similarity_scores:
            similarity_stats = {
                "average": sum(similarity_scores) / len(similarity_scores),
                "min": min(similarity_scores),
                "max": max(similarity_scores),
                "count": len(similarity_scores),
            }

        return {
            "total_duplicates_found": len(duplicate_logs),
            "match_types": dict(match_types),
            "similarity_statistics": similarity_stats,
        }

    def analyze_operation_performance(self) -> Dict[str, Any]:
        """Analyze operation performance from logs."""
        operation_logs = [
            log
            for log in self.logs
            if "operation_id" in log and "duration_seconds" in log
        ]

        if not operation_logs:
            return {"message": "No operation performance logs found"}

        # Group by operation type
        operations = defaultdict(list)

        for log in operation_logs:
            op_type = log.get("operation_type", "unknown")
            duration = log.get("duration_seconds", 0)
            status = log.get("status", "unknown")

            operations[op_type].append({"duration": duration, "status": status})

        # Calculate statistics per operation type
        operation_stats = {}
        for op_type, ops in operations.items():
            durations = [op["duration"] for op in ops]
            success_count = sum(1 for op in ops if op["status"] == "success")

            operation_stats[op_type] = {
                "count": len(ops),
                "success_count": success_count,
                "failure_count": len(ops) - success_count,
                "success_rate": (success_count / len(ops) * 100) if ops else 0,
                "avg_duration": sum(durations) / len(durations) if durations else 0,
                "min_duration": min(durations) if durations else 0,
                "max_duration": max(durations) if durations else 0,
            }

        return operation_stats

    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate a comprehensive summary report."""
        # Get batch progress logs
        batch_logs = [
            log for log in self.logs if log.get("event_type") == "batch_progress"
        ]

        # Get the final batch summary if available
        final_batch = None
        if batch_logs:
            # Sort by processed count to get the final state
            batch_logs.sort(key=lambda x: x.get("processed", 0))
            final_batch = batch_logs[-1] if batch_logs else None

        return {
            "report_generated": datetime.utcnow().isoformat(),
            "logs_analyzed": len(self.logs),
            "time_range": {
                "start": (
                    min(log.get("timestamp", "") for log in self.logs)
                    if self.logs
                    else None
                ),
                "end": (
                    max(log.get("timestamp", "") for log in self.logs)
                    if self.logs
                    else None
                ),
            },
            "batch_summary": (
                {
                    "total_processed": (
                        final_batch.get("processed", 0) if final_batch else 0
                    ),
                    "total_merged": final_batch.get("merged", 0) if final_batch else 0,
                    "total_flagged": (
                        final_batch.get("flagged", 0) if final_batch else 0
                    ),
                    "total_errors": final_batch.get("errors", 0) if final_batch else 0,
                }
                if final_batch
                else None
            ),
            "merge_analysis": self.analyze_merge_patterns(),
            "conflict_analysis": self.analyze_conflicts(),
            "duplicate_patterns": self.analyze_duplicate_patterns(),
            "performance_analysis": self.analyze_operation_performance(),
        }


def main():
    """Main entry point for the log analysis script."""
    parser = argparse.ArgumentParser(
        description="Analyze deduplication logs and generate insights"
    )
    parser.add_argument("log_file", help="Path to the log file (JSON lines format)")
    parser.add_argument(
        "--start-time",
        help="Start time for analysis (ISO format)",
        type=lambda s: datetime.fromisoformat(s),
    )
    parser.add_argument(
        "--end-time",
        help="End time for analysis (ISO format)",
        type=lambda s: datetime.fromisoformat(s),
    )
    parser.add_argument(
        "--output", help="Output file for the report (default: stdout)", default=None
    )
    parser.add_argument(
        "--format", choices=["json", "text"], default="text", help="Output format"
    )

    args = parser.parse_args()

    # Create analyzer
    analyzer = EnhancedDedupeLogAnalyzer()

    # Load logs
    print(f"Loading logs from {args.log_file}...")
    logs = analyzer.load_logs_from_file(
        args.log_file, start_time=args.start_time, end_time=args.end_time
    )
    print(f"Loaded {len(logs)} log entries")

    # Generate report
    print("Analyzing logs...")
    report = analyzer.generate_summary_report()

    # Output report
    if args.format == "json":
        output = json.dumps(report, indent=2)
    else:
        # Format as text
        output = format_text_report(report)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report written to {args.output}")
    else:
        print("\n" + "=" * 80)
        print("DEDUPLICATION LOG ANALYSIS REPORT")
        print("=" * 80)
        print(output)


def format_text_report(report: Dict[str, Any]) -> str:
    """Format the report as human-readable text."""
    lines = []

    # Summary
    lines.append(f"Report Generated: {report['report_generated']}")
    lines.append(f"Logs Analyzed: {report['logs_analyzed']}")

    if report.get("time_range"):
        lines.append(
            f"Time Range: {report['time_range']['start']} to {report['time_range']['end']}"
        )

    lines.append("")

    # Batch Summary
    if report.get("batch_summary"):
        lines.append("BATCH SUMMARY:")
        lines.append("-" * 40)
        batch = report["batch_summary"]
        lines.append(f"Total Processed: {batch['total_processed']}")
        lines.append(f"Total Merged: {batch['total_merged']}")
        lines.append(f"Total Flagged: {batch['total_flagged']}")
        lines.append(f"Total Errors: {batch['total_errors']}")
        lines.append("")

    # Merge Analysis
    if report.get("merge_analysis") and "message" not in report["merge_analysis"]:
        lines.append("MERGE ANALYSIS:")
        lines.append("-" * 40)
        merge = report["merge_analysis"]
        lines.append(f"Total Merges: {merge.get('total_merges', 0)}")
        lines.append(f"Successful Merges: {merge.get('successful_merges', 0)}")
        lines.append(f"Success Rate: {merge.get('success_rate', 0):.1f}%")
        lines.append(f"Average Confidence: {merge.get('average_confidence', 0):.2f}")
        lines.append("")

    # Performance Analysis
    if report.get("performance_analysis"):
        lines.append("PERFORMANCE ANALYSIS:")
        lines.append("-" * 40)
        for op_type, stats in report["performance_analysis"].items():
            lines.append(f"\n{op_type}:")
            lines.append(f"  Count: {stats['count']}")
            lines.append(f"  Success Rate: {stats['success_rate']:.1f}%")
            lines.append(f"  Avg Duration: {stats['avg_duration']:.3f}s")
            lines.append(
                f"  Min/Max Duration: {stats['min_duration']:.3f}s / {stats['max_duration']:.3f}s"
            )
        lines.append("")

    # Conflict Analysis
    if report.get("conflict_analysis") and "message" not in report["conflict_analysis"]:
        lines.append("CONFLICT ANALYSIS:")
        lines.append("-" * 40)
        conflicts = report["conflict_analysis"]
        lines.append(f"Total Conflicts: {conflicts.get('total_conflicts', 0)}")
        lines.append(
            f"Fields with Conflicts: {conflicts.get('fields_with_conflicts', 0)}"
        )

        if conflicts.get("resolution_strategies"):
            lines.append("\nResolution Strategies Used:")
            for strategy, count in conflicts["resolution_strategies"].items():
                lines.append(f"  {strategy}: {count}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
