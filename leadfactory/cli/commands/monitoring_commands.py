"""
CLI commands for monitoring services.
"""

import asyncio
import json
import sys
from datetime import datetime

import click

from leadfactory.monitoring.bounce_rate_monitor import (
    get_automated_monitor,
    start_automated_monitoring,
    stop_automated_monitoring,
)
from leadfactory.services.bounce_monitor import BounceRateMonitor
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


@click.group()
def monitoring():
    """Monitoring management commands."""
    pass


@monitoring.command()
@click.option(
    '--interval',
    default=300,
    help='Check interval in seconds (default: 300)',
    type=int
)
@click.option(
    '--webhook-url',
    help='Webhook URL for alerts',
    type=str
)
@click.option(
    '--daemon',
    is_flag=True,
    help='Run as daemon process'
)
def start_bounce_monitor(interval: int, webhook_url: str, daemon: bool):
    """Start automated bounce rate monitoring."""
    async def run():
        try:
            monitor = await start_automated_monitoring(
                check_interval_seconds=interval,
                alert_webhook_url=webhook_url
            )
            
            logger.info(f"Started bounce rate monitoring (interval: {interval}s)")
            
            if daemon:
                # Keep running until interrupted
                try:
                    while True:
                        await asyncio.sleep(60)
                        status = monitor.get_monitoring_status()
                        logger.info(f"Monitor status: {status['active_alerts']} active alerts")
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal")
            else:
                # Just start and return
                click.echo(f"Bounce rate monitoring started (interval: {interval}s)")
                
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            sys.exit(1)
            
    asyncio.run(run())
    

@monitoring.command()
def stop_bounce_monitor():
    """Stop automated bounce rate monitoring."""
    async def run():
        try:
            await stop_automated_monitoring()
            click.echo("Bounce rate monitoring stopped")
        except Exception as e:
            logger.error(f"Failed to stop monitoring: {e}")
            sys.exit(1)
            
    asyncio.run(run())
    

@monitoring.command()
def bounce_monitor_status():
    """Check bounce rate monitoring status."""
    monitor = get_automated_monitor()
    
    if not monitor:
        click.echo("Bounce rate monitoring is not running")
        return
        
    status = monitor.get_monitoring_status()
    
    click.echo("Bounce Rate Monitoring Status")
    click.echo("=" * 40)
    click.echo(f"Running: {status['running']}")
    click.echo(f"Check Interval: {status['check_interval_seconds']}s")
    click.echo(f"Active Alerts: {status['active_alerts']}")
    
    if status['alert_history']:
        click.echo("\nRecent Alerts:")
        for alert in status['alert_history'][-10:]:  # Last 10 alerts
            click.echo(
                f"  - {alert['ip_subuser']}: {alert['bounce_rate']:.2%} "
                f"at {alert['timestamp']}"
            )
            

@monitoring.command()
@click.option(
    '--ip',
    help='IP address to check',
    type=str
)
@click.option(
    '--subuser',
    help='Subuser to check',
    type=str
)
def check_bounce_rate(ip: str, subuser: str):
    """Check bounce rate for specific IP/subuser."""
    from leadfactory.services.bounce_monitor import BounceRateMonitor, BounceRateConfig
    
    config = BounceRateConfig()
    monitor = BounceRateMonitor(config=config)
    
    if ip and subuser:
        # Check specific IP/subuser
        stats = monitor.get_bounce_rate(ip, subuser)
        if stats:
            click.echo(f"Bounce Rate for {ip}/{subuser}:")
            click.echo(f"  Total Sent: {stats.total_sent}")
            click.echo(f"  Total Bounced: {stats.total_bounced}")
            click.echo(f"  Bounce Rate: {stats.bounce_rate:.2%}")
            click.echo(f"  Status: {stats.status}")
            click.echo(f"  Last Updated: {stats.last_updated}")
        else:
            click.echo(f"No data found for {ip}/{subuser}")
    else:
        # Show all IPs with high bounce rates
        click.echo("IPs with elevated bounce rates:")
        click.echo("=" * 60)
        
        # This would need to be implemented in the bounce monitor
        # For now, we'll show a message
        click.echo("Use --ip and --subuser to check specific combinations")
        

@monitoring.command()
@click.option(
    '--days',
    default=7,
    help='Number of days to look back',
    type=int
)
def warmup_status(days: int):
    """Check IP warmup status."""
    from leadfactory.email.sendgrid_warmup import SendGridWarmupScheduler
    
    scheduler = SendGridWarmupScheduler()
    active_warmups = scheduler.get_active_warmup_ips()
    
    if not active_warmups:
        click.echo("No IPs currently in warmup")
        return
        
    click.echo(f"Active IP Warmups (last {days} days):")
    click.echo("=" * 80)
    
    for warmup in active_warmups:
        click.echo(f"\nIP: {warmup['ip_address']} (Subuser: {warmup['subuser']})")
        click.echo(f"  Status: {warmup['status']}")
        click.echo(f"  Stage: {warmup['stage']} ({warmup['daily_limit']:,} emails/day)")
        click.echo(f"  Progress: Day {warmup['current_day']} of warmup")
        click.echo(f"  Started: {warmup['started_date']}")
        
        if warmup.get('bounce_rate'):
            click.echo(f"  Current Bounce Rate: {warmup['bounce_rate']:.2%}")
            

@monitoring.command()
@click.option(
    '--format',
    type=click.Choice(['json', 'text']),
    default='text',
    help='Output format'
)
def monitoring_report(format: str):
    """Generate monitoring report."""
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'bounce_monitoring': {},
        'warmup_status': {},
        'rotation_pools': {}
    }
    
    # Check bounce monitoring
    monitor = get_automated_monitor()
    if monitor:
        report_data['bounce_monitoring'] = monitor.get_monitoring_status()
    else:
        report_data['bounce_monitoring'] = {'running': False}
        
    # Check warmup status
    try:
        from leadfactory.email.sendgrid_warmup import SendGridWarmupScheduler
        scheduler = SendGridWarmupScheduler()
        report_data['warmup_status'] = {
            'active_warmups': len(scheduler.get_active_warmup_ips()),
            'ips': scheduler.get_active_warmup_ips()
        }
    except Exception as e:
        report_data['warmup_status'] = {'error': str(e)}
        
    # Check rotation pools
    try:
        from leadfactory.services.ip_rotation import IPRotationService
        rotation_service = IPRotationService()
        pools = rotation_service.get_all_pools()
        report_data['rotation_pools'] = {
            'total_pools': len(pools),
            'active_ips': sum(len(p.pool) for p in pools if p.is_active)
        }
    except Exception as e:
        report_data['rotation_pools'] = {'error': str(e)}
        
    if format == 'json':
        click.echo(json.dumps(report_data, indent=2))
    else:
        click.echo("Email System Monitoring Report")
        click.echo("=" * 60)
        click.echo(f"Generated: {report_data['timestamp']}")
        click.echo()
        
        # Bounce monitoring
        bm = report_data['bounce_monitoring']
        click.echo("Bounce Rate Monitoring:")
        if bm.get('running'):
            click.echo(f"  Status: Running")
            click.echo(f"  Check Interval: {bm['check_interval_seconds']}s")
            click.echo(f"  Active Alerts: {bm['active_alerts']}")
        else:
            click.echo("  Status: Not Running")
            
        click.echo()
        
        # Warmup status
        ws = report_data['warmup_status']
        click.echo("IP Warmup Status:")
        if 'error' in ws:
            click.echo(f"  Error: {ws['error']}")
        else:
            click.echo(f"  Active Warmups: {ws['active_warmups']}")
            
        click.echo()
        
        # Rotation pools
        rp = report_data['rotation_pools']
        click.echo("IP Rotation Pools:")
        if 'error' in rp:
            click.echo(f"  Error: {rp['error']}")
        else:
            click.echo(f"  Total Pools: {rp['total_pools']}")
            click.echo(f"  Active IPs: {rp['active_ips']}")


def register_commands(cli):
    """Register monitoring commands with the main CLI."""
    cli.add_command(monitoring)