Feature: IP/Subuser Rotation for Bounce Rate Management
  As a system administrator
  I want the system to automatically rotate IP addresses when bounce rates are high
  So that email deliverability is maintained and sender reputation is protected

  Background:
    Given the IP rotation system is initialized
    And the following IP/subuser combinations are configured:
      | IP           | Subuser   | Priority |
      | 192.168.1.1  | primary   | 1        |
      | 192.168.1.2  | secondary | 2        |
      | 192.168.1.3  | tertiary  | 3        |

  Scenario: Automatic rotation when bounce rate exceeds threshold
    Given the IP "192.168.1.1" with subuser "primary" has sent 100 emails
    And the IP "192.168.1.1" with subuser "primary" has 15 bounces
    When the bounce rate threshold check is performed
    Then the bounce rate should be 0.15
    And a threshold breach should be detected
    When IP rotation is triggered for high bounce rate
    Then the IP should be rotated from "192.168.1.1" to "192.168.1.2"
    And the original IP "192.168.1.1" should be in cooldown status
    And the rotation reason should be "HIGH_BOUNCE_RATE"

  Scenario: Priority-based IP selection during rotation
    Given the IP "192.168.1.1" with subuser "primary" is disabled
    When the next available IP is requested
    Then the IP "192.168.1.2" with subuser "secondary" should be selected
    And the selected IP should have priority 2

  Scenario: No rotation when no alternatives are available
    Given all IPs except "192.168.1.1" are disabled
    When IP rotation is attempted for "192.168.1.1"
    Then the rotation should fail
    And the IP "192.168.1.1" should remain active
    And no rotation history should be recorded

  Scenario: Cooldown period prevents immediate reuse
    Given the IP "192.168.1.1" has been rotated and is in cooldown
    When checking for available IPs
    Then the IP "192.168.1.1" should not be available
    And only non-cooldown IPs should be returned

  Scenario: Rate limiting prevents excessive rotations
    Given the rotation rate limit is set to 2 per hour
    When 5 rotation attempts are made within an hour
    Then only 2 rotations should succeed
    And subsequent rotation attempts should be blocked

  Scenario: Bounce rate monitoring integration
    Given the bounce monitoring system is active
    When emails are sent through IP "192.168.1.1"
    And bounce events are recorded for that IP
    Then the bounce rate should be calculated correctly
    And threshold detection should work with real bounce data

  Scenario: Threshold configuration flexibility
    Given custom threshold rules are configured:
      | Name     | Bounce Rate | Min Volume | Severity |
      | warning  | 0.05        | 10         | WARNING  |
      | critical | 0.10        | 10         | CRITICAL |
    When the bounce rate reaches 0.06 with 20 emails
    Then a WARNING threshold breach should be detected
    When the bounce rate reaches 0.12 with 25 emails
    Then a CRITICAL threshold breach should be detected

  Scenario: Statistics and monitoring
    Given some rotation activity has occurred
    When rotation statistics are requested
    Then the total rotation count should be accurate
    And the count of active IPs should be correct
    And the count of cooldown IPs should be correct
    And the count of disabled IPs should be correct

  Scenario: Manual rotation capability
    Given the IP "192.168.1.1" is active
    When a manual rotation is requested
    Then the IP should be rotated to the next available IP
    And the rotation reason should be "MANUAL_ROTATION"
    And the rotation should be recorded in history

  Scenario: Cooldown expiration and IP reactivation
    Given the IP "192.168.1.1" was put in cooldown 2 hours ago
    And the cooldown period is 1 hour
    When checking IP availability
    Then the IP "192.168.1.1" should be available again
    And the IP status should be ACTIVE
