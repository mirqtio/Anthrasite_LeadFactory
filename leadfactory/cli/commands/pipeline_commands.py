"""Pipeline command implementations"""

from typing import Optional

import click


@click.command()
@click.option("--limit", default=50, help="Limit number of businesses to fetch per API")
@click.option("--zip-code", help="Process only the specified ZIP code")
@click.option("--vertical", help="Process only the specified vertical")
@click.pass_context
def scrape(ctx, limit: int, zip_code: Optional[str], vertical: Optional[str]):
    """Fetch business listings from Yelp Fusion and Google Places APIs"""
    click.echo(f"Scraping businesses (limit: {limit})")
    if zip_code:
        click.echo(f"ZIP code filter: {zip_code}")
    if vertical:
        click.echo(f"Vertical filter: {vertical}")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would execute scraping logic")
        return

    # Validate API keys before proceeding
    try:
        from leadfactory.pipeline.scrape import validate_api_keys

        is_valid, error_message = validate_api_keys()
        if not is_valid:
            click.echo(f"Error: {error_message}", err=True)
            return

    except ImportError:
        click.echo("Warning: Cannot validate API keys - scraping module not found")

    # Import and execute scraping logic
    try:
        from leadfactory.pipeline.scrape import main as scrape_main

        scrape_main(limit=limit, zip_code=zip_code, vertical=vertical)
    except ImportError:
        click.echo("Warning: Scraping module not found, using legacy bin/scrape.py")
        import subprocess
        import sys

        cmd = [sys.executable, "bin/scrape.py", "--limit", str(limit)]
        if zip_code:
            cmd.extend(["--zip", zip_code])
        if vertical:
            cmd.extend(["--vertical", vertical])
        subprocess.run(cmd)


@click.command()
@click.option("--limit", help="Limit number of businesses to process")
@click.option("--id", "business_id", help="Process only the specified business ID")
@click.option("--tier", type=click.Choice(["1", "2", "3"]), help="Override tier level")
@click.pass_context
def enrich(ctx, limit: Optional[int], business_id: Optional[str], tier: Optional[str]):
    """Analyze business websites to extract tech stack and performance metrics"""
    click.echo("Enriching business data")
    if limit:
        click.echo(f"Limit: {limit}")
    if business_id:
        click.echo(f"Business ID: {business_id}")
    if tier:
        click.echo(f"Tier: {tier}")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would execute enrichment logic")
        return

    # Import and execute enrichment logic
    try:
        from leadfactory.pipeline.enrich import main as enrich_main

        enrich_main(limit=limit, business_id=business_id, tier=tier)
    except ImportError:
        click.echo("Warning: Enrichment module not found, using legacy bin/enrich.py")
        import subprocess
        import sys

        cmd = [sys.executable, "bin/enrich.py"]
        if limit:
            cmd.extend(["--limit", str(limit)])
        if business_id:
            cmd.extend(["--id", business_id])
        if tier:
            cmd.extend(["--tier", tier])
        subprocess.run(cmd)


@click.command()
@click.option("--limit", help="Limit number of potential duplicates to process")
@click.option("--threshold", default=0.85, help="Levenshtein distance threshold")
@click.pass_context
def dedupe(ctx, limit: Optional[int], threshold: float):
    """Identify and merge duplicate business records"""
    click.echo(f"Deduplicating businesses (threshold: {threshold})")
    if limit:
        click.echo(f"Limit: {limit}")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would execute deduplication logic")
        return

    # Import and execute deduplication logic
    try:
        from leadfactory.pipeline.dedupe_unified import main as dedupe_main

        dedupe_main(limit=limit, threshold=threshold)
    except ImportError:
        click.echo(
            "Warning: Deduplication module not found, using legacy bin/dedupe.py"
        )
        import subprocess
        import sys

        cmd = [sys.executable, "bin/dedupe.py", "--threshold", str(threshold)]
        if limit:
            cmd.extend(["--limit", str(limit)])
        subprocess.run(cmd)


@click.command()
@click.option("--limit", help="Limit number of emails to send")
@click.option("--id", "business_id", help="Process only the specified business ID")
@click.option("--force", is_flag=True, help="Force sending emails even if already sent")
@click.pass_context
def email(ctx, limit: Optional[int], business_id: Optional[str], force: bool):
    """Send personalized emails via SendGrid with mockup attachments"""
    click.echo("Processing email queue")
    if limit:
        click.echo(f"Limit: {limit}")
    if business_id:
        click.echo(f"Business ID: {business_id}")
    if force:
        click.echo("Force sending enabled")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would execute email sending logic")
        return

    # Import and execute email logic
    try:
        from leadfactory.pipeline.email_queue import main as email_main

        email_main(limit=limit, business_id=business_id, force=force)
    except ImportError:
        click.echo("Warning: Email module not found, using legacy bin/email_queue.py")
        import subprocess
        import sys

        cmd = [sys.executable, "bin/email_queue.py"]
        if limit:
            cmd.extend(["--limit", str(limit)])
        if business_id:
            cmd.extend(["--id", business_id])
        if force:
            cmd.append("--force")
        subprocess.run(cmd)


@click.command()
@click.option("--limit", help="Limit number of businesses to process")
@click.option("--id", "business_id", help="Process only the specified business ID")
@click.option("--force", is_flag=True, help="Force processing even if already scored")
@click.pass_context
def score(ctx, limit: Optional[int], business_id: Optional[str], force: bool):
    """Score businesses based on configurable rules from scoring engine"""
    click.echo("Scoring businesses")
    if limit:
        click.echo(f"Limit: {limit}")
    if business_id:
        click.echo(f"Business ID: {business_id}")
    if force:
        click.echo("Force mode: ON")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would execute scoring logic")
        return

    # Import and execute scoring logic
    try:
        # Convert CLI args to argparse style
        import sys

        from leadfactory.pipeline.score import main as score_main

        sys.argv = ["score.py"]
        if limit:
            sys.argv.extend(["--limit", str(limit)])
        if business_id:
            sys.argv.extend(["--id", business_id])

        score_main()
    except ImportError:
        click.echo("Warning: Scoring module not found, using legacy bin/score.py")
        import subprocess
        import sys

        cmd = [sys.executable, "bin/score.py"]
        if limit:
            cmd.extend(["--limit", str(limit)])
        if business_id:
            cmd.extend(["--id", business_id])
        subprocess.run(cmd)


@click.command()
@click.option("--id", "business_id", help="Business ID to generate mockup for")
@click.option("--output", help="Output directory for mockups")
@click.option(
    "--tier",
    type=click.Choice(["1", "2", "3"]),
    help="Override tier level for mockup generation",
)
@click.pass_context
def mockup(ctx, business_id: Optional[str], output: Optional[str], tier: Optional[str]):
    """Generate AI-powered website mockups for businesses"""
    if not business_id:
        click.echo("Error: --id is required for mockup generation")
        ctx.exit(1)

    click.echo(f"Generating mockup for business ID: {business_id}")
    if output:
        click.echo(f"Output directory: {output}")
    if tier:
        click.echo(f"Tier override: {tier}")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would execute mockup generation")
        return

    # Import and execute mockup logic
    try:
        from leadfactory.pipeline.mockup import generate_business_mockup

        result = generate_business_mockup(int(business_id))
        if result:
            click.echo(f"Successfully generated mockup: {result}")
        else:
            click.echo("Failed to generate mockup")
            ctx.exit(1)
    except ImportError:
        click.echo("Warning: Mockup module not found, using legacy bin/mockup.py")
        import subprocess
        import sys

        cmd = [sys.executable, "bin/mockup.py", "--id", business_id]
        if output:
            cmd.extend(["--output", output])
        subprocess.run(cmd)
