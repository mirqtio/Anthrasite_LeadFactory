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


if __name__ == "__main__":
    purchase()
