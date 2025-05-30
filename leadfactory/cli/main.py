#!/usr/bin/env python3
"""
Anthrasite Lead Factory CLI
Main entry point for all pipeline operations.
"""

import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()


@click.group()
@click.version_option()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--dry-run", is_flag=True, help="Run without making changes")
@click.pass_context
def cli(ctx, verbose, dry_run):
    """
    Anthrasite Lead Factory CLI

    Modern command-line interface for lead generation pipeline operations.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Store global options in context
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run

    # Setup logging based on verbosity
    import logging

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


@cli.group()
def pipeline():
    """Pipeline operations for lead generation"""
    pass


@cli.group()
def admin():
    """Administrative operations"""
    pass


@cli.group()
def dev():
    """Development and testing operations"""
    pass


# Import command modules
from .commands import admin_commands, dev_commands, pipeline_commands

# Register command groups
pipeline.add_command(pipeline_commands.scrape)
pipeline.add_command(pipeline_commands.enrich)
pipeline.add_command(pipeline_commands.dedupe)
pipeline.add_command(pipeline_commands.email)
pipeline.add_command(pipeline_commands.score)
pipeline.add_command(pipeline_commands.mockup)

admin.add_command(admin_commands.db_setup)
admin.add_command(admin_commands.migrate)
admin.add_command(admin_commands.backup)

dev.add_command(dev_commands.test)
dev.add_command(dev_commands.lint)
dev.add_command(dev_commands.format_code)


if __name__ == "__main__":
    cli()
