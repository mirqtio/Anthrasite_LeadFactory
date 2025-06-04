#!/usr/bin/env python
"""
Generate Test Visualizations
---------------------------
This script generates visualizations of test status and re-enablement progress
to provide a clear picture of the current state of testing in the project.

Usage:
    python generate_test_visualizations.py --input test_results/test_status.json --output docs/test_visualizations

Features:
- Generates bar charts of test status by category
- Creates pie charts of test priority distribution
- Produces trend charts of test re-enablement progress over time
- Outputs SVG files that can be embedded in documentation
"""

import argparse
import json
import logging
import math
import os
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "test_visualizations.log")),
    ],
)
logger = logging.getLogger("generate_test_visualizations")


def ensure_directories():
    """Ensure necessary directories exist."""
    directories = ["logs", "test_results", "docs"]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")


def generate_bar_chart_svg(data, title, width=600, height=400, output_file=None):
    """Generate an SVG bar chart."""
    logger.info(f"Generating bar chart: {title}")

    # Calculate dimensions
    margin = 50
    chart_width = width - 2 * margin
    chart_height = height - 2 * margin

    # Calculate bar width and spacing
    num_bars = len(data)
    bar_width = chart_width / (num_bars * 2)

    # Find the maximum value for scaling
    max_value = max(value for _, value in data)

    # Generate SVG
    svg = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'  <text x="{width / 2}" y="20" text-anchor="middle" font-family="Arial" font-size="16">{title}</text>',
        "  <style>",
        "    .bar { fill: #4285f4; }",
        "    .bar:hover { fill: #3367d6; }",
        "    .axis { stroke: #333; stroke-width: 1; }",
        "    .label { font-family: Arial; font-size: 12px; }",
        "    .value { font-family: Arial; font-size: 10px; text-anchor: middle; }",
        "  </style>",
    ]

    # Draw axes
    svg.append(
        f'  <line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" class="axis" />'
    )
    svg.append(
        f'  <line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" class="axis" />'
    )

    # Draw bars
    for i, (label, value) in enumerate(data):
        x = margin + i * (chart_width / num_bars) + bar_width / 2
        bar_height = (value / max_value) * chart_height if max_value > 0 else 0
        y = height - margin - bar_height

        svg.append(
            f'  <rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" class="bar">'
        )
        svg.append(f"    <title>{label}: {value}</title>")
        svg.append("  </rect>")

        # Draw value on top of bar
        svg.append(
            f'  <text x="{x + bar_width / 2}" y="{y - 5}" class="value">{value}</text>'
        )

        # Draw label below bar
        svg.append(
            f'  <text x="{x + bar_width / 2}" y="{height - margin + 15}" text-anchor="middle" transform="rotate(45, {x + bar_width / 2}, {height - margin + 15})" class="label">{label}</text>'
        )

    # Draw y-axis labels
    for i in range(5):
        value = max_value * i / 4
        y = height - margin - (i / 4) * chart_height
        svg.append(
            f'  <text x="{margin - 5}" y="{y}" text-anchor="end" class="label">{int(value)}</text>'
        )
        svg.append(
            f'  <line x1="{margin - 2}" y1="{y}" x2="{margin}" y2="{y}" class="axis" />'
        )

    svg.append("</svg>")

    # Save to file if specified
    if output_file:
        with open(output_file, "w") as f:
            f.write("\n".join(svg))
        logger.info(f"Bar chart saved to {output_file}")

    return "\n".join(svg)


def generate_pie_chart_svg(data, title, width=400, height=400, output_file=None):
    """Generate an SVG pie chart."""
    logger.info(f"Generating pie chart: {title}")

    # Calculate dimensions
    margin = 50
    radius = min(width, height) / 2 - margin
    center_x = width / 2
    center_y = height / 2

    # Calculate total for percentages
    total = sum(value for _, value in data)

    # Generate SVG
    svg = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'  <text x="{width / 2}" y="20" text-anchor="middle" font-family="Arial" font-size="16">{title}</text>',
        "  <style>",
        "    .slice:hover { opacity: 0.8; }",
        "    .label { font-family: Arial; font-size: 12px; }",
        "  </style>",
    ]

    # Colors for the pie slices
    colors = [
        "#4285f4",
        "#ea4335",
        "#fbbc05",
        "#34a853",
        "#673ab7",
        "#3f51b5",
        "#2196f3",
        "#03a9f4",
    ]

    # Draw pie slices
    start_angle = 0
    for i, (label, value) in enumerate(data):
        if value == 0:
            continue

        percentage = value / total * 100 if total > 0 else 0
        angle = 360 * (value / total) if total > 0 else 0
        end_angle = start_angle + angle

        # Convert angles to radians
        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)

        # Calculate arc points
        x1 = center_x + radius * math.sin(start_rad)
        y1 = center_y - radius * math.cos(start_rad)
        x2 = center_x + radius * math.sin(end_rad)
        y2 = center_y - radius * math.cos(end_rad)

        # Determine if the arc is large or small
        large_arc = 1 if angle > 180 else 0

        # Draw the slice
        color = colors[i % len(colors)]
        svg.append(
            f'  <path d="M {center_x} {center_y} L {x1} {y1} A {radius} {radius} 0 {large_arc} 1 {x2} {y2} Z" fill="{color}" class="slice">'
        )
        svg.append(f"    <title>{label}: {value} ({percentage:.1f}%)</title>")
        svg.append("  </path>")

        # Calculate position for label
        label_angle = math.radians(start_angle + angle / 2)
        label_radius = radius * 0.7
        label_x = center_x + label_radius * math.sin(label_angle)
        label_y = center_y - label_radius * math.cos(label_angle)

        # Draw label if slice is large enough
        if angle > 15:
            svg.append(
                f'  <text x="{label_x}" y="{label_y}" text-anchor="middle" class="label">{label}</text>'
            )

        start_angle = end_angle

    # Draw legend
    legend_x = width - margin
    legend_y = margin
    for i, (label, value) in enumerate(data):
        if value == 0:
            continue

        percentage = value / total * 100 if total > 0 else 0
        color = colors[i % len(colors)]

        svg.append(
            f'  <rect x="{legend_x - 10}" y="{legend_y + i * 20}" width="10" height="10" fill="{color}" />'
        )
        svg.append(
            f'  <text x="{legend_x - 15}" y="{legend_y + i * 20 + 9}" text-anchor="end" class="label">{label}: {percentage:.1f}%</text>'
        )

    svg.append("</svg>")

    # Save to file if specified
    if output_file:
        with open(output_file, "w") as f:
            f.write("\n".join(svg))
        logger.info(f"Pie chart saved to {output_file}")

    return "\n".join(svg)


def generate_stacked_bar_chart_svg(
    data, title, width=600, height=400, output_file=None
):
    """Generate an SVG stacked bar chart."""
    logger.info(f"Generating stacked bar chart: {title}")

    # Calculate dimensions
    margin = 50
    chart_width = width - 2 * margin
    chart_height = height - 2 * margin

    # Calculate bar width and spacing
    num_bars = len(data)
    bar_width = chart_width / (num_bars * 2)

    # Find the maximum value for scaling
    max_value = max(sum(values) for _, values in data)

    # Generate SVG
    svg = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'  <text x="{width / 2}" y="20" text-anchor="middle" font-family="Arial" font-size="16">{title}</text>',
        "  <style>",
        "    .bar-enabled { fill: #4285f4; }",
        "    .bar-disabled { fill: #ea4335; }",
        "    .bar-enabled:hover, .bar-disabled:hover { opacity: 0.8; }",
        "    .axis { stroke: #333; stroke-width: 1; }",
        "    .label { font-family: Arial; font-size: 12px; }",
        "    .value { font-family: Arial; font-size: 10px; text-anchor: middle; }",
        "  </style>",
    ]

    # Draw axes
    svg.append(
        f'  <line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" class="axis" />'
    )
    svg.append(
        f'  <line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" class="axis" />'
    )

    # Draw bars
    for i, (label, values) in enumerate(data):
        x = margin + i * (chart_width / num_bars) + bar_width / 2

        # Enabled value (bottom part of the stack)
        enabled_value = values[0]
        enabled_height = (
            (enabled_value / max_value) * chart_height if max_value > 0 else 0
        )
        enabled_y = height - margin - enabled_height

        # Disabled value (top part of the stack)
        disabled_value = values[1]
        disabled_height = (
            (disabled_value / max_value) * chart_height if max_value > 0 else 0
        )
        disabled_y = enabled_y - disabled_height

        # Draw enabled bar
        svg.append(
            f'  <rect x="{x}" y="{enabled_y}" width="{bar_width}" height="{enabled_height}" class="bar-enabled">'
        )
        svg.append(f"    <title>Enabled: {enabled_value}</title>")
        svg.append("  </rect>")

        # Draw disabled bar
        svg.append(
            f'  <rect x="{x}" y="{disabled_y}" width="{bar_width}" height="{disabled_height}" class="bar-disabled">'
        )
        svg.append(f"    <title>Disabled: {disabled_value}</title>")
        svg.append("  </rect>")

        # Draw total value on top of bar
        total_value = enabled_value + disabled_value
        svg.append(
            f'  <text x="{x + bar_width / 2}" y="{disabled_y - 5}" class="value">{total_value}</text>'
        )

        # Draw label below bar
        svg.append(
            f'  <text x="{x + bar_width / 2}" y="{height - margin + 15}" text-anchor="middle" transform="rotate(45, {x + bar_width / 2}, {height - margin + 15})" class="label">{label}</text>'
        )

    # Draw y-axis labels
    for i in range(5):
        value = max_value * i / 4
        y = height - margin - (i / 4) * chart_height
        svg.append(
            f'  <text x="{margin - 5}" y="{y}" text-anchor="end" class="label">{int(value)}</text>'
        )
        svg.append(
            f'  <line x1="{margin - 2}" y1="{y}" x2="{margin}" y2="{y}" class="axis" />'
        )

    # Draw legend
    legend_x = width - margin
    legend_y = margin

    svg.append(
        f'  <rect x="{legend_x - 10}" y="{legend_y}" width="10" height="10" class="bar-enabled" />'
    )
    svg.append(
        f'  <text x="{legend_x - 15}" y="{legend_y + 9}" text-anchor="end" class="label">Enabled</text>'
    )

    svg.append(
        f'  <rect x="{legend_x - 10}" y="{legend_y + 20}" width="10" height="10" class="bar-disabled" />'
    )
    svg.append(
        f'  <text x="{legend_x - 15}" y="{legend_y + 29}" text-anchor="end" class="label">Disabled</text>'
    )

    svg.append("</svg>")

    # Save to file if specified
    if output_file:
        with open(output_file, "w") as f:
            f.write("\n".join(svg))
        logger.info(f"Stacked bar chart saved to {output_file}")

    return "\n".join(svg)


def generate_visualizations(test_data, output_dir):
    """Generate visualizations from test data."""
    logger.info(f"Generating visualizations to {output_dir}")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Generate category bar chart
    category_data = []
    for category, cat_data in sorted(test_data["categories"].items()):
        if cat_data["count"] > 0:
            category_data.append((category, cat_data["count"]))

    generate_bar_chart_svg(
        category_data,
        "Test Files by Category",
        output_file=os.path.join(output_dir, "category_bar_chart.svg"),
    )

    # Generate priority pie chart
    priority_data = []
    for priority in ["critical", "high", "medium", "low"]:
        if priority in test_data["priorities"]:
            priority_data.append((priority, test_data["priorities"][priority]["count"]))

    generate_pie_chart_svg(
        priority_data,
        "Test Files by Priority",
        output_file=os.path.join(output_dir, "priority_pie_chart.svg"),
    )

    # Generate category stacked bar chart
    stacked_data = []
    for category, cat_data in sorted(test_data["categories"].items()):
        if cat_data["count"] > 0:
            enabled = cat_data["enabled"]
            disabled = cat_data["count"] - enabled
            stacked_data.append((category, [enabled, disabled]))

    generate_stacked_bar_chart_svg(
        stacked_data,
        "Test Files Status by Category",
        output_file=os.path.join(output_dir, "category_stacked_bar_chart.svg"),
    )

    # Generate HTML index file
    with open(os.path.join(output_dir, "index.html"), "w") as f:
        f.write(
            f"""<!DOCTYPE html>
<html>
<head>
    <title>Test Status Visualizations</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            line-height: 1.6;
        }}
        h1, h2 {{
            color: #333;
        }}
        .chart-container {{
            margin: 20px 0;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        .chart {{
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>Test Status Visualizations</h1>
    <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

    <div class="chart-container">
        <h2>Test Files by Category</h2>
        <div class="chart">
            <img src="category_bar_chart.svg" alt="Test Files by Category">
        </div>
    </div>

    <div class="chart-container">
        <h2>Test Files by Priority</h2>
        <div class="chart">
            <img src="priority_pie_chart.svg" alt="Test Files by Priority">
        </div>
    </div>

    <div class="chart-container">
        <h2>Test Files Status by Category</h2>
        <div class="chart">
            <img src="category_stacked_bar_chart.svg" alt="Test Files Status by Category">
        </div>
    </div>

    <p><a href="../test_status_report.md">View detailed test status report</a></p>
</body>
</html>
"""
        )

    logger.info(
        f"HTML index file generated at {os.path.join(output_dir, 'index.html')}"
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate Test Visualizations")
    parser.add_argument(
        "--input",
        type=str,
        default="test_results/test_status.json",
        help="Input JSON file with test data",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="docs/test_visualizations",
        help="Output directory for visualizations",
    )
    args = parser.parse_args()

    try:
        # Ensure directories exist
        ensure_directories()

        # Load test data
        with open(args.input) as f:
            test_data = json.load(f)

        # Generate visualizations
        generate_visualizations(test_data, args.output)

        return 0

    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
