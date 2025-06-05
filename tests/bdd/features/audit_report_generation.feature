Feature: Audit Report Generation
  As a customer who purchased an audit
  I want to receive a comprehensive website audit report
  So that I can understand my website's performance and get actionable recommendations

  Background:
    Given the audit report generation service is available
    And the business database contains test data
    And the LLM service is configured for analysis

  Scenario: Generate comprehensive audit report for business with full data
    Given a business "TechStart Solutions" exists with complete metrics data
    And the business has a PageSpeed score of 85
    And the business uses technologies "React, Node.js, PostgreSQL"
    And the business has 3 SEO errors and 5 SEO warnings
    When I request an audit report for "TechStart Solutions"
    And I provide customer email "client@techstart.com"
    And I provide report ID "audit-2024-001"
    Then a comprehensive PDF report should be generated
    And the report should contain business information
    And the report should contain technical analysis
    And the report should contain AI-generated findings
    And the report should contain actionable recommendations
    And the report file size should be greater than 50KB

  Scenario: Generate audit report with minimal business data
    Given a business "Minimal Corp" exists with basic information only
    And the business has no PageSpeed data
    And the business has no technology stack data
    When I request an audit report for "Minimal Corp"
    And I provide customer email "owner@minimal.com"
    And I provide report ID "audit-2024-002"
    Then a basic PDF report should be generated
    And the report should contain general recommendations
    And the report should acknowledge limited data availability
    And the report file size should be greater than 20KB

  Scenario: Generate audit report when business not found in database
    Given no business exists with name "Non-existent Company"
    When I request an audit report for "Non-existent Company"
    And I provide customer email "customer@example.com"
    And I provide report ID "audit-2024-003"
    Then a minimal PDF report should be generated
    And the report should contain standard audit recommendations
    And the report should indicate limited data availability
    And the report file size should be greater than 15KB

  Scenario: Generate audit report when LLM service fails
    Given a business "Stable Corp" exists with complete metrics data
    And the LLM service is unavailable
    When I request an audit report for "Stable Corp"
    And I provide customer email "admin@stable.com"
    And I provide report ID "audit-2024-004"
    Then a PDF report should be generated using fallback analysis
    And the report should contain rule-based findings
    And the report should contain technical metrics analysis
    And the report should contain general recommendations

  Scenario: Generate audit report with high-performance website
    Given a business "FastSite Inc" exists with complete metrics data
    And the business has a PageSpeed score of 98
    And the business has 0 SEO errors and 1 SEO warning
    When I request an audit report for "FastSite Inc"
    And I provide customer email "webmaster@fastsite.com"
    And I provide report ID "audit-2024-005"
    Then a comprehensive PDF report should be generated
    And the report should highlight excellent performance
    And the report should contain minimal optimization recommendations
    And the technical analysis should show "Excellent" assessments

  Scenario: Generate audit report with poor-performance website
    Given a business "SlowSite LLC" exists with complete metrics data
    And the business has a PageSpeed score of 45
    And the business has 8 SEO errors and 12 SEO warnings
    When I request an audit report for "SlowSite LLC"
    And I provide customer email "owner@slowsite.com"
    And I provide report ID "audit-2024-006"
    Then a comprehensive PDF report should be generated
    And the report should highlight performance issues
    And the report should contain priority optimization recommendations
    And the technical analysis should show "Needs Improvement" assessments

  Scenario: Generate multiple audit reports concurrently
    Given multiple businesses exist with various data completeness
    When I request audit reports for 3 different businesses simultaneously
    Then all 3 PDF reports should be generated successfully
    And each report should be unique and properly formatted
    And no data should be mixed between reports

  Scenario: Generate audit report and return as bytes
    Given a business "ByteTest Co" exists with complete metrics data
    When I request an audit report for "ByteTest Co" as bytes
    And I provide customer email "tech@bytetest.com"
    And I provide report ID "audit-2024-007"
    Then PDF content should be returned as bytes
    And the bytes should contain valid PDF headers
    And the bytes should represent a complete PDF document

  Scenario: Validate audit report content structure
    Given a business "StructureTest Inc" exists with complete metrics data
    When I request an audit report for "StructureTest Inc"
    And I provide customer email "qa@structuretest.com"
    And I provide report ID "audit-2024-008"
    Then the generated report should have the following sections:
      | Section Name           |
      | Executive Summary      |
      | Business Information   |
      | Technical Analysis     |
      | Key Findings          |
      | Priority Recommendations |
      | Overall Assessment     |
      | Analysis Methodology   |

  Scenario: Generate audit report with custom PDF configuration
    Given a business "Custom Corp" exists with complete metrics data
    And I configure the PDF with custom branding
    When I request an audit report for "Custom Corp"
    And I provide customer email "brand@custom.com"
    And I provide report ID "audit-2024-009"
    Then a branded PDF report should be generated
    And the report should contain custom company information
    And the report metadata should reflect the custom configuration