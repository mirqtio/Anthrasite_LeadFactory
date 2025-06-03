# Velocity Tracking Data Model Design

## Overview
This document defines the data model changes needed to implement comprehensive velocity tracking in the task-master CLI system.

## Current Task Structure
```json
{
  "id": 1,
  "title": "Task Title",
  "description": "Task description",
  "status": "pending|in-progress|done|deferred|cancelled",
  "priority": "low|medium|high",
  "type": "feature|bug|enhancement",
  "created_at": "2025-05-28T09:00:00Z",
  "dependencies": [2, 3],
  "details": "Detailed implementation notes",
  "test_strategy": "Testing approach",
  "subtasks": [...]
}
```

## Enhanced Task Structure with Velocity Tracking

### New Timestamp Fields
```json
{
  // Existing fields...
  "created_at": "2025-05-28T09:00:00Z",

  // NEW: Velocity tracking timestamps
  "started_at": "2025-05-28T10:30:00Z",      // When status changed to 'in-progress'
  "completed_at": "2025-05-28T15:45:00Z",    // When status changed to 'done'
  "last_updated": "2025-05-28T14:20:00Z",    // Last modification timestamp

  // NEW: Velocity metadata
  "velocity_metadata": {
    "complexity_score": 7,                   // Complexity points (1-10)
    "estimated_hours": 8,                    // Initial time estimate
    "actual_hours": 6.25,                    // Calculated from timestamps
    "velocity_points": 7,                    // Points for velocity calculation
    "blocked_time": 0.5,                     // Hours spent blocked
    "status_history": [
      {
        "status": "pending",
        "timestamp": "2025-05-28T09:00:00Z",
        "duration_hours": 1.5
      },
      {
        "status": "in-progress",
        "timestamp": "2025-05-28T10:30:00Z",
        "duration_hours": 5.25
      },
      {
        "status": "done",
        "timestamp": "2025-05-28T15:45:00Z",
        "duration_hours": null
      }
    ]
  }
}
```

## Velocity Calculation Formulas

### 1. Task Duration
```
task_duration = completed_at - started_at
actual_hours = task_duration / (1000 * 60 * 60) // Convert ms to hours
```

### 2. Velocity Points per Hour
```
velocity_rate = complexity_score / actual_hours
```

### 3. Daily Velocity
```
daily_velocity = sum(completed_tasks_complexity) / work_days
```

### 4. Estimated Time to Completion (ETC)
```
remaining_complexity = sum(pending_tasks_complexity)
etc_days = remaining_complexity / daily_velocity
```

### 5. Velocity Trends
```
weekly_velocity = sum(week_completed_complexity) / 7
velocity_trend = (current_week_velocity - previous_week_velocity) / previous_week_velocity * 100
```

## Database Schema Changes

### Migration Strategy
1. **Backward Compatibility**: All new fields are optional
2. **Default Values**: Existing tasks get `null` for new timestamp fields
3. **Gradual Migration**: Timestamps populated as tasks change status

### Field Specifications

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `started_at` | ISO 8601 String | No | `null` | Timestamp when task started |
| `completed_at` | ISO 8601 String | No | `null` | Timestamp when task completed |
| `last_updated` | ISO 8601 String | No | `created_at` | Last modification time |
| `velocity_metadata` | Object | No | `{}` | Velocity tracking data |
| `velocity_metadata.complexity_score` | Integer (1-10) | No | `5` | Task complexity points |
| `velocity_metadata.estimated_hours` | Float | No | `null` | Initial time estimate |
| `velocity_metadata.actual_hours` | Float | No | `null` | Calculated duration |
| `velocity_metadata.velocity_points` | Integer | No | `complexity_score` | Points for velocity calc |
| `velocity_metadata.blocked_time` | Float | No | `0` | Time spent blocked |
| `velocity_metadata.status_history` | Array | No | `[]` | Status change history |

## Data Access Layer Updates

### New Methods Required
```javascript
// Timestamp management
updateTaskTimestamp(taskId, field, timestamp)
getTaskDuration(taskId)
getTaskStatusHistory(taskId)

// Velocity calculations
calculateDailyVelocity(dateRange)
calculateVelocityTrend(weeks)
getVelocityMetrics(filters)

// Reporting
generateVelocityReport(options)
getCompletionEstimates(taskIds)
getTeamVelocityStats()
```

### Status Change Hooks
```javascript
// Automatically update timestamps on status changes
onStatusChange(taskId, oldStatus, newStatus) {
  const timestamp = new Date().toISOString();

  if (newStatus === 'in-progress' && !task.started_at) {
    updateTaskTimestamp(taskId, 'started_at', timestamp);
  }

  if (newStatus === 'done' && !task.completed_at) {
    updateTaskTimestamp(taskId, 'completed_at', timestamp);
    calculateActualHours(taskId);
  }

  updateTaskTimestamp(taskId, 'last_updated', timestamp);
  addStatusHistoryEntry(taskId, newStatus, timestamp);
}
```

## Velocity Metrics Definitions

### Core Metrics
1. **Velocity Rate**: Complexity points completed per day
2. **Cycle Time**: Average time from start to completion
3. **Lead Time**: Average time from creation to completion
4. **Throughput**: Number of tasks completed per time period
5. **Work in Progress (WIP)**: Number of tasks currently in-progress

### Advanced Metrics
1. **Velocity Trend**: Week-over-week velocity change
2. **Predictability**: Variance in velocity over time
3. **Efficiency**: Actual vs estimated time ratio
4. **Blocked Time Ratio**: Percentage of time spent blocked

## Implementation Phases

### Phase 1: Core Data Model (Subtask 15.1)
- Add new timestamp fields to task schema
- Implement backward compatibility
- Create migration utilities

### Phase 2: Calculation Engine (Subtask 15.2)
- Implement velocity calculation formulas
- Create status change hooks
- Build data access methods

### Phase 3: CLI Integration (Subtasks 15.3-15.6)
- Add velocity command interface
- Enhance list command with velocity data
- Implement user preferences

### Phase 4: Testing & Documentation (Subtasks 15.7-15.9)
- Comprehensive testing suite
- Documentation and training materials
- CI/merge verification

## Acceptance Criteria
- ✅ Schema supports all velocity tracking requirements
- ✅ Backward compatibility maintained
- ✅ Timestamp fields automatically populated
- ✅ Velocity calculations are accurate
- ✅ Data access layer supports new operations
- ✅ Migration path defined for existing data
