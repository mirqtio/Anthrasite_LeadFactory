"""Administrative command implementations"""

from typing import Optional

import click


@click.command()
@click.option("--reset", is_flag=True, help="Reset database before setup")
@click.option("--test-data", is_flag=True, help="Load test data after setup")
@click.pass_context
def db_setup(ctx, reset: bool, test_data: bool):
    """Setup database schema and initial data"""
    click.echo("Setting up database")
    if reset:
        click.echo("Reset flag enabled")
    if test_data:
        click.echo("Test data will be loaded")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would execute database setup")
        return

    # Import and execute database setup logic
    try:
        from leadfactory.utils.db_setup import main as db_setup_main

        db_setup_main(reset=reset, test_data=test_data)
    except ImportError:
        click.echo("Warning: Database setup module not found")


@click.command()
@click.option("--target", help="Target migration version")
@click.option("--rollback", is_flag=True, help="Rollback last migration")
@click.pass_context
def migrate(ctx, target: Optional[str], rollback: bool):
    """Run database migrations"""
    click.echo("Running database migrations")
    if target:
        click.echo(f"Target version: {target}")
    if rollback:
        click.echo("Rollback mode enabled")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would execute migrations")
        return

    # Import and execute migration logic
    try:
        from leadfactory.utils.migrations import main as migrate_main

        migrate_main(target=target, rollback=rollback)
    except ImportError:
        click.echo("Warning: Migration module not found")


# Import the new backup commands
from .backup_commands import backup
