"""
CLI commands for managing node capabilities in the LeadFactory pipeline.

This module provides command-line interface for inspecting and configuring
node capabilities, replacing the legacy MOCKUP_ENABLED flag with a more
flexible capability management system.
"""

import json
from typing import Optional

import click
from tabulate import tabulate

from leadfactory.config.node_config import (
    NodeType,
    estimate_node_cost,
    get_capability_registry,
    get_capability_status,
    get_enabled_capabilities,
    get_node_capability_summary,
    set_capability_override,
)


@click.group()
def capabilities():
    """Manage node capabilities for pipeline configuration."""
    pass


@capabilities.command("list")
@click.option(
    "--node-type",
    type=click.Choice([nt.value for nt in NodeType]),
    help="Filter by specific node type",
)
@click.option("--format", type=click.Choice(["table", "json"]), default="table")
def list_capabilities(node_type: Optional[str], format: str):
    """List all node capabilities and their current status."""
    if node_type:
        node_types = [NodeType(node_type)]
    else:
        node_types = [nt for nt in NodeType]

    if format == "json":
        result = {}
        for nt in node_types:
            summary = get_node_capability_summary(nt)
            # Convert any non-serializable objects to dict
            json_summary = {}
            for key, value in summary.items():
                if hasattr(value, "__dict__"):
                    json_summary[key] = value.__dict__
                elif isinstance(value, list):
                    json_summary[key] = [
                        item.__dict__ if hasattr(item, "__dict__") else item
                        for item in value
                    ]
                else:
                    json_summary[key] = value
            result[nt.value] = json_summary
        click.echo(json.dumps(result, indent=2, default=str))
        return

    # Table format
    for nt in node_types:
        summary = get_node_capability_summary(nt)
        click.echo(f"\n {summary['node_name']} ({nt.value})")
        click.echo(
            f"   Capabilities: {summary['enabled_capabilities']}/{summary['total_capabilities']} enabled"
        )
        click.echo(f"   Estimated cost: {summary['estimated_cost_cents']:.1f} cents")

        if summary["capabilities"]:
            headers = ["Capability", "Status", "Cost", "APIs", "Override"]
            rows = []
            for cap in summary["capabilities"]:
                status = "✅ Enabled" if cap["final_enabled"] else "❌ Disabled"
                cost = f"{cap['cost_estimate_cents']:.1f}¢"
                apis = (
                    ", ".join(cap["required_apis"]) if cap["required_apis"] else "None"
                )
                override = ""
                if cap.get("override") and cap["override"]["active"]:
                    override = f"🔧 {cap['override']['reason']}"

                rows.append([cap["name"], status, cost, apis, override])

            click.echo(tabulate(rows, headers=headers, tablefmt="grid"))


@capabilities.command()
@click.argument("node_type", type=click.Choice([nt.value for nt in NodeType]))
@click.argument("capability_name")
def status(node_type: str, capability_name: str):
    """Get detailed status for a specific capability."""
    nt = NodeType(node_type)
    status_info = get_capability_status(nt, capability_name)

    if not status_info["exists"]:
        click.echo(f" {status_info['error']}", err=True)
        return

    click.echo(f" Capability: {status_info['name']}")
    click.echo(f"   Description: {status_info['description']}")
    click.echo(
        f"   Default: {'Enabled' if status_info['enabled_by_default'] else 'Disabled'}"
    )
    click.echo(f"   Cost: {status_info['cost_estimate_cents']:.1f} cents")
    click.echo(f"   Priority: {status_info['priority']}")
    click.echo(
        f"   Final Status: {'✅ Enabled' if status_info['final_enabled'] else '❌ Disabled'}"
    )

    if status_info["required_apis"]:
        click.echo(f"\n Required APIs:")
        for api_name in status_info["required_apis"]:
            api_status = status_info["apis_status"][api_name]
            status_icon = "✅" if api_status["available"] else "❌"
            click.echo(f"   {status_icon} {api_name}")

    if status_info.get("override"):
        override = status_info["override"]
        if override["active"]:
            click.echo(f"\n Override Active:")
            click.echo(f"   Enabled: {override['enabled']}")
            click.echo(f"   Reason: {override['reason']}")


@capabilities.command()
@click.argument("node_type", type=click.Choice([nt.value for nt in NodeType]))
@click.argument("capability_name")
@click.argument("enabled", type=bool)
@click.option("--reason", default="Manual override via CLI")
def override(node_type: str, capability_name: str, enabled: bool, reason: str):
    """Set a capability override for a specific node type."""
    nt = NodeType(node_type)
    success = set_capability_override(nt, capability_name, enabled, reason)

    if success:
        status_icon = "✅" if enabled else "❌"
        click.echo(f"{status_icon} Override set for {node_type}.{capability_name}")
        click.echo(f"   Enabled: {enabled}")
        click.echo(f"   Reason: {reason}")
    else:
        click.echo(
            f" Failed to set override. Capability '{capability_name}' not found for node type '{node_type}'",
            err=True,
        )


@capabilities.command()
@click.option(
    "--node-type",
    type=click.Choice([nt.value for nt in NodeType]),
    help="Filter by specific node type",
)
@click.option("--budget", type=float, help="Available budget in cents")
def estimate(node_type: Optional[str], budget: Optional[float]):
    """Estimate costs for enabled capabilities."""
    if node_type:
        node_types = [NodeType(node_type)]
    else:
        node_types = [nt for nt in NodeType]

    total_cost = 0
    for nt in node_types:
        cost = estimate_node_cost(nt, budget)
        total_cost += cost

        enabled_caps = get_enabled_capabilities(nt, budget)
        click.echo(f" {nt.value}: {cost:.1f} cents ({len(enabled_caps)} capabilities)")

    if len(node_types) > 1:
        click.echo(f"\n Total estimated cost: {total_cost:.1f} cents")


@capabilities.command()
def migrate():
    """Migrate from legacy MOCKUP_ENABLED flag to capability system."""
    import os

    mockup_enabled = os.getenv("MOCKUP_ENABLED", "").lower()
    tier = os.getenv("TIER", "")

    click.echo(" Migrating from legacy configuration...")

    if mockup_enabled:
        click.echo(f"   Found MOCKUP_ENABLED={mockup_enabled}")
        enabled = mockup_enabled == "true"
        set_capability_override(
            NodeType.FINAL_OUTPUT,
            "mockup_generation",
            enabled,
            f"Migrated from MOCKUP_ENABLED={mockup_enabled}",
        )
        click.echo(f"   Set mockup_generation to {enabled}")

    if tier:
        click.echo(f"   Found TIER={tier}")
        if tier == "1":
            # Disable expensive capabilities for Tier 1
            set_capability_override(
                NodeType.FINAL_OUTPUT,
                "mockup_generation",
                False,
                f"Migrated from TIER={tier} (cost optimization)",
            )
            set_capability_override(
                NodeType.ENRICH,
                "semrush_site_audit",
                False,
                f"Migrated from TIER={tier} (cost optimization)",
            )
            click.echo(f"   Disabled expensive capabilities for Tier 1")
        elif tier in ("2", "3"):
            # Enable all capabilities for Tier 2/3
            set_capability_override(
                NodeType.FINAL_OUTPUT,
                "mockup_generation",
                True,
                f"Migrated from TIER={tier} (full feature set)",
            )
            click.echo(f"   Enabled full capabilities for Tier {tier}")

    if not mockup_enabled and not tier:
        click.echo("   No legacy configuration found")

    click.echo("\n Migration complete!")
    click.echo(" Use 'leadfactory capabilities list' to see current configuration")


if __name__ == "__main__":
    capabilities()
