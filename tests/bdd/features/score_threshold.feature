Feature: Score Threshold Filtering
  As a business owner
  I want to filter out businesses with low audit potential scores
  So that I only send emails to high-value prospects

  Background:
    Given the scoring system is configured with an audit threshold of 60
    And the following businesses exist:
      | id | name                | email                  | website               |
      | 1  | Outdated Tech Corp  | contact@outdated.com   | http://outdated.com   |
      | 2  | Modern Digital Inc  | hello@modern.com       | http://modern.com     |
      | 3  | Average Business    | info@average.com       | http://average.com    |
      | 4  | No Website LLC      | contact@nowebsite.com  |                       |

  Scenario: Businesses are scored based on audit potential
    When the businesses are scored
    Then the scores should be:
      | business            | score | reason                                    |
      | Outdated Tech Corp  | 85    | Outdated technology, poor performance     |
      | Modern Digital Inc  | 35    | Modern tech stack, good performance       |
      | Average Business    | 65    | Some optimization opportunities           |
      | No Website LLC      | 10    | No website to audit                       |

  Scenario: Only high-score businesses receive emails
    Given the businesses have been scored as follows:
      | business            | score |
      | Outdated Tech Corp  | 85    |
      | Modern Digital Inc  | 35    |
      | Average Business    | 65    |
      | No Website LLC      | 10    |
    When emails are prepared for sending
    Then emails should be sent to:
      | business            | reason                           |
      | Outdated Tech Corp  | Score 85 exceeds threshold of 60 |
      | Average Business    | Score 65 exceeds threshold of 60 |
    And emails should NOT be sent to:
      | business            | reason                           |
      | Modern Digital Inc  | Score 35 below threshold of 60   |
      | No Website LLC      | Score 10 below threshold of 60   |

  Scenario: Custom audit threshold can be configured
    Given the audit threshold is changed to 70
    And the businesses have been scored as follows:
      | business            | score |
      | Outdated Tech Corp  | 85    |
      | Modern Digital Inc  | 35    |
      | Average Business    | 65    |
    When emails are prepared for sending
    Then only "Outdated Tech Corp" should receive an email
    And "Average Business" should be skipped with reason "Score 65 below threshold of 70"

  Scenario: Score threshold is logged for transparency
    Given the businesses have been scored
    When emails are prepared for sending
    Then the following should be logged:
      | message                                                        |
      | Skipping business 2 (Modern Digital Inc) with score 35 below audit threshold |
      | Skipping business 4 (No Website LLC) with score 10 below audit threshold     |

  Scenario: Businesses without scores are treated as zero
    Given a business "Unknown Score Inc" has no score recorded
    When emails are prepared for sending
    Then "Unknown Score Inc" should be skipped with reason "Score 0 below threshold of 60"

  Scenario: Score threshold prevents resource waste
    Given 100 businesses exist with the following score distribution:
      | score range | count |
      | 0-30        | 40    |
      | 31-60       | 30    |
      | 61-100      | 30    |
    When emails are prepared for sending
    Then exactly 30 emails should be queued
    And 70 businesses should be skipped due to low scores

  Scenario: Score data is preserved in database
    Given a business "Test Corp" is scored at 75
    When the score is saved to the database
    Then the stage_results table should contain:
      | business_id | stage | score |
      | 1           | score | 75    |
    And when emails are prepared, "Test Corp" should be included
