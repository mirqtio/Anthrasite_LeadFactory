Feature: AI Content Integration with Email Templates
  As a sales team member
  I want AI-generated content to be integrated with compliant email templates
  So that personalized emails maintain CAN-SPAM compliance

  Background:
    Given the email system is configured with AI content generation
    And I have a business with website audit data

  Scenario: Generate and send email with AI content
    Given the business is "Denver HVAC Pros" in the "hvac" vertical
    And the business has a low website score of 35
    When I request an email with AI-generated content
    Then the email should contain personalized AI introduction
    And the email should list AI-generated improvements specific to HVAC
    And the email should have an AI-generated call to action
    And the email should include all CAN-SPAM required elements

  Scenario: AI content respects template structure
    Given I have an email template with placeholders for AI content
    When AI content is generated for the business
    Then the AI introduction replaces the default introduction
    And the AI improvements replace the static improvement list
    And the AI call-to-action replaces the default CTA
    But the footer remains unchanged with compliance information

  Scenario: Fallback when AI generation fails
    Given the AI service is unavailable
    When I request an email with AI-generated content
    Then the email should use default content for the introduction
    And the email should use vertical-specific default improvements
    And the email should use a standard call to action
    And the email should still include all CAN-SPAM elements

  Scenario: AI content for different business verticals
    Given I have businesses in different verticals:
      | business_name     | vertical    | expected_keyword |
      | Joe's Plumbing    | plumber     | emergency       |
      | Spark Electric    | electrician | safety          |
      | Bella's Bistro    | restaurant  | reservation     |
      | Fashion Forward   | retail      | product         |
    When I generate AI content for each business
    Then each email should contain vertical-specific improvements
    And each improvement should mention the expected keyword

  Scenario: Score-based AI content prioritization
    Given the business has the following scores:
      | metric           | score |
      | performance      | 20    |
      | mobile           | 25    |
      | seo              | 70    |
      | technology       | 65    |
    When AI content is generated
    Then the first improvements should address performance issues
    And mobile optimization should be prominently mentioned
    And SEO improvements should have lower priority

  Scenario: CAN-SPAM compliance with long AI content
    Given the AI generates very long content:
      | content_type | length |
      | introduction | 500    |
      | improvements | 1000   |
      | cta          | 300    |
    When the email is rendered
    Then the physical address is still visible
    And the unsubscribe link is still accessible
    And the email reason explanation is present
    And the copyright notice is included

  Scenario: AI personalization with business location
    Given the business "Austin HVAC Services" is located in "Austin, TX"
    When AI content is generated
    Then the introduction should mention "Austin"
    And the content should reference local market conditions
    And location-specific opportunities should be highlighted

  Scenario: Email subject line generation with AI
    Given the business has standout improvements available
    When the email subject is generated
    Then it should include the business name
    And it should highlight the most impactful improvement
    And it should be under 60 characters for mobile compatibility

  Scenario: Multi-language AI content support
    Given the business prefers communication in "Spanish"
    When AI content is generated
    Then the improvements should be in Spanish
    But the CAN-SPAM footer remains in English for legal compliance
    And the unsubscribe link text is bilingual

  Scenario: A/B testing with AI variations
    Given an A/B test is running for email content
    When emails are generated for variant A and variant B
    Then variant A uses one style of AI-generated content
    And variant B uses a different style of AI-generated content
    But both variants maintain identical CAN-SPAM footers
    And both include tracking for performance measurement
