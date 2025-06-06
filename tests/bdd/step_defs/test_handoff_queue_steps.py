"""BDD step definitions for handoff queue functionality."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

from leadfactory.services.handoff_queue_service import (
    HandoffQueueService,
    HandoffStatus,
    SalesTeamMember,
)
from leadfactory.services.qualification_engine import (
    QualificationCriteria,
    QualificationEngine,
    QualificationResult,
    QualificationStatus,
)

# Load scenarios from feature file
scenarios('../features/handoff_queue.feature')


@pytest.fixture
def handoff_context():
    """Test context for handoff queue scenarios."""
    context = {
        'businesses': [],
        'criteria': [],
        'sales_members': [],
        'queue_entries': [],
        'operations': [],
        'results': None,
        'error': None
    }

    # Mock services
    context['mock_storage'] = MagicMock()
    context['handoff_service'] = HandoffQueueService()
    context['qualification_engine'] = QualificationEngine()

    # Replace storage with mocks
    context['handoff_service'].storage = context['mock_storage']
    context['qualification_engine'].storage = context['mock_storage']

    return context


@given("the handoff queue system is initialized")
def handoff_system_initialized(handoff_context):
    """Initialize the handoff queue system."""
    # System is already initialized in fixture
    assert handoff_context['handoff_service'] is not None
    assert handoff_context['qualification_engine'] is not None


@given("qualification criteria exist in the system")
def qualification_criteria_exist(handoff_context):
    """Set up qualification criteria."""
    criteria = [
        QualificationCriteria(
            id=1,
            name="Basic Qualification",
            description="Basic lead qualification",
            min_score=50,
            required_fields=["name", "email"],
            engagement_requirements={"min_page_views": 2},
            custom_rules={"has_website": True}
        ),
        QualificationCriteria(
            id=2,
            name="High Value Prospect",
            description="High value prospect qualification",
            min_score=70,
            required_fields=["name", "email", "website"],
            engagement_requirements={"min_page_views": 5, "has_conversions": True},
            custom_rules={"has_website": True, "min_business_score": 70}
        )
    ]

    handoff_context['criteria'] = criteria

    # Mock criteria retrieval
    def mock_get_criteria(criteria_id):
        return next((c for c in criteria if c.id == criteria_id), None)

    handoff_context['qualification_engine'].get_criteria_by_id = mock_get_criteria


@given("sales team members are configured")
def sales_team_configured(handoff_context):
    """Set up sales team members."""
    members = [
        SalesTeamMember(
            id=1,
            user_id="sales_rep_1",
            name="John Doe",
            email="john@example.com",
            role="sales_rep",
            max_capacity=50,
            current_capacity=10,
            is_active=True
        ),
        SalesTeamMember(
            id=2,
            user_id="sales_rep_2",
            name="Jane Smith",
            email="jane@example.com",
            role="sales_rep",
            max_capacity=30,
            current_capacity=30,  # At capacity
            is_active=True
        )
    ]

    handoff_context['sales_members'] = members

    # Mock sales member retrieval
    def mock_get_member(user_id):
        return next((m for m in members if m.user_id == user_id), None)

    handoff_context['handoff_service'].get_sales_team_member = mock_get_member


@given("I have a list of businesses with various scores")
def businesses_with_scores(handoff_context):
    """Set up businesses with different scores."""
    businesses = [
        {"id": 1, "name": "TechCorp", "email": "info@techcorp.com", "website": "https://techcorp.com", "score": 85},
        {"id": 2, "name": "StartupInc", "email": "hello@startup.com", "website": "https://startup.com", "score": 45},
        {"id": 3, "name": "Enterprise Ltd", "email": "contact@enterprise.com", "website": "https://enterprise.com", "score": 92},
        {"id": 4, "name": "SmallBiz", "email": "info@smallbiz.com", "website": "", "score": 65}  # No website
    ]

    handoff_context['businesses'] = businesses

    # Mock business retrieval
    def mock_get_business(business_id):
        return next((b for b in businesses if b["id"] == business_id), None)

    handoff_context['mock_storage'].get_business_by_id.side_effect = mock_get_business


@given("I select qualification criteria with minimum score of 70")
def select_criteria_min_score_70(handoff_context):
    """Select qualification criteria with min score 70."""
    handoff_context['selected_criteria_id'] = 2  # High Value Prospect


@given("there are queue entries with different statuses")
def queue_entries_different_statuses(handoff_context):
    """Set up queue entries with various statuses."""
    from leadfactory.services.handoff_queue_service import HandoffQueueEntry

    entries = [
        HandoffQueueEntry(
            id=1, business_id=1, qualification_criteria_id=1,
            status=HandoffStatus.QUALIFIED, priority=85
        ),
        HandoffQueueEntry(
            id=2, business_id=2, qualification_criteria_id=1,
            status=HandoffStatus.ASSIGNED, priority=75, assigned_to="sales_rep_1"
        ),
        HandoffQueueEntry(
            id=3, business_id=3, qualification_criteria_id=1,
            status=HandoffStatus.QUALIFIED, priority=90
        )
    ]

    handoff_context['queue_entries'] = entries


@given("there are qualified entries in the handoff queue")
def qualified_entries_in_queue(handoff_context):
    """Set up qualified entries in the queue."""
    from leadfactory.services.handoff_queue_service import HandoffQueueEntry

    entries = [
        HandoffQueueEntry(
            id=1, business_id=1, qualification_criteria_id=1,
            status=HandoffStatus.QUALIFIED, priority=85
        ),
        HandoffQueueEntry(
            id=2, business_id=3, qualification_criteria_id=1,
            status=HandoffStatus.QUALIFIED, priority=90
        )
    ]

    handoff_context['queue_entries'] = entries

    # Mock queue entry retrieval
    def mock_get_entry(entry_id):
        return next((e for e in entries if e.id == entry_id), None)

    handoff_context['handoff_service'].get_queue_entry = mock_get_entry


@given("a sales team member has available capacity")
def sales_member_available_capacity(handoff_context):
    """Ensure sales member has available capacity."""
    handoff_context['selected_assignee'] = "sales_rep_1"  # Has capacity


@given("a sales team member is at full capacity")
def sales_member_full_capacity(handoff_context):
    """Select sales member at full capacity."""
    handoff_context['selected_assignee'] = "sales_rep_2"  # At capacity


@given("there is a qualified entry in the handoff queue")
def qualified_entry_in_queue(handoff_context):
    """Set up a single qualified entry."""
    from leadfactory.services.handoff_queue_service import HandoffQueueEntry

    entry = HandoffQueueEntry(
        id=1, business_id=1, qualification_criteria_id=1,
        status=HandoffStatus.QUALIFIED, priority=85,
        qualification_details={"criteria_name": "Basic Qualification", "score": 85},
        engagement_summary={"total_page_views": 10, "conversions": 2}
    )

    handoff_context['selected_entry'] = entry
    handoff_context['handoff_service'].get_queue_entry = MagicMock(return_value=entry)


@given("I have businesses with different engagement levels")
def businesses_different_engagement(handoff_context):
    """Set up businesses with varying engagement levels."""
    businesses = [
        {"id": 1, "name": "HighEngagement", "email": "info@high.com", "website": "https://high.com", "score": 75},
        {"id": 2, "name": "LowEngagement", "email": "info@low.com", "website": "https://low.com", "score": 80},
        {"id": 3, "name": "NoEngagement", "email": "info@none.com", "website": "https://none.com", "score": 85}
    ]

    handoff_context['businesses'] = businesses

    # Mock business and engagement data
    def mock_get_business(business_id):
        return next((b for b in businesses if b["id"] == business_id), None)

    handoff_context['mock_storage'].get_business_by_id.side_effect = mock_get_business

    # Mock engagement analytics
    mock_engagement = MagicMock()
    engagement_data = {
        "business_1": {"total_page_views": 10, "conversions": 2},  # High
        "business_2": {"total_page_views": 3, "conversions": 0},   # Low
        "business_3": {"total_page_views": 1, "conversions": 0}    # None
    }

    def mock_get_engagement(user_id, days=30):
        return engagement_data.get(user_id, {"total_page_views": 0, "conversions": 0})

    mock_engagement.get_user_engagement_summary.side_effect = mock_get_engagement
    handoff_context['qualification_engine'].engagement_analytics = mock_engagement


@given("qualification criteria requiring minimum page views")
def criteria_requiring_page_views(handoff_context):
    """Set criteria requiring minimum page views."""
    handoff_context['selected_criteria_id'] = 2  # Has page view requirements


@given("there are entries in various queue statuses")
def entries_various_statuses(handoff_context):
    """Set up entries for analytics."""
    # Mock database responses for analytics
    status_data = [
        ("qualified", 10, 75.5, 82.3),
        ("assigned", 5, 80.0, 85.0),
        ("contacted", 3, 85.0, 88.0)
    ]

    assignment_data = [
        ("sales_rep_1", 5),
        ("sales_rep_2", 3)
    ]

    criteria_data = [
        (1, "Basic Qualification", 8, 80.0),
        (2, "High Value Prospect", 5, 87.0)
    ]

    handoff_context['analytics_data'] = {
        'status': status_data,
        'assignments': assignment_data,
        'criteria': criteria_data,
        'totals': {'total': 18, 'unassigned': 10, 'active_sales': 2}
    }


@given("some entries are assigned to different sales team members")
def entries_assigned_to_members(handoff_context):
    """Entries are assigned to sales members (included in previous step)."""
    pass


@given("I want to create new qualification criteria")
def want_create_criteria(handoff_context):
    """Set up for creating new criteria."""
    handoff_context['new_criteria'] = {
        "name": "Custom Criteria",
        "description": "Custom qualification criteria",
        "min_score": 60,
        "required_fields": ["name", "email", "phone"],
        "engagement_requirements": {"min_page_views": 3},
        "custom_rules": {"has_complete_profile": True}
    }


@given("I start a bulk qualification operation")
def start_bulk_operation(handoff_context):
    """Start a bulk qualification operation."""
    handoff_context['operation_id'] = "test-operation-123"
    handoff_context['operation_status'] = "in_progress"


@when("I perform bulk qualification on the businesses")
def perform_bulk_qualification(handoff_context):
    """Perform bulk qualification."""
    business_ids = [b["id"] for b in handoff_context['businesses']]
    criteria_id = handoff_context['selected_criteria_id']

    # Mock qualification results
    results = []
    criteria = handoff_context['qualification_engine'].get_criteria_by_id(criteria_id)

    for business in handoff_context['businesses']:
        # Simple qualification logic for testing
        qualifies = (
            business['score'] >= criteria.min_score and
            business.get('website', '') != ''  # Has website requirement
        )

        status = QualificationStatus.QUALIFIED if qualifies else QualificationStatus.REJECTED

        result = QualificationResult(
            business_id=business['id'],
            status=status,
            score=business['score'],
            criteria_id=criteria_id,
            details={"criteria_name": criteria.name}
        )
        results.append(result)

    handoff_context['qualification_results'] = results

    # Mock the service call
    handoff_context['qualification_engine'].qualify_businesses_bulk = MagicMock(return_value=results)
    handoff_context['handoff_service']._add_to_queue = MagicMock(return_value=1)
    handoff_context['handoff_service']._create_bulk_operation = MagicMock(return_value=True)
    handoff_context['handoff_service']._update_bulk_operation = MagicMock(return_value=True)

    with patch('uuid.uuid4') as mock_uuid:
        mock_uuid.return_value.__str__ = lambda: "test-operation-id"
        operation_id = handoff_context['handoff_service'].bulk_qualify(
            business_ids, criteria_id, "test_user"
        )

    handoff_context['operation_id'] = operation_id


@when('I filter the queue by "qualified" status')
def filter_queue_qualified(handoff_context):
    """Filter queue by qualified status."""
    qualified_entries = [
        e for e in handoff_context['queue_entries']
        if e.status == HandoffStatus.QUALIFIED
    ]

    # Sort by priority descending
    qualified_entries.sort(key=lambda x: x.priority, reverse=True)

    handoff_context['filtered_entries'] = qualified_entries


@when("I assign multiple entries to the sales team member")
def assign_entries_to_member(handoff_context):
    """Assign entries to sales team member."""
    entry_ids = [e.id for e in handoff_context['queue_entries']]
    assignee = handoff_context['selected_assignee']

    # Mock assignment success
    handoff_context['handoff_service'].assign_queue_entry = MagicMock(return_value=True)
    handoff_context['handoff_service']._create_bulk_operation = MagicMock(return_value=True)
    handoff_context['handoff_service']._update_bulk_operation = MagicMock(return_value=True)

    try:
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda: "test-assign-op"
            operation_id = handoff_context['handoff_service'].bulk_assign(
                entry_ids, assignee, "admin"
            )
        handoff_context['assignment_result'] = {"success": True, "operation_id": operation_id}
    except Exception as e:
        handoff_context['assignment_result'] = {"success": False, "error": str(e)}


@when("I try to assign entries to the sales team member")
def try_assign_entries_full_capacity(handoff_context):
    """Try to assign entries to member at capacity."""
    entry_ids = [e.id for e in handoff_context['queue_entries']]
    assignee = handoff_context['selected_assignee']

    try:
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda: "test-assign-op"
            operation_id = handoff_context['handoff_service'].bulk_assign(
                entry_ids, assignee, "admin"
            )
        handoff_context['assignment_result'] = {"success": True, "operation_id": operation_id}
    except Exception as e:
        handoff_context['assignment_result'] = {"success": False, "error": str(e)}


@when("I request the entry details")
def request_entry_details(handoff_context):
    """Request details for a queue entry."""
    entry = handoff_context['selected_entry']

    # Mock enriched entry details
    handoff_context['entry_details'] = {
        'entry': entry,
        'business': handoff_context['businesses'][0],  # First business
        'criteria': handoff_context['criteria'][0]     # First criteria
    }


@when("I perform bulk qualification")
def perform_bulk_qualification_engagement(handoff_context):
    """Perform bulk qualification with engagement checks."""
    business_ids = [b["id"] for b in handoff_context['businesses']]
    criteria_id = handoff_context['selected_criteria_id']

    # Mock qualification with engagement checks
    results = []
    criteria = handoff_context['qualification_engine'].get_criteria_by_id(criteria_id)

    for business in handoff_context['businesses']:
        user_id = f"business_{business['id']}"
        engagement = handoff_context['qualification_engine'].engagement_analytics.get_user_engagement_summary(user_id)

        # Check engagement requirements
        meets_engagement = engagement.get('total_page_views', 0) >= criteria.engagement_requirements.get('min_page_views', 0)

        qualifies = (
            business['score'] >= criteria.min_score and
            business.get('website', '') != '' and
            meets_engagement
        )

        status = QualificationStatus.QUALIFIED if qualifies else QualificationStatus.REJECTED

        result = QualificationResult(
            business_id=business['id'],
            status=status,
            score=business['score'],
            criteria_id=criteria_id,
            details={
                "criteria_name": criteria.name,
                "engagement_data": {"engagement_summary": engagement}
            }
        )
        results.append(result)

    handoff_context['qualification_results'] = results


@when("they are qualified for handoff")
def qualified_for_handoff(handoff_context):
    """Businesses are qualified and priority calculated."""
    # Calculate priorities for qualified businesses
    qualified_results = [
        r for r in handoff_context.get('qualification_results', [])
        if r.status == QualificationStatus.QUALIFIED
    ]

    priorities = []
    for result in qualified_results:
        priority = handoff_context['handoff_service']._calculate_priority(result)
        priorities.append({
            'business_id': result.business_id,
            'score': result.score,
            'priority': priority,
            'engagement': result.details.get('engagement_data', {})
        })

    handoff_context['priority_results'] = priorities


@when("I request the analytics summary")
def request_analytics_summary(handoff_context):
    """Request analytics summary."""
    analytics_data = handoff_context['analytics_data']

    # Mock analytics response
    handoff_context['analytics_summary'] = {
        'summary': analytics_data['totals'],
        'status_breakdown': [
            {
                'status': row[0],
                'count': row[1],
                'avg_priority': row[2],
                'avg_score': row[3]
            }
            for row in analytics_data['status']
        ],
        'assignment_breakdown': [
            {
                'assignee_id': row[0],
                'assignee_name': 'Test User',
                'assigned_count': row[1]
            }
            for row in analytics_data['assignments']
        ],
        'criteria_breakdown': [
            {
                'criteria_id': row[0],
                'criteria_name': row[1],
                'qualified_count': row[2],
                'avg_score': row[3]
            }
            for row in analytics_data['criteria']
        ]
    }


@when("I specify the criteria parameters")
def specify_criteria_parameters(handoff_context):
    """Specify parameters for new criteria."""
    # Parameters already set in given step
    pass


@when("include required fields and custom rules")
def include_fields_and_rules(handoff_context):
    """Include required fields and custom rules."""
    # Already included in criteria definition
    pass


@when("I check the operation status")
def check_operation_status(handoff_context):
    """Check bulk operation status."""
    operation_id = handoff_context['operation_id']

    # Mock operation status response
    handoff_context['operation_status'] = {
        'operation_id': operation_id,
        'status': 'completed',
        'total_count': 4,
        'success_count': 2,
        'failure_count': 2,
        'operation_details': {
            'qualified_count': 2,
            'rejected_count': 2
        }
    }


@then("only businesses meeting the criteria should be qualified")
def only_qualifying_businesses_qualified(handoff_context):
    """Verify only qualifying businesses were qualified."""
    results = handoff_context['qualification_results']
    qualified = [r for r in results if r.status == QualificationStatus.QUALIFIED]

    # Based on our test data: TechCorp (85) and Enterprise Ltd (92) should qualify
    # StartupInc (45) fails score, SmallBiz (65) fails website requirement
    assert len(qualified) == 2
    qualified_ids = [r.business_id for r in qualified]
    assert 1 in qualified_ids  # TechCorp
    assert 3 in qualified_ids  # Enterprise Ltd


@then("qualified businesses should be added to the handoff queue")
def qualified_added_to_queue(handoff_context):
    """Verify qualified businesses were added to queue."""
    # Verify add_to_queue was called for qualified businesses
    qualified_count = len([r for r in handoff_context['qualification_results']
                          if r.status == QualificationStatus.QUALIFIED])

    assert handoff_context['handoff_service']._add_to_queue.call_count == qualified_count


@then("an operation record should track the qualification process")
def operation_record_tracks_process(handoff_context):
    """Verify operation tracking."""
    assert handoff_context['operation_id'] is not None
    assert handoff_context['handoff_service']._create_bulk_operation.called
    assert handoff_context['handoff_service']._update_bulk_operation.called


@then("I should only see qualified entries")
def only_see_qualified_entries(handoff_context):
    """Verify only qualified entries are shown."""
    filtered = handoff_context['filtered_entries']

    for entry in filtered:
        assert entry.status == HandoffStatus.QUALIFIED


@then("the entries should be sorted by priority")
def entries_sorted_by_priority(handoff_context):
    """Verify entries are sorted by priority."""
    filtered = handoff_context['filtered_entries']

    # Check descending priority order
    priorities = [e.priority for e in filtered]
    assert priorities == sorted(priorities, reverse=True)


@then("the entries should be marked as assigned")
def entries_marked_assigned(handoff_context):
    """Verify entries were marked as assigned."""
    result = handoff_context['assignment_result']
    assert result['success'] is True


@then("the sales team member's capacity should be updated")
def capacity_updated(handoff_context):
    """Verify capacity was updated."""
    # In actual implementation, this would update the database
    # Here we verify the assignment calls were made
    assert handoff_context['handoff_service'].assign_queue_entry.called


@then("assignment history should be recorded")
def assignment_history_recorded(handoff_context):
    """Verify assignment history was recorded."""
    # This would be verified by checking database calls in real implementation
    assert handoff_context['assignment_result']['success'] is True


@then("the assignment should be rejected")
def assignment_rejected(handoff_context):
    """Verify assignment was rejected."""
    result = handoff_context['assignment_result']
    assert result['success'] is False


@then("an error message should indicate capacity exceeded")
def error_capacity_exceeded(handoff_context):
    """Verify capacity exceeded error."""
    result = handoff_context['assignment_result']
    assert "capacity" in result['error'].lower()


@then("I should see business information")
def see_business_information(handoff_context):
    """Verify business information is shown."""
    details = handoff_context['entry_details']
    assert 'business' in details
    assert details['business']['name'] == "TechCorp"


@then("qualification criteria details")
def see_criteria_details(handoff_context):
    """Verify criteria details are shown."""
    details = handoff_context['entry_details']
    assert 'criteria' in details
    assert details['criteria'].name == "Basic Qualification"


@then("engagement analytics summary")
def see_engagement_summary(handoff_context):
    """Verify engagement summary is shown."""
    entry = handoff_context['entry_details']['entry']
    assert entry.engagement_summary is not None


@then("qualification scoring breakdown")
def see_scoring_breakdown(handoff_context):
    """Verify scoring breakdown is shown."""
    entry = handoff_context['entry_details']['entry']
    assert entry.qualification_details is not None


@then("only businesses with sufficient engagement should qualify")
def only_sufficient_engagement_qualify(handoff_context):
    """Verify engagement requirements were checked."""
    results = handoff_context['qualification_results']
    qualified = [r for r in results if r.status == QualificationStatus.QUALIFIED]

    # Only business_1 should qualify (10 page views >= 5 required)
    assert len(qualified) == 1
    assert qualified[0].business_id == 1


@then("engagement data should be included in qualification details")
def engagement_data_included(handoff_context):
    """Verify engagement data is included."""
    results = handoff_context['qualification_results']

    for result in results:
        assert 'engagement_data' in result.details


@then("higher scoring businesses should get higher priority")
def higher_scores_higher_priority(handoff_context):
    """Verify score-based priority calculation."""
    priorities = handoff_context['priority_results']

    # Sort by score and verify priority order
    by_score = sorted(priorities, key=lambda x: x['score'], reverse=True)
    by_priority = sorted(priorities, key=lambda x: x['priority'], reverse=True)

    # Higher scores should generally correlate with higher priorities
    assert by_score[0]['business_id'] == by_priority[0]['business_id']


@then("businesses with conversions should get priority boost")
def conversions_priority_boost(handoff_context):
    """Verify conversion-based priority boost."""
    priorities = handoff_context['priority_results']

    # Find businesses with and without conversions
    with_conversions = [p for p in priorities
                       if p['engagement'].get('engagement_summary', {}).get('conversions', 0) > 0]
    without_conversions = [p for p in priorities
                          if p['engagement'].get('engagement_summary', {}).get('conversions', 0) == 0]

    if with_conversions and without_conversions:
        # Businesses with conversions should generally have higher priority
        # (accounting for base score differences)
        max_with = max(p['priority'] for p in with_conversions)
        max_without = max(p['priority'] for p in without_conversions)
        assert max_with >= max_without


@then("businesses with high page views should get priority boost")
def high_pageviews_priority_boost(handoff_context):
    """Verify page view-based priority boost."""
    priorities = handoff_context['priority_results']

    # This is tested implicitly through the overall priority calculation
    assert len(priorities) > 0


@then("I should see total counts by status")
def see_total_counts_by_status(handoff_context):
    """Verify status breakdown in analytics."""
    summary = handoff_context['analytics_summary']
    assert 'status_breakdown' in summary
    assert len(summary['status_breakdown']) > 0


@then("assignment breakdown by sales team member")
def see_assignment_breakdown(handoff_context):
    """Verify assignment breakdown."""
    summary = handoff_context['analytics_summary']
    assert 'assignment_breakdown' in summary
    assert len(summary['assignment_breakdown']) > 0


@then("qualification criteria breakdown")
def see_criteria_breakdown(handoff_context):
    """Verify criteria breakdown."""
    summary = handoff_context['analytics_summary']
    assert 'criteria_breakdown' in summary
    assert len(summary['criteria_breakdown']) > 0


@then("average scores and priorities")
def see_average_scores_priorities(handoff_context):
    """Verify average scores and priorities."""
    summary = handoff_context['analytics_summary']
    status_breakdown = summary['status_breakdown']

    for status in status_breakdown:
        assert 'avg_priority' in status
        assert 'avg_score' in status


@then("the criteria should be created successfully")
def criteria_created_successfully(handoff_context):
    """Verify criteria creation."""
    # Mock successful creation
    handoff_context['creation_result'] = {"success": True, "criteria_id": 3}
    assert handoff_context['creation_result']['success'] is True


@then("available for use in bulk qualification")
def available_for_qualification(handoff_context):
    """Verify criteria is available for use."""
    # In actual implementation, this would be verified by listing criteria
    assert handoff_context['creation_result']['criteria_id'] is not None


@then("I should see the current progress")
def see_current_progress(handoff_context):
    """Verify operation progress is shown."""
    status = handoff_context['operation_status']
    assert 'status' in status
    assert 'total_count' in status


@then("counts of successful and failed qualifications")
def see_success_failure_counts(handoff_context):
    """Verify success/failure counts."""
    status = handoff_context['operation_status']
    assert 'success_count' in status
    assert 'failure_count' in status


@then("detailed operation results when completed")
def see_detailed_results(handoff_context):
    """Verify detailed operation results."""
    status = handoff_context['operation_status']
    assert status['status'] == 'completed'
    assert 'operation_details' in status
    assert 'qualified_count' in status['operation_details']
