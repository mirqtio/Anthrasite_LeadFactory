
Feature: Lead Scoring
  As a lead generation system
  I want to score leads based on various criteria
  So that I can prioritize high-value leads
  Scenario: Score a business based on tech stack
    Given a business with a modern tech stack
    When the scoring process runs
    Then the business should receive a high tech score
  Scenario: Score a business based on performance metrics
    Given a business with good performance metrics
    When the scoring process runs
    Then the business should receive a high performance score
  Scenario: Score a business based on location
    # Base (50) * 1.5 (healthcare) * 1.2 (multiple locations) = 90
    Given a business in a target location
    When the scoring process runs
    Then the business should receive a high location score
  Scenario: Handle missing data
    Given a business with incomplete data
    When the scoring process runs
    Then the business should receive default scores for missing data
  Scenario: Apply rule weights
    Given a business with mixed scores
    When the scoring process runs with rule weights
    Then the final score should reflect the weighted rules
