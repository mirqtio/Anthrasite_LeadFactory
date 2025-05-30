# Velocity Tracking Quick Reference

## Essential Commands

### Dashboard & Metrics
```bash
task-master velocity dashboard          # Show velocity dashboard
task-master velocity metrics           # Show velocity metrics
task-master velocity trend             # Show velocity trend
```

### Charts & Visualization
```bash
task-master velocity chart --type=velocity    # Velocity trend chart
task-master velocity chart --type=burndown    # Burndown chart
task-master velocity chart --type=cycle-time  # Cycle time chart
```

### Configuration
```bash
task-master velocity config list              # List all preferences
task-master velocity config set <key> <value> # Set preference
task-master velocity config get <key>         # Get preference value
task-master velocity config reset             # Reset to defaults
```

## Key Preferences

### Display Settings
| Setting | Default | Description |
|---------|---------|-------------|
| `display.useColors` | `true` | Enable colored output |
| `display.chartHeight` | `10` | Chart height (5-50) |
| `display.compactMode` | `false` | Compact display format |

### Calculation Settings
| Setting | Default | Description |
|---------|---------|-------------|
| `calculation.workingHoursPerDay` | `8` | Working hours per day |
| `calculation.workingDaysPerWeek` | `5` | Working days per week |
| `calculation.velocityPeriod` | `"week"` | Velocity calculation period |

## Quick Setup

```bash
# 1. Migrate existing tasks (if needed)
node src/velocity/migrate.js

# 2. Configure for your team
task-master velocity config set calculation.workingHoursPerDay 8
task-master velocity config set calculation.workingDaysPerWeek 5

# 3. View your dashboard
task-master velocity dashboard
```

## Common Use Cases

### Daily Standup
```bash
task-master velocity metrics --days=1
task-master velocity dashboard
```

### Sprint Planning
```bash
task-master velocity metrics --period=week --weeks=4
task-master velocity chart --type=velocity
```

### Monthly Review
```bash
task-master velocity metrics --period=month
task-master velocity trend --weeks=12
```

## Troubleshooting

### No Data Showing
```bash
# Check if tasks have velocity metadata
node src/velocity/migrate.js

# Verify completed tasks exist
task-master list --status=done
```

### Incorrect Calculations
```bash
# Check working hours setting
task-master velocity config get calculation.workingHoursPerDay

# Review preferences
task-master velocity config list
```

### Performance Issues
```bash
# Limit date range
task-master velocity metrics --days=7

# Use compact mode
task-master velocity config set display.compactMode true
```

## Key Metrics Explained

- **Daily Velocity**: Points completed per working day
- **Cycle Time**: Time from start to completion
- **ETC**: Estimated time to complete remaining work
- **Velocity Points**: Complexity/effort measure for tasks

## Status Workflow

```
pending → in-progress → done
```

Velocity is calculated when tasks move to `done` status.

## Testing

```bash
# Run all tests
node src/velocity/test-suite.js

# Performance tests
node src/velocity/test-suite.js --performance

# Preferences tests
node src/velocity/preferences-test.js --test
```

---

For detailed information, see the [complete velocity tracking guide](velocity-tracking-guide.md).
