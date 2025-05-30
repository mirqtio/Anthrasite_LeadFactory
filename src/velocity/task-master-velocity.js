#!/usr/bin/env node

/**
 * Task-Master with Velocity Integration
 * Enhanced task-master commands with velocity tracking
 */

const { spawn } = require('child_process');
const VelocityIntegration = require('./integration');
const chalk = require('chalk');

class TaskMasterVelocity {
  constructor() {
    this.integration = new VelocityIntegration();
  }

  /**
   * Enhanced set-status command with velocity tracking
   * @param {Array} args - Command arguments
   */
  async setStatus(args) {
    try {
      // Parse arguments
      const idIndex = args.findIndex(arg => arg.startsWith('--id='));
      const statusIndex = args.findIndex(arg => arg.startsWith('--status='));

      if (idIndex === -1 || statusIndex === -1) {
        console.error(chalk.red('❌ Error: --id and --status are required'));
        return;
      }

      const taskId = args[idIndex].split('=')[1];
      const newStatus = args[statusIndex].split('=')[1];

      // Get old status before change
      const tasks = await this.integration.velocityService.loadTasks();
      const task = this.integration.velocityService.findTaskById(tasks, taskId);
      const oldStatus = task ? task.status : null;

      // Run original task-master command
      console.log(chalk.blue('🔄 Running task-master set-status with velocity tracking...\n'));

      const result = await this.runTaskMasterCommand(['set-status', ...args.slice(1)]);

      if (result.success) {
        // Update velocity metadata
        if (oldStatus !== newStatus) {
          await this.integration.onTaskStatusChange(taskId, oldStatus, newStatus);

          // Show velocity insights
          if (newStatus === 'done') {
            console.log(chalk.green.bold('\n📊 Velocity Insights:'));
            await this.showTaskVelocityInsights(taskId);
          }
        }
      }

    } catch (error) {
      console.error(chalk.red('❌ Error in velocity-enhanced set-status:'), error.message);
    }
  }

  /**
   * Enhanced list command with velocity summary
   * @param {Array} args - Command arguments
   */
  async list(args) {
    try {
      // Run original task-master list command
      const result = await this.runTaskMasterCommand(['list', ...args.slice(1)]);

      if (result.success) {
        // Add velocity summary
        console.log(chalk.blue.bold('\n📊 Velocity Summary'));
        console.log(chalk.gray('─'.repeat(40)));

        const summary = await this.integration.generateVelocitySummary();

        if (summary) {
          const velocityColor = summary.dailyVelocity > 0 ? chalk.green : chalk.gray;
          const trendIcon = this.getTrendIcon(summary.trend);

          console.log(`Daily Velocity:    ${velocityColor.bold(summary.dailyVelocity.toFixed(1))} points/day ${trendIcon}`);
          console.log(`Tasks Completed:   ${chalk.cyan.bold(summary.tasksCompleted)} (last 7 days)`);
          console.log(`Avg Cycle Time:    ${chalk.green.bold(summary.averageCycleTime.toFixed(1))} hours`);
          console.log(`Work in Progress:  ${chalk.yellow.bold(summary.workInProgress)} tasks`);

          if (summary.estimatedCompletion) {
            const completionDate = new Date(summary.estimatedCompletion).toLocaleDateString();
            console.log(`Est. Completion:   ${chalk.green.bold(completionDate)}`);
          }

          if (summary.trendChange !== 0) {
            const changeColor = summary.trendChange > 0 ? chalk.green : chalk.red;
            console.log(`Trend Change:      ${changeColor.bold(`${summary.trendChange > 0 ? '+' : ''}${summary.trendChange.toFixed(1)}%`)}`);
          }
        } else {
          console.log(chalk.gray('Velocity data not available'));
        }

        console.log(chalk.gray('\nUse "velocity dashboard" for detailed metrics'));
        console.log('');
      }

    } catch (error) {
      console.error(chalk.red('❌ Error in velocity-enhanced list:'), error.message);
    }
  }

  /**
   * Show velocity insights for a specific task
   * @param {string|number} taskId - Task ID
   */
  async showTaskVelocityInsights(taskId) {
    try {
      const tasks = await this.integration.velocityService.loadTasks();
      const task = this.integration.velocityService.findTaskById(tasks, taskId);

      if (!task || !task.velocity_metadata) {
        console.log(chalk.gray('No velocity data available for this task'));
        return;
      }

      const vm = task.velocity_metadata;

      console.log(`Task: ${chalk.bold(task.title)}`);
      console.log(`Complexity: ${chalk.cyan.bold(vm.complexity_score)} points`);

      if (vm.actual_hours) {
        console.log(`Actual Time: ${chalk.green.bold(vm.actual_hours.toFixed(2))} hours`);

        const velocityRate = this.integration.velocityService.calculator.calculateVelocityRate(
          vm.complexity_score,
          vm.actual_hours
        );
        console.log(`Velocity Rate: ${chalk.green.bold(velocityRate.toFixed(2))} points/hour`);
      }

      if (task.started_at && task.completed_at) {
        const cycleTime = this.integration.velocityService.calculator.calculateTaskDuration(
          task.started_at,
          task.completed_at
        );
        console.log(`Cycle Time: ${chalk.green.bold(cycleTime.toFixed(2))} hours`);
      }

    } catch (error) {
      console.error(chalk.red('❌ Error showing velocity insights:'), error.message);
    }
  }

  /**
   * Run original task-master command
   * @param {Array} args - Command arguments
   * @returns {Promise<Object>} Command result
   */
  async runTaskMasterCommand(args) {
    return new Promise((resolve) => {
      const child = spawn('task-master', args, {
        stdio: 'inherit',
        cwd: process.cwd()
      });

      child.on('close', (code) => {
        resolve({ success: code === 0, exitCode: code });
      });

      child.on('error', (error) => {
        console.error(chalk.red('❌ Error running task-master:'), error.message);
        resolve({ success: false, error });
      });
    });
  }

  /**
   * Get trend direction icon
   * @param {string} direction - Trend direction
   * @returns {string} Icon
   */
  getTrendIcon(direction) {
    switch (direction) {
      case 'improving': return '📈';
      case 'declining': return '📉';
      case 'stable': return '➡️';
      default: return '';
    }
  }

  /**
   * Show help with velocity commands
   */
  showHelp() {
    console.log(chalk.blue.bold('\n🚀 Task-Master with Velocity Tracking\n'));

    console.log(chalk.yellow.bold('Enhanced Commands:'));
    console.log('  set-status --id=<id> --status=<status>');
    console.log('    Set task status with velocity tracking');
    console.log('');
    console.log('  list');
    console.log('    List tasks with velocity summary');
    console.log('');

    console.log(chalk.yellow.bold('Velocity Commands:'));
    console.log('  velocity metrics [--period=week|month]');
    console.log('    Show velocity metrics');
    console.log('');
    console.log('  velocity dashboard');
    console.log('    Show velocity dashboard with charts');
    console.log('');
    console.log('  velocity trend [--weeks=4]');
    console.log('    Show velocity trend analysis');
    console.log('');
    console.log('  velocity report [--output=file.json]');
    console.log('    Generate velocity report');
    console.log('');

    console.log(chalk.yellow.bold('Migration:'));
    console.log('  migrate [--dry-run]');
    console.log('    Migrate existing tasks to velocity tracking');
    console.log('');

    console.log(chalk.gray('Examples:'));
    console.log(chalk.gray('  ./task-master-velocity.js set-status --id=15.5 --status=done'));
    console.log(chalk.gray('  ./task-master-velocity.js list'));
    console.log(chalk.gray('  ./task-master-velocity.js velocity dashboard'));
    console.log('');
  }
}

// CLI entry point
async function main() {
  const velocityTM = new TaskMasterVelocity();
  const args = process.argv.slice(2);

  if (args.length === 0) {
    velocityTM.showHelp();
    return;
  }

  const command = args[0];

  try {
    switch (command) {
      case 'set-status':
        await velocityTM.setStatus(args);
        break;
      case 'list':
        await velocityTM.list(args);
        break;
      case 'velocity':
        // Delegate to velocity CLI
        const { spawn } = require('child_process');
        const velocityCLI = spawn('node', ['src/velocity/cli.js', ...args.slice(1)], {
          stdio: 'inherit',
          cwd: process.cwd()
        });
        break;
      case 'migrate':
        const migrateCLI = spawn('node', ['src/velocity/migrate.js', ...args.slice(1)], {
          stdio: 'inherit',
          cwd: process.cwd()
        });
        break;
      case 'help':
      default:
        velocityTM.showHelp();
        break;
    }
  } catch (error) {
    console.error(chalk.red('❌ Command failed:'), error.message);
    process.exit(1);
  }
}

// Export for testing
module.exports = TaskMasterVelocity;

// Run CLI if called directly
if (require.main === module) {
  main().catch(console.error);
}
