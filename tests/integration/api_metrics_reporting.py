"""
API metrics reporting and visualization for LeadFactory.

This module provides functionality for aggregating, analyzing, and visualizing
API metrics collected during integration tests.
"""

import datetime
import json
import os
import re
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


class APIMetricsReport:
    """Generate reports and visualizations from API metrics data."""

    def __init__(self, metrics_data: List[Dict[str, Any]] = None):
        """
        Initialize the reporter with metrics data.

        Args:
            metrics_data: List of metric dictionaries to analyze
        """
        self.metrics_data = metrics_data or []
        self.metrics_dir = Path(os.environ.get('METRICS_DIR', 'metrics'))
        self.report_dir = self.metrics_dir / 'reports'
        self.report_dir.mkdir(parents=True, exist_ok=True)

        # Initialize data storage
        self._df = None
        self._api_names = set()
        self._endpoints = {}

    def load_metrics_from_file(self, filepath: str) -> None:
        """
        Load metrics from a JSONL file.

        Args:
            filepath: Path to the metrics file
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Metrics file not found: {filepath}")

        metrics = []
        with open(path, 'r') as f:
            for line in f:
                try:
                    metric = json.loads(line.strip())
                    metrics.append(metric)
                except json.JSONDecodeError:
                    continue

        self.metrics_data.extend(metrics)

    def load_metrics_from_directory(self, directory: str = None) -> None:
        """
        Load all metrics files from a directory.

        Args:
            directory: Directory containing metrics files (*.jsonl)
        """
        dir_path = Path(directory) if directory else self.metrics_dir
        if not dir_path.exists():
            raise FileNotFoundError(f"Metrics directory not found: {dir_path}")

        for file in dir_path.glob('*.jsonl'):
            self.load_metrics_from_file(str(file))

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert metrics data to a pandas DataFrame for analysis.

        Returns:
            DataFrame with metrics data
        """
        if self._df is not None:
            return self._df

        if not self.metrics_data:
            self._df = pd.DataFrame()
            return self._df

        # Convert to DataFrame
        df = pd.DataFrame(self.metrics_data)

        # Convert timestamp to datetime
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            df['date'] = df['datetime'].dt.date

        # Add hour and weekday columns for time-based analysis
        if 'datetime' in df.columns:
            df['hour'] = df['datetime'].dt.hour
            df['weekday'] = df['datetime'].dt.day_name()

        # Fill missing values
        df['cost'] = df['cost'].fillna(0)
        df['token_count'] = df['token_count'].fillna(0)

        # Identify unique APIs and endpoints
        self._api_names = set(df['api'].unique())
        self._endpoints = {
            api: set(df[df['api'] == api]['endpoint'].unique())
            for api in self._api_names
        }

        self._df = df
        return df

    def generate_summary_statistics(self) -> Dict[str, Any]:
        """
        Generate summary statistics for all API calls.

        Returns:
            Dictionary of summary statistics
        """
        df = self.to_dataframe()
        if df.empty:
            return {"error": "No metrics data available"}

        # Overall statistics
        stats = {
            "total_calls": len(df),
            "unique_apis": len(self._api_names),
            "total_cost": df['cost'].sum(),
            "total_tokens": int(df['token_count'].sum()),
            "time_period": {
                "start": df['datetime'].min().strftime('%Y-%m-%d %H:%M:%S') if 'datetime' in df else None,
                "end": df['datetime'].max().strftime('%Y-%m-%d %H:%M:%S') if 'datetime' in df else None,
            },
            "request_time": {
                "mean": df['request_time'].mean(),
                "median": df['request_time'].median(),
                "min": df['request_time'].min(),
                "max": df['request_time'].max(),
                "p95": df['request_time'].quantile(0.95),
            },
            "api_breakdown": {}
        }

        # Per-API statistics
        for api in self._api_names:
            api_df = df[df['api'] == api]
            stats["api_breakdown"][api] = {
                "calls": len(api_df),
                "cost": api_df['cost'].sum(),
                "tokens": int(api_df['token_count'].sum()),
                "request_time": {
                    "mean": api_df['request_time'].mean(),
                    "median": api_df['request_time'].median(),
                    "min": api_df['request_time'].min(),
                    "max": api_df['request_time'].max(),
                    "p95": api_df['request_time'].quantile(0.95),
                },
                "success_rate": len(api_df[api_df['status_code'] < 400]) / len(api_df) if len(api_df) > 0 else 0,
                "endpoints": {
                    endpoint: len(api_df[api_df['endpoint'] == endpoint])
                    for endpoint in self._endpoints[api]
                }
            }

        return stats

    def save_summary_report(self, filepath: Optional[str] = None) -> str:
        """
        Save summary statistics to a JSON file.

        Args:
            filepath: Output file path (default: metrics/reports/summary_YYYY-MM-DD.json)

        Returns:
            Path to the saved report
        """
        stats = self.generate_summary_statistics()

        if filepath is None:
            date_str = datetime.datetime.now().strftime('%Y-%m-%d')
            filepath = self.report_dir / f"summary_{date_str}.json"

        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(stats, f, indent=2)

        return str(filepath)

    def plot_request_times_by_api(self, filepath: Optional[str] = None) -> str:
        """
        Generate boxplot of request times by API.

        Args:
            filepath: Output file path (default: metrics/reports/request_times_YYYY-MM-DD.png)

        Returns:
            Path to the saved plot
        """
        df = self.to_dataframe()
        if df.empty:
            raise ValueError("No metrics data available for plotting")

        plt.figure(figsize=(12, 8))
        sns.set_style("whitegrid")

        # Create boxplot
        ax = sns.boxplot(x='api', y='request_time', data=df)

        # Add points for individual measurements
        sns.stripplot(x='api', y='request_time', data=df,
                     size=4, color=".3", linewidth=0, alpha=0.3)

        # Add titles and labels
        plt.title('API Request Times (seconds)', fontsize=16)
        plt.xlabel('API', fontsize=14)
        plt.ylabel('Request Time (s)', fontsize=14)
        plt.xticks(rotation=45)

        # Add summary statistics as text
        stats_text = "Summary Statistics:\n"
        for api in sorted(self._api_names):
            api_df = df[df['api'] == api]
            mean_time = api_df['request_time'].mean()
            median_time = api_df['request_time'].median()
            p95_time = api_df['request_time'].quantile(0.95)
            stats_text += f"{api}: mean={mean_time:.4f}s, median={median_time:.4f}s, p95={p95_time:.4f}s\n"

        plt.figtext(0.1, -0.05, stats_text, fontsize=10)
        plt.tight_layout()

        # Save the plot
        if filepath is None:
            date_str = datetime.datetime.now().strftime('%Y-%m-%d')
            filepath = self.report_dir / f"request_times_{date_str}.png"

        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        plt.savefig(filepath, bbox_inches='tight', dpi=300)
        plt.close()

        return str(filepath)

    def plot_cost_by_api(self, filepath: Optional[str] = None) -> str:
        """
        Generate bar chart of costs by API.

        Args:
            filepath: Output file path (default: metrics/reports/costs_YYYY-MM-DD.png)

        Returns:
            Path to the saved plot
        """
        df = self.to_dataframe()
        if df.empty:
            raise ValueError("No metrics data available for plotting")

        # Group by API and sum costs
        cost_by_api = df.groupby('api')['cost'].sum().reset_index()
        if cost_by_api['cost'].sum() == 0:
            return "No cost data available"

        plt.figure(figsize=(12, 8))
        sns.set_style("whitegrid")

        # Create bar chart
        ax = sns.barplot(x='api', y='cost', data=cost_by_api)

        # Add titles and labels
        plt.title('API Costs (USD)', fontsize=16)
        plt.xlabel('API', fontsize=14)
        plt.ylabel('Cost ($)', fontsize=14)
        plt.xticks(rotation=45)

        # Add total cost as text
        total_cost = cost_by_api['cost'].sum()
        plt.figtext(0.5, 0.01, f"Total Cost: ${total_cost:.6f}", fontsize=12, ha='center')

        # Add cost values on bars
        for i, cost in enumerate(cost_by_api['cost']):
            ax.text(i, cost + 0.0001, f"${cost:.6f}", ha='center', fontsize=10)

        plt.tight_layout()

        # Save the plot
        if filepath is None:
            date_str = datetime.datetime.now().strftime('%Y-%m-%d')
            filepath = self.report_dir / f"costs_{date_str}.png"

        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        plt.savefig(filepath, bbox_inches='tight', dpi=300)
        plt.close()

        return str(filepath)

    def plot_requests_over_time(self, filepath: Optional[str] = None) -> str:
        """
        Generate line chart of API requests over time.

        Args:
            filepath: Output file path (default: metrics/reports/requests_time_YYYY-MM-DD.png)

        Returns:
            Path to the saved plot
        """
        df = self.to_dataframe()
        if df.empty or 'datetime' not in df.columns:
            raise ValueError("No time-series metrics data available for plotting")

        # Prepare time-series data
        df_time = df.set_index('datetime').sort_index()
        requests_by_time = df_time.groupby([pd.Grouper(freq='1H'), 'api']).size().unstack(fill_value=0)

        plt.figure(figsize=(15, 8))
        sns.set_style("whitegrid")

        # Create line chart
        ax = requests_by_time.plot(kind='line', marker='o', ax=plt.gca())

        # Add titles and labels
        plt.title('API Requests Over Time', fontsize=16)
        plt.xlabel('Time', fontsize=14)
        plt.ylabel('Number of Requests', fontsize=14)
        plt.legend(title='API')

        plt.tight_layout()

        # Save the plot
        if filepath is None:
            date_str = datetime.datetime.now().strftime('%Y-%m-%d')
            filepath = self.report_dir / f"requests_time_{date_str}.png"

        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        plt.savefig(filepath, bbox_inches='tight', dpi=300)
        plt.close()

        return str(filepath)

    def generate_html_report(self, filepath: Optional[str] = None) -> str:
        """
        Generate a comprehensive HTML report with all metrics and visualizations.

        Args:
            filepath: Output file path (default: metrics/reports/api_report_YYYY-MM-DD.html)

        Returns:
            Path to the saved HTML report
        """
        # Ensure we have data
        df = self.to_dataframe()
        if df.empty:
            raise ValueError("No metrics data available for reporting")

        # Generate statistics
        stats = self.generate_summary_statistics()

        # Generate plots and save to temporary files
        plots_dir = self.report_dir / "plots"
        plots_dir.mkdir(exist_ok=True)

        request_times_plot = self.plot_request_times_by_api(str(plots_dir / "request_times.png"))
        cost_plot = self.plot_cost_by_api(str(plots_dir / "costs.png"))

        try:
            time_plot = self.plot_requests_over_time(str(plots_dir / "requests_time.png"))
            has_time_plot = True
        except ValueError:
            has_time_plot = False

        # Create HTML content
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>API Metrics Report - {datetime.datetime.now().strftime('%Y-%m-%d')}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #2c3e50; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .section {{ margin-bottom: 30px; border: 1px solid #eee; padding: 20px; border-radius: 5px; }}
                .summary {{ display: flex; flex-wrap: wrap; gap: 20px; }}
                .summary-box {{ background-color: #f8f9fa; border-radius: 5px; padding: 15px; min-width: 200px; }}
                .metric {{ font-size: 24px; font-weight: bold; color: #3498db; }}
                .metric-label {{ font-size: 14px; color: #7f8c8d; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
                .plot {{ margin: 20px 0; text-align: center; }}
                .plot img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>API Metrics Report - {datetime.datetime.now().strftime('%Y-%m-%d')}</h1>

                <div class="section">
                    <h2>Summary</h2>
                    <div class="summary">
                        <div class="summary-box">
                            <div class="metric">{stats['total_calls']}</div>
                            <div class="metric-label">Total API Calls</div>
                        </div>
                        <div class="summary-box">
                            <div class="metric">{stats['unique_apis']}</div>
                            <div class="metric-label">Unique APIs</div>
                        </div>
                        <div class="summary-box">
                            <div class="metric">${stats['total_cost']:.6f}</div>
                            <div class="metric-label">Total Cost</div>
                        </div>
                        <div class="summary-box">
                            <div class="metric">{stats['total_tokens']}</div>
                            <div class="metric-label">Total Tokens</div>
                        </div>
                        <div class="summary-box">
                            <div class="metric">{stats['request_time']['mean']*1000:.2f}ms</div>
                            <div class="metric-label">Avg Request Time</div>
                        </div>
                    </div>
                </div>

                <div class="section">
                    <h2>API Breakdown</h2>
                    <table>
                        <tr>
                            <th>API</th>
                            <th>Calls</th>
                            <th>Cost</th>
                            <th>Tokens</th>
                            <th>Avg Time (ms)</th>
                            <th>Success Rate</th>
                        </tr>
        """

        # Add rows for each API
        for api, api_stats in stats['api_breakdown'].items():
            html += f"""
                        <tr>
                            <td>{api}</td>
                            <td>{api_stats['calls']}</td>
                            <td>${api_stats['cost']:.6f}</td>
                            <td>{api_stats['tokens']}</td>
                            <td>{api_stats['request_time']['mean']*1000:.2f}</td>
                            <td>{api_stats['success_rate']*100:.1f}%</td>
                        </tr>
            """

        html += """
                    </table>
                </div>

                <div class="section">
                    <h2>Visualizations</h2>
        """

        # Add plots
        html += f"""
                    <div class="plot">
                        <h3>Request Times by API</h3>
                        <img src="{os.path.relpath(request_times_plot, os.path.dirname(self.report_dir))}" alt="Request Times">
                    </div>

                    <div class="plot">
                        <h3>API Costs</h3>
                        <img src="{os.path.relpath(cost_plot, os.path.dirname(self.report_dir))}" alt="API Costs">
                    </div>
        """

        if has_time_plot:
            html += f"""
                    <div class="plot">
                        <h3>API Requests Over Time</h3>
                        <img src="{os.path.relpath(time_plot, os.path.dirname(self.report_dir))}" alt="Requests Over Time">
                    </div>
            """

        # Close HTML
        html += """
                </div>
            </div>
        </body>
        </html>
        """

        # Save the HTML report
        if filepath is None:
            date_str = datetime.datetime.now().strftime('%Y-%m-%d')
            filepath = self.report_dir / f"api_report_{date_str}.html"

        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            f.write(html)

        return str(filepath)


def generate_report_from_files(directory: str = None, output_path: str = None) -> str:
    """
    Generate a comprehensive report from metrics files.

    Args:
        directory: Directory containing metrics files
        output_path: Path for the output HTML report

    Returns:
        Path to the generated HTML report
    """
    reporter = APIMetricsReport()
    reporter.load_metrics_from_directory(directory)
    return reporter.generate_html_report(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate API metrics reports")
    parser.add_argument("--dir", help="Directory containing metrics files")
    parser.add_argument("--output", help="Output file path for HTML report")

    args = parser.parse_args()

    try:
        report_path = generate_report_from_files(args.dir, args.output)
        print(f"Report generated: {report_path}")
    except Exception as e:
        print(f"Error generating report: {e}")
        sys.exit(1)
