#!/usr/bin/env node

/**
 * Velocity CLI Module
 * Command-line interface for velocity tracking and reporting
 */

const VelocityService = require('./service');
const VelocityVisualizer = require('./visualizer');
const VelocityPreferences = require('./preferences');
const chalk = require('chalk');

class VelocityCLI {
  constructor() {
    this.service = new VelocityService();
    this.visualizer = new VelocityVisualizer();
    this.preferences = new VelocityPreferences();
  }

  /**
   * Display velocity metrics
   * @param {Object} options - Command options
   */
  async showMetrics(options = {}) {
    try {
      const {
        period = 'week',
        days = period === 'week' ? 7 : period === 'month' ? 30 : 7,
        format = 'table'
      } = options;

      console.log(chalk.blue.bold('\n📊 Velocity Metrics Report\n'));
      console.log(chalk.gray(`Period: Last ${days} days\n`));

      const metrics = await this.service.getVelocityMetrics({ days });

      // Summary section
      console.log(chalk.yellow.bold('📈 Summary'));
      console.log(`Daily Velocity:     ${chalk.green.bold(metrics.velocity.daily.toFixed(1))} points/day`);
      console.log(`Weekly Velocity:    ${chalk.green.bold(metrics.velocity.weekly.toFixed(1))} points/week`);
      console.log(`Tasks Completed:    ${chalk.cyan.bold(metrics.completed.count)}`);
      console.log(`Total Complexity:   ${chalk.cyan.bold(metrics.completed.totalComplexity)} points`);
      console.log(`Work in Progress:   ${chalk.yellow.bold(metrics.workInProgress.count)} tasks`);

      // Cycle time section
      console.log(chalk.yellow.bold('\n⏱️  Cycle Time'));
      console.log(`Average:            ${chalk.green.bold(metrics.cycleTime.average.toFixed(1))} hours`);
      console.log(`Median:             ${chalk.green.bold(metrics.cycleTime.median.toFixed(1))} hours`);
      console.log(`Range:              ${chalk.gray(`${metrics.cycleTime.min.toFixed(1)} - ${metrics.cycleTime.max.toFixed(1)} hours`)}`);

      // Estimates section
      console.log(chalk.yellow.bold('\n🎯 Estimates'));
      console.log(`Remaining Tasks:    ${chalk.cyan.bold(metrics.estimates.totalComplexity)} complexity points`);
      console.log(`Estimated Days:     ${chalk.green.bold(metrics.estimates.estimatedDays.toFixed(1))} days`);
      console.log(`Completion Date:    ${chalk.green.bold(new Date(metrics.estimates.completionDate).toLocaleDateString())}`);

      // Recent tasks
      if (metrics.tasks.length > 0) {
        console.log(chalk.yellow.bold('\n✅ Recently Completed Tasks'));
        metrics.tasks.slice(0, 5).forEach(task => {
          const cycleTime = task.cycleTime ? `${task.cycleTime.toFixed(1)}h` : 'N/A';
          console.log(`  ${chalk.gray('•')} ${task.title.substring(0, 50)}${task.title.length > 50 ? '...' : ''}`);
          console.log(`    ${chalk.gray(`Complexity: ${task.complexity}, Cycle Time: ${cycleTime}`)}`);
        });
      }

      console.log('\n');

    } catch (error) {
      console.error(chalk.red('❌ Error displaying velocity metrics:'), error.message);
    }
  }

  /**
   * Display velocity trend analysis
   * @param {Object} options - Command options
   */
  async showTrend(options = {}) {
    try {
      const { weeks = 4 } = options;

      console.log(chalk.blue.bold('\n📈 Velocity Trend Analysis\n'));
      console.log(chalk.gray(`Analysis period: Last ${weeks} weeks\n`));

      const trend = await this.service.getVelocityTrend(weeks);

      // Trend summary
      console.log(chalk.yellow.bold('📊 Trend Summary'));
      console.log(`Direction:          ${this.getTrendIcon(trend.trend.direction)} ${chalk.bold(trend.trend.direction.toUpperCase())}`);

      if (trend.trend.changePercent !== 0) {
        const color = trend.trend.changePercent > 0 ? chalk.green : chalk.red;
        console.log(`Change:             ${color.bold(`${trend.trend.changePercent > 0 ? '+' : ''}${trend.trend.changePercent.toFixed(1)}%`)}`);
      }

      console.log(`Average Velocity:   ${chalk.green.bold(trend.summary.averageVelocity.toFixed(1))} points/day`);
      console.log(`Total Tasks:        ${chalk.cyan.bold(trend.summary.totalTasksCompleted)}`);
      console.log(`Total Complexity:   ${chalk.cyan.bold(trend.summary.totalComplexityCompleted)} points`);

      // Weekly breakdown
      console.log(chalk.yellow.bold('\n📅 Weekly Breakdown'));
      trend.history.forEach((week, index) => {
        const velocityColor = week.velocity > trend.summary.averageVelocity ? chalk.green : chalk.yellow;
        const bar = this.createProgressBar(week.velocity, trend.summary.averageVelocity * 2, 20);

        console.log(`${week.period.padEnd(8)} ${velocityColor.bold(week.velocity.toFixed(1).padStart(5))} pts/day ${bar} (${week.tasksCompleted} tasks)`);
      });

      console.log('\n');

    } catch (error) {
      console.error(chalk.red('❌ Error displaying velocity trend:'), error.message);
    }
  }

  /**
   * Generate comprehensive velocity report
   * @param {Object} options - Command options
   */
  async generateReport(options = {}) {
    try {
      const {
        period = 'week',
        output = null,
        includeDetails = true
      } = options;

      console.log(chalk.blue.bold('\n📋 Generating Velocity Report...\n'));

      const report = await this.service.generateVelocityReport({
        period,
        includeDetails
      });

      if (output) {
        // Save to file
        const fs = require('fs').promises;
        await fs.writeFile(output, JSON.stringify(report, null, 2));
        console.log(chalk.green(`✅ Report saved to: ${output}`));
      } else {
        // Display in console
        this.displayReport(report);
      }

    } catch (error) {
      console.error(chalk.red('❌ Error generating velocity report:'), error.message);
    }
  }

  /**
   * Display formatted report
   * @param {Object} report - Velocity report
   */
  displayReport(report) {
    console.log(chalk.blue.bold('📊 Velocity Report'));
    console.log(chalk.gray(`Generated: ${new Date(report.generatedAt).toLocaleString()}\n`));

    // Summary
    console.log(chalk.yellow.bold('📈 Executive Summary'));
    console.log(`Current Velocity:   ${chalk.green.bold(report.summary.currentVelocity.toFixed(1))} points/day`);
    console.log(`Tasks Completed:    ${chalk.cyan.bold(report.summary.tasksCompleted)}`);
    console.log(`Avg Cycle Time:     ${chalk.green.bold(report.summary.averageCycleTime.toFixed(1))} hours`);
    console.log(`Work in Progress:   ${chalk.yellow.bold(report.summary.workInProgress)}`);
    console.log(`Est. Completion:    ${chalk.green.bold(new Date(report.summary.estimatedCompletion).toLocaleDateString())}`);

    // Recommendations
    if (report.recommendations && report.recommendations.length > 0) {
      console.log(chalk.yellow.bold('\n💡 Recommendations'));
      report.recommendations.forEach(rec => {
        const icon = this.getPriorityIcon(rec.priority);
        const color = this.getPriorityColor(rec.priority);
        console.log(`${icon} ${color.bold(rec.type.toUpperCase())}: ${rec.message}`);
        console.log(`   ${chalk.gray('Action:')} ${rec.action}`);
      });
    }

    console.log('\n');
  }

  /**
   * Update task status with velocity tracking
   * @param {string|number} taskId - Task ID
   * @param {string} status - New status
   */
  async updateTaskStatus(taskId, status) {
    try {
      console.log(chalk.blue(`\n🔄 Updating task ${taskId} to ${status}...\n`));

      const result = await this.service.updateTaskStatus(taskId, status);

      console.log(chalk.green('✅ Task updated successfully!'));
      console.log(`Task: ${result.task.title}`);
      console.log(`Status: ${chalk.bold(result.statusChange.from)} → ${chalk.bold(result.statusChange.to)}`);
      console.log(`Timestamp: ${new Date(result.statusChange.timestamp).toLocaleString()}`);

      // Show velocity metadata if available
      if (result.task.velocity_metadata) {
        const vm = result.task.velocity_metadata;
        console.log(chalk.yellow.bold('\n📊 Velocity Metadata:'));
        console.log(`Complexity Score: ${vm.complexity_score}`);
        if (vm.actual_hours) {
          console.log(`Actual Hours: ${vm.actual_hours.toFixed(2)}`);
        }
        console.log(`Status History: ${vm.status_history.length} entries`);
      }

      console.log('\n');

    } catch (error) {
      console.error(chalk.red('❌ Error updating task status:'), error.message);
    }
  }

  /**
   * Display velocity dashboard with visualizations
   * @param {Object} options - Command options
   */
  async showDashboard(options = {}) {
    try {
      console.log(chalk.blue('🚀 Loading Velocity Dashboard...\n'));

      // Load user preferences
      const prefs = await this.preferences.load();

      // Get velocity metrics with user-preferred period
      const period = options.period || prefs.calculation.velocityPeriod || 'week';
      const days = period === 'week' ? 7 : period === 'month' ? 30 : 7;

      const metrics = await this.service.getVelocityMetrics({ days });
      const trend = await this.service.getVelocityTrend(prefs.calculation.trendAnalysisPeriod || 4);

      // Create dashboard with user preferences
      const dashboardOptions = {
        useColors: prefs.display.useColors,
        chartHeight: prefs.display.chartHeight,
        showTrend: prefs.display.showTrendIndicators,
        compactMode: prefs.display.compactMode
      };

      const dashboard = this.visualizer.createVelocityDashboard(metrics, trend, dashboardOptions);
      console.log(dashboard);

    } catch (error) {
      console.error(chalk.red('❌ Error generating dashboard:'), error.message);
    }
  }

  /**
   * Display velocity chart
   * @param {Object} options - Command options
   */
  async showChart(options = {}) {
    try {
      const { weeks = 4, type = 'velocity' } = options;

      console.log(chalk.blue.bold(`\n📈 Velocity Chart (${type})\n`));

      if (type === 'velocity') {
        const trend = await this.service.getVelocityTrend(weeks);
        const chart = this.visualizer.createVelocityChart(trend.history, {
          title: `Velocity Trend - Last ${weeks} Weeks`,
          showValues: true
        });
        console.log(chart);
      } else if (type === 'cycletime') {
        const metrics = await this.service.getVelocityMetrics({ days: weeks * 7 });
        const cycleTimes = metrics.tasks
          .map(t => t.cycleTime)
          .filter(ct => ct !== null && ct > 0);

        if (cycleTimes.length > 0) {
          const histogram = this.visualizer.createCycleTimeHistogram(cycleTimes, {
            title: 'Cycle Time Distribution',
            bins: 10
          });
          console.log(histogram);
        } else {
          console.log(chalk.yellow('⚠️  No cycle time data available for chart'));
        }
      } else if (type === 'burndown') {
        // Create sample burndown data (would be enhanced with real data)
        const metrics = await this.service.getVelocityMetrics({ days: weeks * 7 });
        const burndownData = [];
        const totalComplexity = metrics.estimates.totalComplexity + metrics.completed.totalComplexity;

        for (let i = 0; i <= weeks; i++) {
          const remaining = totalComplexity * (1 - (i / weeks));
          burndownData.push({
            period: `Week ${i + 1}`,
            remaining: Math.max(0, remaining)
          });
        }

        const chart = this.visualizer.createBurndownChart(burndownData, {
          title: 'Project Burndown Chart',
          showIdealLine: true
        });
        console.log(chart);
      }

    } catch (error) {
      console.error(chalk.red('❌ Error displaying velocity chart:'), error.message);
    }
  }

  /**
   * Manage velocity preferences
   * @param {Array} args - Command arguments
   */
  async manageConfig(args) {
    try {
      const { spawn } = require('child_process');

      // Delegate to preferences CLI
      const preferencesPath = require('path').join(__dirname, 'preferences-cli.js');
      const child = spawn('node', [preferencesPath, ...args], {
        stdio: 'inherit',
        cwd: process.cwd()
      });

      return new Promise((resolve) => {
        child.on('close', (code) => {
          resolve(code === 0);
        });
      });

    } catch (error) {
      console.error(chalk.red('❌ Error managing config:'), error.message);
      return false;
    }
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
      default: return '❓';
    }
  }

  /**
   * Get priority icon
   * @param {string} priority - Priority level
   * @returns {string} Icon
   */
  getPriorityIcon(priority) {
    switch (priority) {
      case 'high': return '🔴';
      case 'medium': return '🟡';
      case 'low': return '🟢';
      default: return '⚪';
    }
  }

  /**
   * Get priority color
   * @param {string} priority - Priority level
   * @returns {Function} Chalk color function
   */
  getPriorityColor(priority) {
    switch (priority) {
      case 'high': return chalk.red;
      case 'medium': return chalk.yellow;
      case 'low': return chalk.green;
      default: return chalk.gray;
    }
  }

  /**
   * Create a simple progress bar
   * @param {number} value - Current value
   * @param {number} max - Maximum value
   * @param {number} width - Bar width
   * @returns {string} Progress bar
   */
  createProgressBar(value, max, width = 20) {
    const percentage = Math.min(value / max, 1);
    const filled = Math.round(percentage * width);
    const empty = width - filled;

    return chalk.green('█'.repeat(filled)) + chalk.gray('░'.repeat(empty));
  }

  /**
   * Display help information
   */
  showHelp() {
    console.log(chalk.blue.bold('\n🚀 Velocity CLI Commands\n'));

    console.log(chalk.yellow.bold('📊 Metrics & Reporting:'));
    console.log('  velocity metrics [--period=week|month] [--days=7]');
    console.log('    Show current velocity metrics and cycle time stats');
    console.log('');
    console.log('  velocity trend [--weeks=4]');
    console.log('    Display velocity trend analysis over time');
    console.log('');
    console.log('  velocity report [--period=week|month] [--output=file.json]');
    console.log('    Generate comprehensive velocity report');
    console.log('');
    console.log('  velocity dashboard');
    console.log('    Display velocity dashboard with visualizations');
    console.log('');
    console.log('  velocity chart [--weeks=4] [--type=velocity|cycletime|burndown]');
    console.log('    Display velocity chart');
    console.log('');

    console.log(chalk.yellow.bold('🔄 Task Management:'));
    console.log('  velocity update-status --id=15 --status=done');
    console.log('    Update task status with velocity tracking');
    console.log('');

    console.log(chalk.yellow.bold('📖 Help:'));
    console.log('  velocity help');
    console.log('    Show this help information');
    console.log('');

    console.log(chalk.yellow.bold('📝 Configuration:'));
    console.log('  velocity config <command> [args]');
    console.log('    Manage velocity preferences (list|set|get|reset)');
    console.log('');

    console.log(chalk.gray('Examples:'));
    console.log(chalk.gray('  velocity metrics --period=month'));
    console.log(chalk.gray('  velocity trend --weeks=6'));
    console.log(chalk.gray('  velocity report --output=velocity-report.json'));
    console.log(chalk.gray('  velocity config list --section=display'));
    console.log(chalk.gray('  velocity config set display.useColors false'));
    console.log('');
  }
}

// CLI entry point
async function main() {
  const cli = new VelocityCLI();
  const args = process.argv.slice(2);

  if (args.length === 0) {
    cli.showHelp();
    return;
  }

  const command = args[0];
  const options = {};

  // Parse command line arguments
  for (let i = 1; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith('--')) {
      const [key, value] = arg.slice(2).split('=');
      if (value !== undefined) {
        // Handle numeric values
        const numValue = Number(value);
        options[key] = isNaN(numValue) ? value : numValue;
      } else {
        options[key] = true;
      }
    }
  }

  try {
    switch (command) {
      case 'metrics':
        await cli.showMetrics(options);
        break;
      case 'trend':
        await cli.showTrend(options);
        break;
      case 'report':
        await cli.generateReport(options);
        break;
      case 'dashboard':
        await cli.showDashboard(options);
        break;
      case 'chart':
        await cli.showChart(options);
        break;
      case 'update-status':
        if (!options.id || !options.status) {
          console.error(chalk.red('❌ Error: --id and --status are required'));
          process.exit(1);
        }
        await cli.updateTaskStatus(options.id, options.status);
        break;
      case 'config':
        await cli.manageConfig(args.slice(1));
        break;
      case 'help':
      default:
        cli.showHelp();
        break;
    }
  } catch (error) {
    console.error(chalk.red('❌ Command failed:'), error.message);
    process.exit(1);
  }
}

// Export for testing and integration
module.exports = VelocityCLI;

// Run CLI if called directly
if (require.main === module) {
  main().catch(console.error);
}
