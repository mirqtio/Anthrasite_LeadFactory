# Velocity Tracking Setup Guide

## Quick Start

The velocity tracking system is now integrated with your existing task-master workflow!

### 🚀 Easy Usage

Use the new `tm-velocity` command instead of `task-master` to get velocity tracking automatically:

```bash
# Enhanced list with velocity metrics
./scripts/tm-velocity list

# Quick access to velocity dashboard
./scripts/tm-velocity dashboard

# All other task-master commands work as normal
./scripts/tm-velocity set-status --id=1 --status=done
./scripts/tm-velocity next
./scripts/tm-velocity expand --id=5
```

### 📊 Available Commands

**Enhanced Commands:**
- `./scripts/tm-velocity list` - List tasks with velocity summary and dashboard
- `./scripts/tm-velocity dashboard` - Show velocity dashboard
- `./scripts/tm-velocity summary` - Show velocity summary
- `./scripts/tm-velocity metrics` - Show detailed metrics
- `./scripts/tm-velocity trend` - Show trend analysis

**Standard Commands:**
All regular task-master commands work through tm-velocity:
- `./scripts/tm-velocity set-status --id=X --status=done`
- `./scripts/tm-velocity next`
- `./scripts/tm-velocity expand --id=X`
- etc.

### 🔧 Setup Alias (Optional)

For even easier access, add this to your shell profile (`.bashrc`, `.zshrc`, etc.):

```bash
# Add to ~/.bashrc or ~/.zshrc
alias tm='./scripts/tm-velocity'
alias task-master-v='./scripts/tm-velocity'
```

Then you can use:
```bash
tm list
tm dashboard
tm set-status --id=1 --status=done
```

### 📈 What You Get

When you use `tm-velocity list`, you'll see:
1. **Velocity Summary** - Key metrics at the top
2. **Standard Task List** - Your familiar task table
3. **Velocity Dashboard** - Visual progress and trends

### 🎯 Key Features

- **Automatic Integration** - Works with existing task-master workflow
- **Real-time Metrics** - Updates as you complete tasks
- **Visual Dashboard** - Progress bars and trend analysis
- **Zero Configuration** - Works out of the box
- **Backward Compatible** - All existing commands work

### 📚 More Information

For detailed documentation, see:
- `docs/velocity-tracking-guide.md` - Complete feature guide
- `docs/velocity-quick-reference.md` - Command reference
- `docs/velocity-api.md` - API documentation
- `src/velocity/README.md` - Technical overview

### 🚀 Next Steps

1. Try `./scripts/tm-velocity list` to see the enhanced interface
2. Complete a few tasks to see velocity metrics update
3. Use `./scripts/tm-velocity dashboard` to track your progress
4. Set up the optional alias for easier access

The velocity tracking system automatically tracks your task completion patterns and provides insights to help you work more efficiently!
