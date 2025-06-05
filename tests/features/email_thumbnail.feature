Feature: Email Thumbnail Embedding
  As a sales team member
  I want to embed website thumbnails in outreach emails
  So that recipients can see their current website alongside our mockup

  Background:
    Given the email system is configured
    And I have a business with both screenshot and mockup assets

  Scenario: Send email with website thumbnail
    When I send an email to the business
    Then the email should contain two inline images:
      | content_id              | description          |
      | website-thumbnail.png   | Current website      |
      | website-mockup.png      | Proposed design      |
    And the HTML content should reference both images

  Scenario: Send email without screenshot
    Given the business has no screenshot asset
    But the business has a mockup asset
    When I send an email to the business
    Then the email should be sent successfully
    And the email should contain only the mockup image
    And no thumbnail reference should appear in the HTML

  Scenario: Thumbnail appears before mockup
    When I generate email content for a business
    Then the thumbnail section should appear before the mockup section
    And the thumbnail should have a "Current Website:" label
    And the mockup should have a "how your website could look:" label

  Scenario: Thumbnail file is missing
    Given the business has a screenshot asset record
    But the screenshot file doesn't exist on disk
    When I send an email to the business
    Then the email should still be sent successfully
    And only the mockup should be embedded
    And a warning should be logged about the missing screenshot

  Scenario: Both attachments are inline
    When I send an email with both thumbnail and mockup
    Then both attachments should have disposition "inline"
    And both should have unique content IDs
    And both should be base64 encoded

  Scenario: Email template styling
    When I view the email HTML
    Then the thumbnail should have:
      | property    | value     |
      | max-width   | 300px     |
      | border      | 1px solid |
      | shadow      | present   |
    And the mockup should be larger than the thumbnail

  Scenario: Dry run mode
    When I send an email in dry-run mode
    Then no actual email should be sent
    But the email record should be saved
    And attachment preparation should be skipped

  Scenario: Email with custom template
    Given I have a custom email template with thumbnail placeholder
    When I send an email using the custom template
    Then the thumbnail should be embedded at the placeholder location
    And the content ID should match the template reference