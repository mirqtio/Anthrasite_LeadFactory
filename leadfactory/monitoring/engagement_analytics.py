"""Enhanced engagement tracking and analytics service.

Implements Feature 5: Engagement Tracking improvements.
- Comprehensive user engagement metrics
- Real-time tracking and analytics
- Conversion funnel analysis
- User behavior insights
- Performance dashboards
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """Types of engagement events."""

    PAGE_VIEW = "page_view"
    EMAIL_OPEN = "email_open"
    EMAIL_CLICK = "email_click"
    FORM_SUBMIT = "form_submit"
    DOWNLOAD = "download"
    VIDEO_PLAY = "video_play"
    PURCHASE = "purchase"
    SIGNUP = "signup"
    LOGIN = "login"
    LOGOUT = "logout"
    SHARE = "share"
    COMMENT = "comment"
    LIKE = "like"
    SEARCH = "search"
    FILTER = "filter"
    SORT = "sort"


class ConversionGoal(Enum):
    """Conversion goal types."""

    LEAD_GENERATION = "lead_generation"
    PURCHASE = "purchase"
    SIGNUP = "signup"
    ENGAGEMENT = "engagement"
    RETENTION = "retention"


@dataclass
class EngagementEvent:
    """Individual engagement event."""

    event_id: str
    user_id: str
    session_id: str
    event_type: EventType
    timestamp: datetime
    properties: Dict[str, Any]
    page_url: Optional[str] = None
    referrer: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    campaign_id: Optional[str] = None
    ab_test_variant: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["event_type"] = (
            data["event_type"].value
            if isinstance(data["event_type"], EventType)
            else data["event_type"]
        )
        if isinstance(data["timestamp"], datetime):
            data["timestamp"] = data["timestamp"].isoformat()
        return data


@dataclass
class UserSession:
    """User session tracking."""

    session_id: str
    user_id: str
    start_time: datetime
    end_time: Optional[datetime]
    total_events: int
    page_views: int
    unique_pages: int
    bounce_rate: float
    time_on_site: float  # seconds
    conversion_events: List[str]
    traffic_source: Optional[str] = None
    campaign_id: Optional[str] = None
    device_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        if isinstance(data["start_time"], datetime):
            data["start_time"] = data["start_time"].isoformat()
        if data["end_time"] and isinstance(data["end_time"], datetime):
            data["end_time"] = data["end_time"].isoformat()
        return data


@dataclass
class ConversionFunnel:
    """Conversion funnel configuration."""

    funnel_id: str
    name: str
    steps: List[Dict[str, Any]]
    goal_type: ConversionGoal
    time_window_hours: int = 24
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["goal_type"] = (
            data["goal_type"].value
            if isinstance(data["goal_type"], ConversionGoal)
            else data["goal_type"]
        )
        return data


class EngagementAnalytics:
    """Service for tracking and analyzing user engagement."""

    def __init__(self):
        """Initialize the engagement analytics service."""
        self.storage = get_storage_instance()
        logger.info("Initialized EngagementAnalytics")

    def track_event(
        self,
        user_id: str,
        session_id: str,
        event_type: str,
        properties: Dict[str, Any],
        page_url: Optional[str] = None,
        referrer: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        campaign_id: Optional[str] = None,
        ab_test_variant: Optional[str] = None,
    ) -> bool:
        """Track an engagement event.

        Args:
            user_id: User identifier
            session_id: Session identifier
            event_type: Type of event
            properties: Event-specific properties
            page_url: Current page URL
            referrer: Referrer URL
            user_agent: User agent string
            ip_address: User IP address
            campaign_id: Associated campaign ID
            ab_test_variant: A/B test variant

        Returns:
            True if tracked successfully, False otherwise
        """
        try:
            import uuid

            event_id = str(uuid.uuid4())

            # Convert string event type to enum
            try:
                event_type_enum = EventType(event_type.lower())
            except ValueError:
                logger.warning(f"Unknown event type: {event_type}")
                event_type_enum = EventType.PAGE_VIEW  # Default fallback

            event = EngagementEvent(
                event_id=event_id,
                user_id=user_id,
                session_id=session_id,
                event_type=event_type_enum,
                timestamp=datetime.utcnow(),
                properties=properties,
                page_url=page_url,
                referrer=referrer,
                user_agent=user_agent,
                ip_address=ip_address,
                campaign_id=campaign_id,
                ab_test_variant=ab_test_variant,
            )

            # Store event
            success = self.storage.store_engagement_event(event.to_dict())

            if success:
                # Update session data
                self._update_session(session_id, user_id, event)

                # Check for conversions
                self._check_conversions(user_id, session_id, event)

                logger.debug(f"Tracked event {event_type} for user {user_id}")
                return True
            else:
                logger.error(f"Failed to store engagement event for user {user_id}")
                return False

        except Exception as e:
            logger.error(f"Error tracking event: {e}")
            return False

    def _update_session(
        self, session_id: str, user_id: str, event: EngagementEvent
    ) -> None:
        """Update session tracking data."""
        try:
            # Get or create session
            session_data = self.storage.get_user_session(session_id)

            if not session_data:
                # Create new session
                session = UserSession(
                    session_id=session_id,
                    user_id=user_id,
                    start_time=event.timestamp,
                    end_time=None,
                    total_events=1,
                    page_views=1 if event.event_type == EventType.PAGE_VIEW else 0,
                    unique_pages=(
                        1
                        if event.event_type == EventType.PAGE_VIEW and event.page_url
                        else 0
                    ),
                    bounce_rate=0.0,
                    time_on_site=0.0,
                    conversion_events=[],
                    traffic_source=event.referrer,
                    campaign_id=event.campaign_id,
                    device_type=self._extract_device_type(event.user_agent),
                )
            else:
                # Update existing session
                session = UserSession(**session_data)
                session.end_time = event.timestamp
                session.total_events += 1

                if event.event_type == EventType.PAGE_VIEW:
                    session.page_views += 1
                    if event.page_url:
                        # Get unique pages count
                        unique_pages = self.storage.get_session_unique_pages(session_id)
                        session.unique_pages = (
                            len(unique_pages) if unique_pages else session.unique_pages
                        )

                # Calculate time on site
                if session.start_time:
                    session.time_on_site = (
                        event.timestamp - session.start_time
                    ).total_seconds()

                # Calculate bounce rate (1 page view = 100% bounce)
                session.bounce_rate = 1.0 if session.page_views == 1 else 0.0

                # Track conversions
                if self._is_conversion_event(event.event_type):
                    if event.event_id not in session.conversion_events:
                        session.conversion_events.append(event.event_id)

            # Store updated session
            self.storage.update_user_session(session.to_dict())

        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")

    def _extract_device_type(self, user_agent: Optional[str]) -> Optional[str]:
        """Extract device type from user agent."""
        if not user_agent:
            return None

        user_agent_lower = user_agent.lower()

        if any(
            mobile in user_agent_lower
            for mobile in ["mobile", "android", "iphone", "ipad"]
        ):
            return "mobile"
        elif "tablet" in user_agent_lower:
            return "tablet"
        else:
            return "desktop"

    def _is_conversion_event(self, event_type: EventType) -> bool:
        """Check if event type is a conversion event."""
        conversion_events = {
            EventType.PURCHASE,
            EventType.SIGNUP,
            EventType.FORM_SUBMIT,
            EventType.DOWNLOAD,
        }
        return event_type in conversion_events

    def _check_conversions(
        self, user_id: str, session_id: str, event: EngagementEvent
    ) -> None:
        """Check if event triggers any conversion funnels."""
        try:
            # Get active funnels
            funnels = self.storage.get_active_conversion_funnels()

            for funnel_data in funnels:
                funnel = ConversionFunnel(**funnel_data)

                # Check if event matches any funnel step
                for step_idx, step in enumerate(funnel.steps):
                    if self._event_matches_step(event, step):
                        # Record funnel progress
                        self.storage.update_funnel_progress(
                            funnel.funnel_id,
                            user_id,
                            session_id,
                            step_idx,
                            event.timestamp,
                        )

                        # Check if user completed the funnel
                        if step_idx == len(funnel.steps) - 1:
                            self._record_conversion(funnel, user_id, session_id, event)

                        break

        except Exception as e:
            logger.error(f"Error checking conversions: {e}")

    def _event_matches_step(self, event: EngagementEvent, step: Dict[str, Any]) -> bool:
        """Check if event matches a funnel step."""
        try:
            step_event_type = step.get("event_type")
            if step_event_type and event.event_type.value != step_event_type:
                return False

            # Check properties match
            required_properties = step.get("properties", {})
            for key, value in required_properties.items():
                if event.properties.get(key) != value:
                    return False

            # Check page URL pattern
            page_pattern = step.get("page_pattern")
            if page_pattern and event.page_url:
                import re

                if not re.match(page_pattern, event.page_url):
                    return False

            return True

        except Exception as e:
            logger.error(f"Error matching event to step: {e}")
            return False

    def _record_conversion(
        self,
        funnel: ConversionFunnel,
        user_id: str,
        session_id: str,
        event: EngagementEvent,
    ) -> None:
        """Record a completed conversion."""
        try:
            conversion_data = {
                "funnel_id": funnel.funnel_id,
                "user_id": user_id,
                "session_id": session_id,
                "conversion_time": event.timestamp.isoformat(),
                "goal_type": funnel.goal_type.value,
                "event_id": event.event_id,
                "campaign_id": event.campaign_id,
                "ab_test_variant": event.ab_test_variant,
            }

            self.storage.record_conversion(conversion_data)
            logger.info(
                f"Recorded conversion for funnel {funnel.funnel_id}, user {user_id}"
            )

        except Exception as e:
            logger.error(f"Error recording conversion: {e}")

    def get_user_engagement_summary(
        self, user_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get engagement summary for a user.

        Args:
            user_id: User identifier
            days: Number of days to analyze

        Returns:
            Engagement summary dictionary
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get user events
            events = self.storage.get_user_events(user_id, start_date, end_date)

            # Get user sessions
            sessions = self.storage.get_user_sessions(user_id, start_date, end_date)

            # Calculate metrics
            total_events = len(events)
            total_sessions = len(sessions)

            # Event type breakdown
            event_types = {}
            for event in events:
                event_type = event.get("event_type", "unknown")
                event_types[event_type] = event_types.get(event_type, 0) + 1

            # Session metrics
            avg_session_duration = 0
            total_page_views = 0
            if sessions:
                total_duration = sum(s.get("time_on_site", 0) for s in sessions)
                avg_session_duration = total_duration / len(sessions)
                total_page_views = sum(s.get("page_views", 0) for s in sessions)

            # Conversion metrics
            conversions = self.storage.get_user_conversions(
                user_id, start_date, end_date
            )

            return {
                "user_id": user_id,
                "period_days": days,
                "total_events": total_events,
                "total_sessions": total_sessions,
                "total_page_views": total_page_views,
                "avg_session_duration": round(avg_session_duration, 2),
                "event_types": event_types,
                "conversions": len(conversions),
                "conversion_rate": (
                    len(conversions) / total_sessions if total_sessions > 0 else 0
                ),
                "last_activity": events[0].get("timestamp") if events else None,
            }

        except Exception as e:
            logger.error(f"Error getting user engagement summary: {e}")
            return {}

    def get_campaign_analytics(
        self, campaign_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get analytics for a specific campaign.

        Args:
            campaign_id: Campaign identifier
            days: Number of days to analyze

        Returns:
            Campaign analytics dictionary
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get campaign events
            events = self.storage.get_campaign_events(campaign_id, start_date, end_date)

            # Get unique users
            unique_users = set(event.get("user_id") for event in events)

            # Get sessions for this campaign
            sessions = self.storage.get_campaign_sessions(
                campaign_id, start_date, end_date
            )

            # Calculate metrics
            total_events = len(events)
            total_users = len(unique_users)
            total_sessions = len(sessions)

            # Event breakdown
            event_breakdown = {}
            for event in events:
                event_type = event.get("event_type", "unknown")
                event_breakdown[event_type] = event_breakdown.get(event_type, 0) + 1

            # Conversion metrics
            conversions = self.storage.get_campaign_conversions(
                campaign_id, start_date, end_date
            )
            conversion_rate = (
                len(conversions) / total_sessions if total_sessions > 0 else 0
            )

            # Traffic sources
            traffic_sources = {}
            for session in sessions:
                source = session.get("traffic_source", "direct")
                traffic_sources[source] = traffic_sources.get(source, 0) + 1

            return {
                "campaign_id": campaign_id,
                "period_days": days,
                "total_events": total_events,
                "total_users": total_users,
                "total_sessions": total_sessions,
                "event_breakdown": event_breakdown,
                "conversions": len(conversions),
                "conversion_rate": round(conversion_rate, 4),
                "traffic_sources": traffic_sources,
                "top_pages": self._get_top_pages(events),
                "avg_events_per_session": (
                    round(total_events / total_sessions, 2) if total_sessions > 0 else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error getting campaign analytics: {e}")
            return {}

    def _get_top_pages(
        self, events: List[Dict[str, Any]], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top pages by event count."""
        page_counts = {}

        for event in events:
            page_url = event.get("page_url")
            if page_url:
                page_counts[page_url] = page_counts.get(page_url, 0) + 1

        # Sort by count and return top pages
        sorted_pages = sorted(page_counts.items(), key=lambda x: x[1], reverse=True)

        return [
            {"page_url": page, "event_count": count}
            for page, count in sorted_pages[:limit]
        ]

    def create_conversion_funnel(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        goal_type: str,
        time_window_hours: int = 24,
    ) -> str:
        """Create a new conversion funnel.

        Args:
            name: Funnel name
            steps: List of funnel steps
            goal_type: Type of conversion goal
            time_window_hours: Time window for completion

        Returns:
            Funnel ID
        """
        try:
            import uuid

            funnel_id = str(uuid.uuid4())

            # Convert string goal type to enum
            try:
                goal_type_enum = ConversionGoal(goal_type.lower())
            except ValueError:
                logger.warning(f"Unknown goal type: {goal_type}")
                goal_type_enum = ConversionGoal.ENGAGEMENT  # Default fallback

            funnel = ConversionFunnel(
                funnel_id=funnel_id,
                name=name,
                steps=steps,
                goal_type=goal_type_enum,
                time_window_hours=time_window_hours,
            )

            # Store funnel
            success = self.storage.create_conversion_funnel(funnel.to_dict())

            if success:
                logger.info(f"Created conversion funnel: {name} ({funnel_id})")
                return funnel_id
            else:
                logger.error(f"Failed to create conversion funnel: {name}")
                return ""

        except Exception as e:
            logger.error(f"Error creating conversion funnel: {e}")
            return ""

    def get_funnel_analytics(self, funnel_id: str, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a conversion funnel.

        Args:
            funnel_id: Funnel identifier
            days: Number of days to analyze

        Returns:
            Funnel analytics dictionary
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get funnel data
            funnel_data = self.storage.get_conversion_funnel(funnel_id)
            if not funnel_data:
                return {}

            funnel = ConversionFunnel(**funnel_data)

            # Get funnel progress data
            progress_data = self.storage.get_funnel_progress(
                funnel_id, start_date, end_date
            )

            # Calculate step conversion rates
            step_stats = []
            for i, step in enumerate(funnel.steps):
                users_at_step = len(
                    [p for p in progress_data if p.get("step_index") >= i]
                )
                completed_step = len(
                    [p for p in progress_data if p.get("step_index") > i]
                )

                conversion_rate = (
                    completed_step / users_at_step if users_at_step > 0 else 0
                )

                step_stats.append(
                    {
                        "step_index": i,
                        "step_name": step.get("name", f"Step {i+1}"),
                        "users_entered": users_at_step,
                        "users_completed": completed_step,
                        "conversion_rate": round(conversion_rate, 4),
                        "drop_off_rate": round(1 - conversion_rate, 4),
                    }
                )

            # Overall funnel metrics
            total_entries = len([p for p in progress_data if p.get("step_index") == 0])
            total_completions = len(
                [
                    p
                    for p in progress_data
                    if p.get("step_index") == len(funnel.steps) - 1
                ]
            )
            overall_conversion_rate = (
                total_completions / total_entries if total_entries > 0 else 0
            )

            return {
                "funnel_id": funnel_id,
                "funnel_name": funnel.name,
                "goal_type": funnel.goal_type.value,
                "period_days": days,
                "total_entries": total_entries,
                "total_completions": total_completions,
                "overall_conversion_rate": round(overall_conversion_rate, 4),
                "step_stats": step_stats,
                "avg_completion_time": self._calculate_avg_completion_time(
                    progress_data
                ),
            }

        except Exception as e:
            logger.error(f"Error getting funnel analytics: {e}")
            return {}

    def _calculate_avg_completion_time(
        self, progress_data: List[Dict[str, Any]]
    ) -> float:
        """Calculate average completion time for funnel."""
        try:
            completion_times = []

            # Group by user and calculate completion time
            user_progress = {}
            for entry in progress_data:
                user_id = entry.get("user_id")
                if user_id not in user_progress:
                    user_progress[user_id] = []
                user_progress[user_id].append(entry)

            for user_id, entries in user_progress.items():
                if len(entries) > 1:
                    # Sort by timestamp
                    sorted_entries = sorted(
                        entries, key=lambda x: x.get("timestamp", "")
                    )
                    start_time = datetime.fromisoformat(
                        sorted_entries[0].get("timestamp", "")
                    )
                    end_time = datetime.fromisoformat(
                        sorted_entries[-1].get("timestamp", "")
                    )
                    completion_time = (end_time - start_time).total_seconds()
                    completion_times.append(completion_time)

            return (
                sum(completion_times) / len(completion_times) if completion_times else 0
            )

        except Exception as e:
            logger.error(f"Error calculating completion time: {e}")
            return 0

    def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time engagement metrics.

        Returns:
            Real-time metrics dictionary
        """
        try:
            # Get metrics for the last hour
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)

            # Active users (users with events in last hour)
            active_events = self.storage.get_events_in_timeframe(start_time, end_time)
            active_users = set(event.get("user_id") for event in active_events)

            # Active sessions
            active_sessions = self.storage.get_active_sessions(start_time)

            # Event breakdown for last hour
            event_breakdown = {}
            for event in active_events:
                event_type = event.get("event_type", "unknown")
                event_breakdown[event_type] = event_breakdown.get(event_type, 0) + 1

            # Page views in last hour
            page_views = len(
                [e for e in active_events if e.get("event_type") == "page_view"]
            )

            return {
                "timestamp": end_time.isoformat(),
                "active_users": len(active_users),
                "active_sessions": len(active_sessions),
                "total_events": len(active_events),
                "page_views": page_views,
                "events_per_minute": round(len(active_events) / 60, 2),
                "event_breakdown": event_breakdown,
            }

        except Exception as e:
            logger.error(f"Error getting real-time metrics: {e}")
            return {}
