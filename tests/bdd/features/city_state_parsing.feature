Feature: City and State Parsing
  As a LeadFactory user
  I want business addresses to have city and state parsed
  So that I can filter and query businesses by location

  Background:
    Given the LeadFactory pipeline is configured

  Scenario: Parse city and state from Yelp business address
    Given a Yelp business with display address "123 Main St, San Francisco, CA 94102"
    When the business is processed through the scraping pipeline
    Then the business should have city "San Francisco"
    And the business should have state "CA"

  Scenario: Parse city and state from Google Places address
    Given a Google Place with formatted address "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA"
    When the place is processed through the scraping pipeline
    Then the business should have city "Mountain View"
    And the business should have state "CA"

  Scenario: Parse addresses with full state names
    Given a business address "456 Oak Ave, Los Angeles, California 90028"
    When the address is parsed
    Then the city should be "Los Angeles"
    And the state should be "CA"

  Scenario: Parse addresses without comma before state
    Given a business address "789 Pine Rd, Chicago IL 60601"
    When the address is parsed
    Then the city should be "Chicago"
    And the state should be "IL"

  Scenario: Handle empty addresses gracefully
    Given a business with no address information
    When the business is processed
    Then the business should have empty city
    And the business should have empty state

  Scenario Outline: Parse various address formats
    Given a business address "<address>"
    When the address is parsed
    Then the city should be "<expected_city>"
    And the state should be "<expected_state>"

    Examples:
      | address                                              | expected_city    | expected_state |
      | 350 5th Ave, New York, NY 10118                    | New York         | NY             |
      | 100 Universal City Plaza, Universal City, CA 91608 | Universal City   | CA             |
      | 1 Microsoft Way, Redmond, WA 98052                 | Redmond          | WA             |
      | 233 S Wacker Dr, Chicago, IL 60606                 | Chicago          | IL             |
      | 456 Main St, Winston-Salem, NC 27101               | Winston-Salem    | NC             |
      | 123 Main St, Manchester, New Hampshire 03101       | Manchester       | NH             |
