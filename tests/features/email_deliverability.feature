Feature: Email Deliverability Hardening
  As a Lead Factory system administrator
  I want to ensure email deliverability is optimized
  So that our marketing emails reach recipients effectively

  Background:
    Given the bounce rate is 0.01
    And the spam complaint rate is 0.0005

  Scenario: Check bounce rate is below threshold
    When I check the bounce rate
    Then the bounce rate should be 0.01

  Scenario: Check spam complaint rate is below threshold
    When I check the spam complaint rate
    Then the spam complaint rate should be 0.0005

  Scenario: Block sending when bounce rate exceeds threshold
    Given the bounce rate is 0.03
    When I attempt to send an email
    Then the email should not be sent

  Scenario: Block sending when spam complaint rate exceeds threshold
    Given the spam complaint rate is 0.002
    When I attempt to send an email
    Then the email should not be sent

  Scenario: Switch to alternative IP pool when primary has high bounce rate
    Given the IP pool "primary" has a bounce rate of 0.03
    And the IP pool "secondary" has a bounce rate of 0.01
    When I check the bounce rate for IP pool "primary"
    Then the bounce rate for IP pool "primary" should be 0.03
    When I check the bounce rate for IP pool "secondary"
    Then the bounce rate for IP pool "secondary" should be 0.01

  Scenario: Switch to alternative subuser when primary has high bounce rate
    Given the subuser "primary" has a bounce rate of 0.03
    And the subuser "secondary" has a bounce rate of 0.01
    When I check the bounce rate for subuser "primary"
    Then the bounce rate for subuser "primary" should be 0.03
    When I check the bounce rate for subuser "secondary"
    Then the bounce rate for subuser "secondary" should be 0.01

  Scenario: Successfully send email when metrics are below thresholds
    Given the bounce rate is 0.01
    And the spam complaint rate is 0.0005
    When I attempt to send an email
    Then the email should be sent successfully
