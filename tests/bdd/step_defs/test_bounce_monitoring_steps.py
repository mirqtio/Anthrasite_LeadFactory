"""
Step definitions for bounce monitoring BDD tests.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from leadfactory.email.sendgrid_warmup import WarmupStatus
from leadfactory.monitoring.bounce_rate_monitor import AutomatedBounceMonitor
from leadfactory.services.bounce_monitor import BounceEvent

# Load scenarios
scenarios('../features/bounce_monitoring.feature')


@pytest.fixture
def monitoring_context():
    """Context for monitoring tests."""
    return {
        'services': {},
        'monitor': None,
        'alerts': [],
        'stats': {}
    }


@given('the bounce monitoring service is configured')
def configure_monitoring(monitoring_context):
    """Configure monitoring service."""
    from leadfactory.services.bounce_monitor import BounceRateConfig, BounceRateMonitor
    
    config = BounceRateConfig(
        minimum_sample_size=10,
        warning_threshold=0.05,
        critical_threshold=0.10,
        block_threshold=0.15
    )
    monitoring_context['services']['bounce_monitor'] = BounceRateMonitor(
        config=config,
        db_path=":memory:"
    )


@given('the IP warmup service is running')
def configure_warmup(monitoring_context):
    """Configure warmup service."""
    from leadfactory.email.sendgrid_warmup import SendGridWarmupScheduler
    
    monitoring_context['services']['warmup_scheduler'] = SendGridWarmupScheduler(
        db_path=":memory:"
    )


@given('the IP rotation service is active')
def configure_rotation(monitoring_context):
    """Configure rotation service."""
    from leadfactory.services.ip_rotation import IPRotationService, RotationConfig
    
    config = RotationConfig()
    monitoring_context['services']['rotation_service'] = IPRotationService(
        config=config
    )
    
    # Create the monitor
    from leadfactory.email.sendgrid_warmup_integration import (
        SendGridWarmupIntegration,
        WarmupIntegrationConfig,
    )
    
    integration = SendGridWarmupIntegration(
        warmup_scheduler=monitoring_context['services']['warmup_scheduler'],
        bounce_monitor=monitoring_context['services']['bounce_monitor'],
        rotation_service=monitoring_context['services']['rotation_service'],
        config=WarmupIntegrationConfig()
    )
    
    monitor = AutomatedBounceMonitor(
        bounce_monitor=monitoring_context['services']['bounce_monitor'],
        warmup_scheduler=monitoring_context['services']['warmup_scheduler'],
        rotation_service=monitoring_context['services']['rotation_service'],
        warmup_integration=integration,
        check_interval_seconds=1
    )
    
    # Mock alert sending to capture alerts
    original_send_alert = monitor._send_alert
    async def mock_send_alert(severity, title, message):
        monitoring_context['alerts'].append({
            'severity': severity,
            'title': title,
            'message': message
        })
        await original_send_alert(severity, title, message)
    
    monitor._send_alert = mock_send_alert
    monitoring_context['monitor'] = monitor


@given(parsers.parse('IP "{ip}" is in warmup stage {stage:d}'))
def ip_in_warmup(monitoring_context, ip, stage):
    """Set IP in warmup stage."""
    scheduler = monitoring_context['services']['warmup_scheduler']
    scheduler.start_warmup(ip, f'warmup_{ip}')
    # Manually set stage
    with scheduler.db_connection() as db:
        db.execute(
            "UPDATE warmup_schedules SET current_stage = ? WHERE ip_address = ?",
            (stage, ip)
        )
        db.commit()


@given(parsers.parse('IP "{ip}" is in the production rotation pool'))
def ip_in_rotation(monitoring_context, ip):
    """Add IP to rotation pool."""
    rotation = monitoring_context['services']['rotation_service']
    rotation.add_ip_subuser(ip, f'user_{ip}')


@given(parsers.parse('IP "{ip}" has priority {priority:d}'))
def set_ip_priority(monitoring_context, ip, priority):
    """Set IP priority."""
    rotation = monitoring_context['services']['rotation_service']
    ip_pool_entry = rotation.get_ip_subuser_pool(ip, f'user_{ip}')
    if ip_pool_entry:
        ip_pool_entry.priority = priority


@given(parsers.parse('IP "{ip}" has sent {count:d} emails'))
def record_sends(monitoring_context, ip, count):
    """Record email sends."""
    bounce_monitor = monitoring_context['services']['bounce_monitor']
    subuser = f'user_{ip}' if 'warmup' not in ip else f'warmup_{ip}'
    
    for _ in range(count):
        bounce_monitor.record_send(ip, subuser)
        
    monitoring_context['stats'][ip] = {'sent': count, 'bounced': 0}


@given(parsers.parse('IP "{ip}" has sent {count:d} new emails'))
def record_new_sends(monitoring_context, ip, count):
    """Record additional email sends."""
    record_sends(monitoring_context, ip, count)


@given(parsers.parse('IP "{ip}" has an active bounce rate alert'))
def add_alert_history(monitoring_context, ip):
    """Add alert history for IP."""
    monitor = monitoring_context['monitor']
    monitor._alert_history[f'{ip}:user_{ip}'] = {
        'bounce_rate': 0.08,
        'timestamp': asyncio.get_event_loop().time()
    }


@when(parsers.parse('{count:d} emails bounce with type "{bounce_type}"'))
def record_bounces(monitoring_context, count, bounce_type):
    """Record email bounces."""
    bounce_monitor = monitoring_context['services']['bounce_monitor']
    
    # Find the last IP that had sends recorded
    last_ip = None
    for ip in monitoring_context['stats']:
        last_ip = ip
    
    if last_ip:
        subuser = f'user_{last_ip}' if 'warmup' not in last_ip else f'warmup_{last_ip}'
        
        for i in range(count):
            event = BounceEvent(
                email=f'test{i}@example.com',
                ip_address=last_ip,
                subuser=subuser,
                bounce_type=bounce_type,
                reason='Test bounce'
            )
            bounce_monitor.record_bounce(event)
            
        monitoring_context['stats'][last_ip]['bounced'] += count


@when(parsers.parse('only {count:d} emails bounce'))
def record_minimal_bounces(monitoring_context, count):
    """Record minimal bounces."""
    record_bounces(monitoring_context, count, 'soft')


@when('the monitoring service checks bounce rates')
def check_bounce_rates(monitoring_context):
    """Run bounce rate check."""
    monitor = monitoring_context['monitor']
    asyncio.run(monitor._check_bounce_rates())


@when(parsers.parse('the monitoring service is started with interval {interval:d} seconds'))
def start_monitoring(monitoring_context, interval):
    """Start monitoring service."""
    monitor = monitoring_context['monitor']
    monitor.check_interval = interval
    asyncio.run(monitor.start())


@when('the monitoring service is stopped')
def stop_monitoring(monitoring_context):
    """Stop monitoring service."""
    monitor = monitoring_context['monitor']
    asyncio.run(monitor.stop())


@then(parsers.parse('the bounce rate for IP "{ip}" should be {rate:d}%'))
def verify_bounce_rate(monitoring_context, ip, rate):
    """Verify bounce rate."""
    bounce_monitor = monitoring_context['services']['bounce_monitor']
    subuser = f'user_{ip}' if 'warmup' not in ip else f'warmup_{ip}'
    
    stats = bounce_monitor.get_bounce_rate(ip, subuser)
    assert stats is not None
    assert abs(stats.bounce_rate * 100 - rate) < 0.1


@then(parsers.parse('IP "{ip}" warmup should be "{status}"'))
def verify_warmup_status(monitoring_context, ip, status):
    """Verify warmup status."""
    scheduler = monitoring_context['services']['warmup_scheduler']
    warmup_status = scheduler.get_warmup_status(ip)
    
    assert warmup_status is not None
    if status == 'paused':
        assert warmup_status.status == WarmupStatus.PAUSED


@then(parsers.parse('an alert should be sent with severity "{severity}"'))
def verify_alert_sent(monitoring_context, severity):
    """Verify alert was sent."""
    alerts = monitoring_context['alerts']
    assert any(alert['severity'] == severity for alert in alerts)


@then(parsers.parse('IP "{ip}" should be marked as "{status}"'))
def verify_ip_status(monitoring_context, ip, status):
    """Verify IP status."""
    rotation = monitoring_context['services']['rotation_service']
    ip_pool_entry = rotation.get_ip_subuser_pool(ip, f'user_{ip}')
    
    assert ip_pool_entry is not None
    assert ip_pool_entry.status.value == status.lower()


@then(parsers.parse('IP "{ip}" should be removed from rotation'))
def verify_ip_removed(monitoring_context, ip):
    """Verify IP removed from rotation."""
    rotation = monitoring_context['services']['rotation_service']
    ip_pool_entry = rotation.get_ip_subuser_pool(ip, f'user_{ip}')
    
    # Check that IP is either not in pool or marked as disabled
    if ip_pool_entry:
        assert ip_pool_entry.status.value == 'disabled'


@then(parsers.parse('IP "{ip}" should have priority greater than {priority:d}'))
def verify_priority_lowered(monitoring_context, ip, priority):
    """Verify IP priority was lowered."""
    rotation = monitoring_context['services']['rotation_service']
    ip_pool_entry = rotation.get_ip_subuser_pool(ip, f'user_{ip}')
    
    assert ip_pool_entry is not None
    assert ip_pool_entry.priority > priority


@then(parsers.parse('IP "{ip}" should have no active alerts'))
def verify_no_alerts(monitoring_context, ip):
    """Verify no active alerts for IP."""
    monitor = monitoring_context['monitor']
    alert_key = f'{ip}:user_{ip}'
    assert alert_key not in monitor._alert_history


@then(parsers.parse('no alerts should be triggered for IP "{ip}"'))
def verify_no_alerts_triggered(monitoring_context, ip):
    """Verify no alerts were triggered."""
    alerts = monitoring_context['alerts']
    ip_alerts = [a for a in alerts if ip in a['message']]
    assert len(ip_alerts) == 0


@then(parsers.parse('IP "{ip}" should remain "{status}"'))
def verify_ip_remains_active(monitoring_context, ip, status):
    """Verify IP remains in status."""
    rotation = monitoring_context['services']['rotation_service']
    ip_pool_entry = rotation.get_ip_subuser_pool(ip, f'user_{ip}')
    
    assert ip_pool_entry is not None
    assert ip_pool_entry.status.value == status.lower()


@then(parsers.parse('the monitoring service should be "{status}"'))
def verify_monitoring_status(monitoring_context, status):
    """Verify monitoring service status."""
    monitor = monitoring_context['monitor']
    if status == 'running':
        assert monitor._running is True
    else:
        assert monitor._running is False


@then(parsers.parse('the monitoring service should check rates every {interval:d} seconds'))
def verify_check_interval(monitoring_context, interval):
    """Verify check interval."""
    monitor = monitoring_context['monitor']
    assert monitor.check_interval == interval