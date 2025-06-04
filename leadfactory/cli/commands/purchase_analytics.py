"""
Purchase Analytics CLI Commands
=============================

CLI commands for viewing purchase metrics, revenue analytics, and business intelligence
for the LeadFactory audit business model.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

import click

from leadfactory.cost.purchase_metrics import purchase_metrics_tracker
from leadfactory.monitoring.alert_manager import alert_manager
from leadfactory.monitoring.conversion_tracking import (
    ConversionChannel,
    conversion_tracker,
)
from leadfactory.monitoring.dashboard import run_dashboard
from leadfactory.monitoring.purchase_monitoring import (
    MonitoringPeriod,
    purchase_monitor,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


@click.group()
def purchase():
    """Purchase analytics and metrics commands."""
    pass


@purchase.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def summary(output_format: str):
    """Display comprehensive purchase analytics summary."""
    try:
        analytics_data = purchase_metrics_tracker.get_purchase_analytics_summary()

        if output_format == "json":
            click.echo(json.dumps(analytics_data, indent=2))
            return

        # Table format
        click.echo("=" * 60)
        click.echo("PURCHASE ANALYTICS SUMMARY")
        click.echo("=" * 60)

        # Daily metrics
        daily = analytics_data.get("daily_metrics", {})
        if daily:
            click.echo(f"\n📊 TODAY'S METRICS ({daily.get('date', 'N/A')})")
            click.echo(f"Revenue: ${(daily.get('total_revenue_cents', 0) / 100):,.2f}")
            click.echo(f"Transactions: {daily.get('transaction_count', 0)}")
            click.echo(
                f"Stripe Fees: ${(daily.get('total_stripe_fees_cents', 0) / 100):,.2f}"
            )
            click.echo(
                f"Net Revenue: ${(daily.get('net_revenue_cents', 0) / 100):,.2f}"
            )
            if daily.get("refund_count", 0) > 0:
                click.echo(
                    f"Refunds: {daily.get('refund_count', 0)} (${(daily.get('refund_amount_cents', 0) / 100):,.2f})"
                )

        # Monthly metrics
        monthly = analytics_data.get("monthly_metrics", {})
        if monthly:
            click.echo(
                f"\n📈 THIS MONTH ({monthly.get('year')}/{monthly.get('month')})"
            )
            click.echo(
                f"Revenue: ${(monthly.get('total_revenue_cents', 0) / 100):,.2f}"
            )
            click.echo(f"Transactions: {monthly.get('total_transactions', 0)}")
            click.echo(f"Active Days: {monthly.get('active_days', 0)}")
            if monthly.get("total_refunds", 0) > 0:
                click.echo(
                    f"Refunds: {monthly.get('total_refunds', 0)} (${(monthly.get('total_refund_amount_cents', 0) / 100):,.2f})"
                )

        # Profit analysis
        profit = analytics_data.get("profit_analysis", {})
        if profit and profit.get("revenue"):
            click.echo(f"\n💰 PROFIT ANALYSIS (Last 30 Days)")
            revenue = profit["revenue"]
            costs = profit.get("costs", {})
            profit_info = profit.get("profit", {})

            click.echo(
                f"Gross Revenue: ${revenue.get('gross_revenue_dollars', 0):,.2f}"
            )
            click.echo(f"Stripe Fees: ${revenue.get('stripe_fees_dollars', 0):,.2f}")
            click.echo(f"Net Revenue: ${revenue.get('net_revenue_dollars', 0):,.2f}")
            click.echo(f"Operating Costs: ${costs.get('total_costs_dollars', 0):,.2f}")
            click.echo(
                f"Gross Profit: ${profit_info.get('gross_profit_dollars', 0):,.2f}"
            )
            click.echo(
                f"Profit Margin: {profit_info.get('gross_margin_percent', 0):.1f}%"
            )

        # Customer metrics
        customer = analytics_data.get("customer_metrics", {})
        if customer:
            clv = customer.get("lifetime_value_dollars", 0)
            if clv > 0:
                click.echo(f"\n👥 CUSTOMER METRICS")
                click.echo(f"Customer Lifetime Value: ${clv:,.2f}")

    except Exception as e:
        logger.error(f"Failed to get purchase analytics: {e}")
        click.echo(f"Error: {e}", err=True)


@purchase.command()
@click.option(
    "--audit-type",
    default="all",
    help="Audit type to analyze (default: all)",
)
@click.option(
    "--days",
    type=int,
    default=30,
    help="Number of days to analyze (default: 30)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def conversion(audit_type: str, days: int, output_format: str):
    """Display conversion funnel metrics."""
    try:
        conversion_data = purchase_metrics_tracker.get_conversion_metrics(audit_type)

        if output_format == "json":
            click.echo(json.dumps(conversion_data, indent=2))
            return

        # Table format
        click.echo("=" * 50)
        click.echo(f"CONVERSION METRICS - {audit_type.upper()}")
        click.echo("=" * 50)

        period = conversion_data.get("period", {})
        metrics = conversion_data.get("metrics", {})

        click.echo(f"Period: {period.get('start_date')} to {period.get('end_date')}")
        click.echo(f"Audit Type: {audit_type}")
        click.echo()

        if metrics:
            total_purchases = metrics.get("total_purchases", 0)
            total_revenue = metrics.get("total_revenue_cents", 0)
            aov = metrics.get("average_order_value_cents", 0)

            click.echo(f"Total Purchases: {total_purchases}")
            click.echo(f"Total Revenue: ${(total_revenue / 100):,.2f}")
            click.echo(f"Average Order Value: ${(aov / 100):,.2f}")

            if total_purchases > 0:
                click.echo(
                    f"Revenue per Transaction: ${(total_revenue / total_purchases / 100):,.2f}"
                )
        else:
            click.echo("No conversion data available for the specified period.")

    except Exception as e:
        logger.error(f"Failed to get conversion metrics: {e}")
        click.echo(f"Error: {e}", err=True)


@purchase.command()
@click.option(
    "--days",
    type=int,
    default=365,
    help="Number of days to analyze for CLV calculation (default: 365)",
)
def clv(days: int):
    """Calculate and display Customer Lifetime Value."""
    try:
        clv_dollars = purchase_metrics_tracker.get_customer_lifetime_value(days)

        click.echo("=" * 40)
        click.echo("CUSTOMER LIFETIME VALUE")
        click.echo("=" * 40)
        click.echo(f"Analysis Period: {days} days")
        click.echo(f"Customer Lifetime Value: ${clv_dollars:,.2f}")

        if clv_dollars > 0:
            # Provide some context
            monthly_clv = clv_dollars * 12 / days if days >= 30 else clv_dollars
            click.echo(f"Estimated Monthly CLV: ${monthly_clv:,.2f}")

            # Basic recommendations
            if clv_dollars < 100:
                click.echo("\n💡 Consider strategies to increase customer value:")
                click.echo("   - Upselling premium audit services")
                click.echo("   - Offering subscription models")
                click.echo("   - Improving customer retention")
            elif clv_dollars > 500:
                click.echo("\n🎉 Strong customer lifetime value!")
                click.echo(
                    "   Consider expanding marketing to acquire similar customers"
                )
        else:
            click.echo("\n⚠️  Insufficient data to calculate CLV")

    except Exception as e:
        logger.error(f"Failed to calculate CLV: {e}")
        click.echo(f"Error: {e}", err=True)


@purchase.command()
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD). Defaults to 30 days ago.",
)
@click.option(
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD). Defaults to today.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def profit(
    start_date: Optional[datetime], end_date: Optional[datetime], output_format: str
):
    """Display profit margin analysis for a date range."""
    try:
        # Set default dates if not provided
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Get profit data from financial tracker
        from leadfactory.cost.financial_tracking import financial_tracker

        profit_data = financial_tracker.get_profit_margin_data(start_str, end_str)

        if output_format == "json":
            click.echo(json.dumps(profit_data, indent=2))
            return

        # Table format
        click.echo("=" * 50)
        click.echo("PROFIT MARGIN ANALYSIS")
        click.echo("=" * 50)

        period = profit_data.get("period", {})
        revenue = profit_data.get("revenue", {})
        costs = profit_data.get("costs", {})
        profit_info = profit_data.get("profit", {})

        click.echo(f"Period: {period.get('start_date')} to {period.get('end_date')}")
        click.echo()

        click.echo("REVENUE BREAKDOWN:")
        click.echo(f"  Gross Revenue: ${revenue.get('gross_revenue_dollars', 0):,.2f}")
        click.echo(f"  Stripe Fees:   ${revenue.get('stripe_fees_dollars', 0):,.2f}")
        click.echo(f"  Taxes:         ${revenue.get('tax_dollars', 0):,.2f}")
        click.echo(f"  Net Revenue:   ${revenue.get('net_revenue_dollars', 0):,.2f}")
        click.echo()

        click.echo("COST BREAKDOWN:")
        click.echo(f"  Operating Costs: ${costs.get('total_costs_dollars', 0):,.2f}")
        click.echo()

        click.echo("PROFIT ANALYSIS:")
        click.echo(
            f"  Gross Profit:    ${profit_info.get('gross_profit_dollars', 0):,.2f}"
        )
        click.echo(
            f"  Profit Margin:   {profit_info.get('gross_margin_percent', 0):.1f}%"
        )

        # Provide insights
        margin = profit_info.get("gross_margin_percent", 0)
        if margin > 50:
            click.echo("\n🎉 Excellent profit margins!")
        elif margin > 25:
            click.echo("\n✅ Healthy profit margins")
        elif margin > 0:
            click.echo("\n⚠️  Low profit margins - consider cost optimization")
        else:
            click.echo("\n🚨 Negative margins - immediate attention needed")

    except Exception as e:
        logger.error(f"Failed to get profit analysis: {e}")
        click.echo(f"Error: {e}", err=True)


@purchase.command()
@click.option(
    "--period",
    type=click.Choice(["hourly", "daily", "weekly", "monthly"]),
    default="daily",
    help="Time period for monitoring (default: daily)",
)
@click.option(
    "--lookback-days",
    type=int,
    default=30,
    help="Number of days to look back for trends (default: 30)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def monitor(period: str, lookback_days: int, output_format: str):
    """Display comprehensive purchase monitoring dashboard data."""
    try:
        # Map string to enum
        period_map = {
            "hourly": MonitoringPeriod.HOURLY,
            "daily": MonitoringPeriod.DAILY,
            "weekly": MonitoringPeriod.WEEKLY,
            "monthly": MonitoringPeriod.MONTHLY,
        }

        monitoring_period = period_map[period]
        dashboard_data = purchase_monitor.get_dashboard_data(
            monitoring_period, lookback_days
        )

        if output_format == "json":
            # Convert to JSON-serializable format
            data = {
                "timestamp": dashboard_data.timestamp.isoformat(),
                "period": dashboard_data.period.value,
                "kpis": [
                    {
                        "name": kpi.name,
                        "value": kpi.value,
                        "unit": kpi.unit,
                        "change_percentage": kpi.change_percentage,
                        "trend": kpi.trend,
                        "target": kpi.target,
                    }
                    for kpi in dashboard_data.kpis
                ],
                "revenue_breakdown": dashboard_data.revenue_breakdown,
                "conversion_metrics": dashboard_data.conversion_metrics,
                "alert_summary": dashboard_data.alert_summary,
                "recent_transactions": dashboard_data.recent_transactions,
                "performance_trends": dashboard_data.performance_trends,
            }
            click.echo(json.dumps(data, indent=2))
            return

        # Table format
        click.echo("=" * 70)
        click.echo("PURCHASE MONITORING DASHBOARD")
        click.echo("=" * 70)
        click.echo(f"Period: {period.upper()} | Generated: {dashboard_data.timestamp}")
        click.echo()

        # Display KPIs
        click.echo("📊 KEY PERFORMANCE INDICATORS")
        click.echo("-" * 40)
        for kpi in dashboard_data.kpis:
            trend_symbol = (
                "📈" if kpi.trend == "up" else "📉" if kpi.trend == "down" else "➡️"
            )
            change_text = (
                f" ({kpi.change_percentage:+.1f}%)" if kpi.change_percentage else ""
            )
            target_text = f" | Target: {kpi.target} {kpi.unit}" if kpi.target else ""

            click.echo(
                f"{trend_symbol} {kpi.name}: {kpi.value:,.2f} {kpi.unit}{change_text}{target_text}"
            )

        # Display alerts
        if dashboard_data.alert_summary.get("active_alerts_count", 0) > 0:
            click.echo("\n🚨 ACTIVE ALERTS")
            click.echo("-" * 40)
            for alert in dashboard_data.alert_summary.get("active_alerts", []):
                click.echo(f"⚠️  {alert['rule_name']}: {alert['message']}")

        # Revenue breakdown
        if dashboard_data.revenue_breakdown:
            breakdown = dashboard_data.revenue_breakdown
            click.echo("\n💰 REVENUE BREAKDOWN")
            click.echo("-" * 40)
            click.echo(
                f"Total Revenue: ${breakdown.get('total_revenue_cents', 0)/100:,.2f}"
            )
            click.echo(
                f"Stripe Fees: ${breakdown.get('total_stripe_fees_cents', 0)/100:,.2f}"
            )
            click.echo(
                f"Net Revenue: ${breakdown.get('net_revenue_cents', 0)/100:,.2f}"
            )

            # Audit type breakdown
            by_audit_type = breakdown.get("by_audit_type", {})
            if by_audit_type:
                click.echo("\nBy Audit Type:")
                for audit_type, data in by_audit_type.items():
                    revenue = data.get("revenue_cents", 0) / 100
                    purchases = data.get("purchases", 0)
                    click.echo(
                        f"  {audit_type}: ${revenue:,.2f} ({purchases} purchases)"
                    )

        # Recent transactions
        recent = dashboard_data.recent_transactions
        if recent:
            click.echo(f"\n📋 RECENT TRANSACTIONS (Last {len(recent)})")
            click.echo("-" * 40)
            for txn in recent[:5]:  # Show only first 5
                amount = txn.get("gross_amount_cents", 0) / 100
                audit_type = txn.get("audit_type", "unknown")
                timestamp = txn.get("timestamp", "unknown")
                click.echo(f"  ${amount:,.2f} - {audit_type} - {timestamp}")

    except Exception as e:
        logger.error(f"Failed to get monitoring data: {e}")
        click.echo(f"Error: {e}", err=True)


@purchase.command()
@click.option(
    "--days-back",
    type=int,
    default=30,
    help="Number of days to analyze (default: 30)",
)
@click.option(
    "--audit-type",
    help="Filter by specific audit type",
)
@click.option(
    "--channel",
    type=click.Choice(
        [
            "direct",
            "organic_search",
            "paid_search",
            "social_media",
            "email_marketing",
            "referral",
        ]
    ),
    help="Filter by marketing channel",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def funnel(
    days_back: int,
    audit_type: Optional[str],
    channel: Optional[str],
    output_format: str,
):
    """Analyze conversion funnel performance."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        channel_enum = None
        if channel:
            channel_enum = ConversionChannel(channel)

        funnel_data = conversion_tracker.analyze_funnel(
            start_date, end_date, audit_type, channel_enum
        )

        if output_format == "json":
            data = {
                "period_start": funnel_data.period_start.isoformat(),
                "period_end": funnel_data.period_end.isoformat(),
                "audit_type": funnel_data.audit_type,
                "channel": funnel_data.channel.value if funnel_data.channel else None,
                "funnel_steps": funnel_data.funnel_steps,
                "conversion_rates": funnel_data.conversion_rates,
                "drop_off_points": funnel_data.drop_off_points,
                "total_revenue_cents": funnel_data.total_revenue_cents,
                "average_time_to_conversion": funnel_data.average_time_to_conversion,
            }
            click.echo(json.dumps(data, indent=2))
            return

        # Table format
        click.echo("=" * 60)
        click.echo("CONVERSION FUNNEL ANALYSIS")
        click.echo("=" * 60)
        click.echo(f"Period: {start_date.date()} to {end_date.date()}")
        click.echo(f"Audit Type: {audit_type or 'All'}")
        click.echo(f"Channel: {channel or 'All'}")
        click.echo(f"Total Revenue: ${funnel_data.total_revenue_cents/100:,.2f}")
        if funnel_data.average_time_to_conversion:
            click.echo(
                f"Avg. Time to Conversion: {funnel_data.average_time_to_conversion:.1f} minutes"
            )
        click.echo()

        # Display funnel steps
        click.echo("🔄 FUNNEL STEPS")
        click.echo("-" * 50)
        for step in funnel_data.funnel_steps:
            step_name = step["step"].replace("_", " ").title()
            count = step["count"]
            rate = step.get("conversion_rate")
            rate_text = f" ({rate:.1f}% conversion)" if rate else ""
            click.echo(f"  {step_name}: {count:,} users{rate_text}")

        # Display drop-off points
        if funnel_data.drop_off_points:
            click.echo("\n⚠️  HIGH DROP-OFF POINTS")
            click.echo("-" * 50)
            for drop_off in funnel_data.drop_off_points:
                from_step = drop_off["from_step"].replace("_", " ").title()
                to_step = drop_off["to_step"].replace("_", " ").title()
                rate = drop_off["drop_off_rate"]
                users_lost = drop_off["users_lost"]
                click.echo(
                    f"  {from_step} → {to_step}: {rate:.1f}% drop-off ({users_lost:,} users lost)"
                )

    except Exception as e:
        logger.error(f"Failed to analyze funnel: {e}")
        click.echo(f"Error: {e}", err=True)


@purchase.command()
@click.option(
    "--days-back",
    type=int,
    default=30,
    help="Number of days to analyze (default: 30)",
)
@click.option(
    "--model",
    type=click.Choice(["last_click", "first_click", "linear"]),
    default="last_click",
    help="Attribution model (default: last_click)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def attribution(days_back: int, model: str, output_format: str):
    """Analyze marketing attribution for conversions."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        attribution_data = conversion_tracker.analyze_attribution(
            start_date, end_date, model
        )

        if output_format == "json":
            data = {
                "period_start": attribution_data.period_start.isoformat(),
                "period_end": attribution_data.period_end.isoformat(),
                "channel_performance": attribution_data.channel_performance,
                "top_converting_channels": attribution_data.top_converting_channels,
                "revenue_attribution": attribution_data.revenue_attribution,
                "conversion_paths": attribution_data.conversion_paths,
            }
            click.echo(json.dumps(data, indent=2))
            return

        # Table format
        click.echo("=" * 60)
        click.echo("MARKETING ATTRIBUTION ANALYSIS")
        click.echo("=" * 60)
        click.echo(f"Period: {start_date.date()} to {end_date.date()}")
        click.echo(f"Attribution Model: {model}")
        click.echo()

        # Display top converting channels
        click.echo("🎯 TOP CONVERTING CHANNELS")
        click.echo("-" * 50)
        for i, channel_data in enumerate(
            attribution_data.top_converting_channels[:5], 1
        ):
            channel = channel_data["channel"]
            conversions = channel_data["conversions"]
            revenue = channel_data["revenue_cents"] / 100
            conv_rate = channel_data.get("conversion_rate", 0)

            click.echo(f"{i}. {channel.replace('_', ' ').title()}")
            click.echo(f"   Conversions: {conversions:,}")
            click.echo(f"   Revenue: ${revenue:,.2f}")
            click.echo(f"   Conversion Rate: {conv_rate:.2f}%")
            click.echo()

        # Revenue attribution
        total_attributed = sum(attribution_data.revenue_attribution.values())
        if total_attributed > 0:
            click.echo("💰 REVENUE ATTRIBUTION")
            click.echo("-" * 50)
            for channel, revenue_cents in attribution_data.revenue_attribution.items():
                revenue = revenue_cents / 100
                percentage = (revenue_cents / total_attributed) * 100
                click.echo(
                    f"  {channel.replace('_', ' ').title()}: ${revenue:,.2f} ({percentage:.1f}%)"
                )

    except Exception as e:
        logger.error(f"Failed to analyze attribution: {e}")
        click.echo(f"Error: {e}", err=True)


@purchase.command()
def alerts():
    """Display current purchase monitoring alerts."""
    try:
        alert_status = alert_manager.get_alert_status()

        click.echo("=" * 50)
        click.echo("PURCHASE MONITORING ALERTS")
        click.echo("=" * 50)

        active_count = alert_status.get("active_alerts_count", 0)
        total_rules = alert_status.get("total_rules", 0)
        enabled_rules = alert_status.get("enabled_rules", 0)

        click.echo(f"Active Alerts: {active_count}")
        click.echo(f"Alert Rules: {enabled_rules}/{total_rules} enabled")
        click.echo(
            f"Notification Channels: {alert_status.get('notification_channels', 0)}"
        )
        click.echo(f"Recent Alerts (24h): {alert_status.get('recent_alerts_24h', 0)}")
        click.echo()

        # Display active alerts
        active_alerts = alert_status.get("active_alerts", [])
        if active_alerts:
            click.echo("🚨 ACTIVE ALERTS")
            click.echo("-" * 30)
            for alert in active_alerts:
                severity = alert["severity"].upper()
                severity_icon = (
                    "🔴"
                    if severity == "CRITICAL"
                    else (
                        "🟡"
                        if severity == "HIGH"
                        else "🟠" if severity == "MEDIUM" else "🔵"
                    )
                )

                click.echo(f"{severity_icon} {alert['rule_name']} ({severity})")
                click.echo(f"   {alert['message']}")
                click.echo(f"   Triggered: {alert['timestamp']}")
                click.echo()
        else:
            click.echo("✅ No active alerts")

    except Exception as e:
        logger.error(f"Failed to get alert status: {e}")
        click.echo(f"Error: {e}", err=True)


@purchase.command()
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host to bind dashboard server (default: 0.0.0.0)",
)
@click.option(
    "--port",
    type=int,
    default=5000,
    help="Port to bind dashboard server (default: 5000)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode",
)
def dashboard(host: str, port: int, debug: bool):
    """Start the web-based purchase metrics dashboard."""
    try:
        click.echo(f"Starting purchase metrics dashboard...")
        click.echo(f"Dashboard will be available at: http://{host}:{port}")
        click.echo("Press Ctrl+C to stop the server")

        run_dashboard(host, port, debug)

    except KeyboardInterrupt:
        click.echo("\nDashboard server stopped")
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
        click.echo(f"Error: {e}", err=True)


@purchase.command()
def status():
    """Display monitoring system status."""
    try:
        monitoring_status = purchase_monitor.get_monitoring_status()

        click.echo("=" * 50)
        click.echo("MONITORING SYSTEM STATUS")
        click.echo("=" * 50)

        is_running = monitoring_status.get("is_running", False)
        status_icon = "🟢" if is_running else "🔴"
        status_text = "RUNNING" if is_running else "STOPPED"

        click.echo(f"Status: {status_icon} {status_text}")

        last_update = monitoring_status.get("last_update")
        if last_update:
            click.echo(f"Last Update: {last_update}")

        click.echo(
            f"Update Interval: {monitoring_status.get('update_interval_seconds', 0)} seconds"
        )
        click.echo(
            f"Realtime Alerts: {'Enabled' if monitoring_status.get('realtime_alerts_enabled') else 'Disabled'}"
        )
        click.echo()

        # Alert manager status
        alert_status = monitoring_status.get("alert_manager_status", {})
        if alert_status:
            click.echo("Alert Manager:")
            click.echo(f"  Active Alerts: {alert_status.get('active_alerts_count', 0)}")
            click.echo(
                f"  Alert Rules: {alert_status.get('enabled_rules', 0)}/{alert_status.get('total_rules', 0)}"
            )

        # Metrics summary
        metrics_summary = monitoring_status.get("metrics_summary", {})
        if metrics_summary:
            click.echo("\nMetrics Storage:")
            click.echo(
                f"  Raw Metrics: {metrics_summary.get('raw_metrics_count', 0):,}"
            )
            click.echo(
                f"  Aggregated Metrics: {metrics_summary.get('aggregated_metrics_count', 0):,}"
            )
            click.echo(
                f"  Conversion Events: {metrics_summary.get('conversion_events_count', 0):,}"
            )

    except Exception as e:
        logger.error(f"Failed to get monitoring status: {e}")
        click.echo(f"Error: {e}", err=True)


if __name__ == "__main__":
    purchase()
