"""Development command implementations"""

from typing import Optional

import click


@click.command()
@click.option("--pattern", help="Test pattern to match")
@click.option("--verbose", "-v", is_flag=True, help="Verbose test output")
@click.option("--coverage", is_flag=True, help="Run with coverage report")
@click.pass_context
def test(ctx, pattern: Optional[str], verbose: bool, coverage: bool):
    """Run test suite"""
    click.echo("Running tests")
    if pattern:
        click.echo(f"Pattern: {pattern}")
    if verbose:
        click.echo("Verbose mode enabled")
    if coverage:
        click.echo("Coverage reporting enabled")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would run tests")
        return

    # Execute test logic
    import subprocess
    import sys

    cmd = [sys.executable, "-m", "pytest"]
    if pattern:
        cmd.extend(["-k", pattern])
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=leadfactory", "--cov-report=html"])

    subprocess.run(cmd)


@click.command()
@click.option("--fix", is_flag=True, help="Automatically fix linting issues")
@click.pass_context
def lint(ctx, fix: bool):
    """Run code linting"""
    click.echo("Running linting")
    if fix:
        click.echo("Auto-fix enabled")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would run linting")
        return

    # Execute linting logic
    import subprocess
    import sys

    # Run flake8
    subprocess.run([sys.executable, "-m", "flake8", "leadfactory/"])

    # Run ruff
    if fix:
        subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", "leadfactory/"])
    else:
        subprocess.run([sys.executable, "-m", "ruff", "check", "leadfactory/"])


@click.command("format")
@click.option("--check", is_flag=True, help="Check formatting without making changes")
@click.pass_context
def format_code(ctx, check: bool):
    """Format code with Black and isort"""
    click.echo("Formatting code")
    if check:
        click.echo("Check mode enabled")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would format code")
        return

    # Execute formatting logic
    import subprocess
    import sys

    # Run Black
    black_cmd = [sys.executable, "-m", "black"]
    if check:
        black_cmd.append("--check")
    black_cmd.append("leadfactory/")
    subprocess.run(black_cmd)

    # Run isort
    isort_cmd = [sys.executable, "-m", "isort"]
    if check:
        isort_cmd.append("--check-only")
    isort_cmd.append("leadfactory/")
    subprocess.run(isort_cmd)
