Feature: Automated Bounce Rate Monitoring
  As an email system administrator
  I want automated monitoring of bounce rates
  So that problematic IPs are automatically handled

  Background:
    Given the bounce monitoring service is configured
    And the IP warmup service is running
    And the IP rotation service is active

  Scenario: Monitor detects high bounce rate during warmup
    Given IP "192.168.1.1" is in warmup stage 2
    And IP "192.168.1.1" has sent 500 emails
    When 100 emails bounce with type "hard"
    And the monitoring service checks bounce rates
    Then the bounce rate for IP "192.168.1.1" should be 20%
    And IP "192.168.1.1" warmup should be "paused"
    And an alert should be sent with severity "critical"

  Scenario: Monitor removes production IP with excessive bounces
    Given IP "192.168.1.2" is in the production rotation pool
    And IP "192.168.1.2" has sent 1000 emails
    When 180 emails bounce with type "hard"
    And the monitoring service checks bounce rates
    Then the bounce rate for IP "192.168.1.2" should be 18%
    And IP "192.168.1.2" should be marked as "failed"
    And IP "192.168.1.2" should be removed from rotation

  Scenario: Monitor deprioritizes IP at critical threshold
    Given IP "192.168.1.3" is in the production rotation pool
    And IP "192.168.1.3" has priority 1
    And IP "192.168.1.3" has sent 1000 emails
    When 120 emails bounce with type "soft"
    And the monitoring service checks bounce rates
    Then the bounce rate for IP "192.168.1.3" should be 12%
    And IP "192.168.1.3" should have priority greater than 1

  Scenario: Monitor clears alerts for recovered IP
    Given IP "192.168.1.4" has an active bounce rate alert
    And IP "192.168.1.4" has sent 1000 new emails
    When only 20 emails bounce
    And the monitoring service checks bounce rates
    Then the bounce rate for IP "192.168.1.4" should be 2%
    And IP "192.168.1.4" should have no active alerts

  Scenario: Monitor ignores IP with insufficient samples
    Given IP "192.168.1.5" is in the production rotation pool
    And IP "192.168.1.5" has sent 5 emails
    When 3 emails bounce with type "hard"
    And the monitoring service checks bounce rates
    Then no alerts should be triggered for IP "192.168.1.5"
    And IP "192.168.1.5" should remain "active"

  Scenario: Monitoring service lifecycle
    When the monitoring service is started with interval 300 seconds
    Then the monitoring service should be "running"
    And the monitoring service should check rates every 300 seconds
    When the monitoring service is stopped
    Then the monitoring service should be "stopped"