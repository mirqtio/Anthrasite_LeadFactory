/**
 * Velocity Integration Module
 * Integrates velocity tracking with existing task-master CLI
 */

const fs = require('fs').promises;
const path = require('path');
const VelocityService = require('./service');

class VelocityIntegration {
  constructor(tasksFilePath = 'tasks/tasks.json') {
    this.tasksFilePath = tasksFilePath;
    this.velocityService = new VelocityService(tasksFilePath);
  }

  /**
   * Hook into task status changes to update velocity metadata
   * This should be called whenever a task status is updated
   * @param {number|string} taskId - Task ID
   * @param {string} oldStatus - Previous status
   * @param {string} newStatus - New status
   * @param {string} timestamp - Optional timestamp
   */
  async onTaskStatusChange(taskId, oldStatus, newStatus, timestamp = new Date().toISOString()) {
    try {
      // Load current tasks
      const tasks = await this.velocityService.loadTasks();
      const task = this.velocityService.findTaskById(tasks, taskId);

      if (!task) {
        console.warn(`[Velocity] Task ${taskId} not found for velocity tracking`);
        return;
      }

      // Initialize velocity metadata if it doesn't exist
      if (!task.velocity_metadata) {
        task.velocity_metadata = {
          complexity_score: this.estimateComplexity(task),
          estimated_hours: null,
          actual_hours: null,
          velocity_points: this.estimateComplexity(task),
          blocked_time: 0,
          status_history: []
        };
      }

      // Update velocity metadata
      this.velocityService.calculator.updateTaskVelocityMetadata(task, newStatus, timestamp);

      // Save updated tasks
      await this.velocityService.saveTasks(tasks);

      // Log velocity tracking info
      console.log(`[Velocity] Updated task ${taskId} velocity metadata (${oldStatus} → ${newStatus})`);

      // Generate velocity insights if task is completed
      if (newStatus === 'done' && task.velocity_metadata.actual_hours) {
        this.logCompletionInsights(task);
      }

      return task;

    } catch (error) {
      console.error(`[Velocity] Error updating velocity metadata for task ${taskId}:`, error.message);
      return null;
    }
  }

  /**
   * Estimate complexity score for a task based on its properties
   * @param {Object} task - Task object
   * @returns {number} Complexity score (1-10)
   */
  estimateComplexity(task) {
    let complexity = 5; // Default medium complexity

    // Adjust based on task title/description keywords
    const text = (task.title + ' ' + (task.details || '')).toLowerCase();

    // High complexity indicators
    if (text.includes('implement') || text.includes('develop') || text.includes('create')) {
      complexity += 1;
    }
    if (text.includes('comprehensive') || text.includes('complex') || text.includes('advanced')) {
      complexity += 2;
    }
    if (text.includes('integration') || text.includes('system') || text.includes('architecture')) {
      complexity += 1;
    }

    // Low complexity indicators
    if (text.includes('update') || text.includes('fix') || text.includes('minor')) {
      complexity -= 1;
    }
    if (text.includes('documentation') || text.includes('readme') || text.includes('comment')) {
      complexity -= 1;
    }

    // Adjust based on dependencies
    if (task.dependencies && task.dependencies.length > 3) {
      complexity += 1;
    }

    // Adjust based on subtasks
    if (task.subtasks && task.subtasks.length > 5) {
      complexity += 2;
    } else if (task.subtasks && task.subtasks.length > 0) {
      complexity += 1;
    }

    // Clamp to valid range
    return Math.max(1, Math.min(10, complexity));
  }

  /**
   * Log completion insights for a completed task
   * @param {Object} task - Completed task
   */
  logCompletionInsights(task) {
    const vm = task.velocity_metadata;
    const velocityRate = this.velocityService.calculator.calculateVelocityRate(
      vm.complexity_score,
      vm.actual_hours
    );

    console.log(`[Velocity] Task ${task.id} completed:`);
    console.log(`  Complexity: ${vm.complexity_score} points`);
    console.log(`  Actual time: ${vm.actual_hours.toFixed(2)} hours`);
    console.log(`  Velocity rate: ${velocityRate.toFixed(2)} points/hour`);
  }

  /**
   * Enhance task list with velocity information
   * @param {Array} tasks - Array of tasks
   * @returns {Array} Enhanced tasks with velocity info
   */
  async enhanceTasksWithVelocity(tasks) {
    const enhancedTasks = [];

    for (const task of tasks) {
      const enhanced = { ...task };

      // Add velocity metadata if it doesn't exist
      if (!enhanced.velocity_metadata) {
        enhanced.velocity_metadata = {
          complexity_score: this.estimateComplexity(task),
          estimated_hours: null,
          actual_hours: null,
          velocity_points: this.estimateComplexity(task),
          blocked_time: 0,
          status_history: []
        };
      }

      // Add calculated velocity metrics
      if (enhanced.started_at && enhanced.completed_at) {
        enhanced.cycle_time = this.velocityService.calculator.calculateTaskDuration(
          enhanced.started_at,
          enhanced.completed_at
        );
      }

      if (enhanced.created_at && enhanced.completed_at) {
        enhanced.lead_time = this.velocityService.calculator.calculateLeadTime(
          enhanced.created_at,
          enhanced.completed_at
        );
      }

      // Enhance subtasks recursively
      if (enhanced.subtasks && Array.isArray(enhanced.subtasks)) {
        enhanced.subtasks = await this.enhanceTasksWithVelocity(enhanced.subtasks);
      }

      enhancedTasks.push(enhanced);
    }

    return enhancedTasks;
  }

  /**
   * Generate velocity summary for task list command
   * @returns {Object} Velocity summary
   */
  async generateVelocitySummary() {
    try {
      const metrics = await this.velocityService.getVelocityMetrics({ days: 7 });
      const trend = await this.velocityService.getVelocityTrend(4);

      return {
        dailyVelocity: metrics.velocity.daily,
        tasksCompleted: metrics.completed.count,
        averageCycleTime: metrics.cycleTime.average,
        workInProgress: metrics.workInProgress.count,
        estimatedCompletion: metrics.estimates.completionDate,
        trend: trend.trend.direction,
        trendChange: trend.trend.changePercent
      };
    } catch (error) {
      console.error('[Velocity] Error generating velocity summary:', error.message);
      return null;
    }
  }

  /**
   * Add velocity commands to existing CLI
   * @param {Object} program - Commander.js program or similar CLI framework
   */
  addVelocityCommands(program) {
    // Add velocity subcommand group
    const velocityCmd = program
      .command('velocity')
      .description('Velocity tracking and reporting commands');

    velocityCmd
      .command('metrics')
      .description('Show velocity metrics')
      .option('--period <period>', 'Time period (week|month)', 'week')
      .option('--days <days>', 'Number of days', parseInt)
      .action(async (options) => {
        const { VelocityCLI } = require('./cli');
        const cli = new VelocityCLI();
        await cli.showMetrics(options);
      });

    velocityCmd
      .command('trend')
      .description('Show velocity trend')
      .option('--weeks <weeks>', 'Number of weeks', parseInt, 4)
      .action(async (options) => {
        const { VelocityCLI } = require('./cli');
        const cli = new VelocityCLI();
        await cli.showTrend(options);
      });

    velocityCmd
      .command('dashboard')
      .description('Show velocity dashboard')
      .option('--period <period>', 'Time period (week|month)', 'week')
      .action(async (options) => {
        const { VelocityCLI } = require('./cli');
        const cli = new VelocityCLI();
        await cli.showDashboard(options);
      });

    velocityCmd
      .command('report')
      .description('Generate velocity report')
      .option('--period <period>', 'Time period (week|month)', 'week')
      .option('--output <file>', 'Output file path')
      .action(async (options) => {
        const { VelocityCLI } = require('./cli');
        const cli = new VelocityCLI();
        await cli.generateReport(options);
      });

    return program;
  }

  /**
   * Create a wrapper for the existing set-status command
   * @param {Function} originalSetStatus - Original set-status function
   * @returns {Function} Enhanced set-status function
   */
  wrapSetStatusCommand(originalSetStatus) {
    return async (taskId, newStatus, options = {}) => {
      // Get old status before change
      const tasks = await this.velocityService.loadTasks();
      const task = this.velocityService.findTaskById(tasks, taskId);
      const oldStatus = task ? task.status : null;

      // Call original set-status command
      const result = await originalSetStatus(taskId, newStatus, options);

      // Update velocity metadata
      if (oldStatus !== newStatus) {
        await this.onTaskStatusChange(taskId, oldStatus, newStatus);
      }

      return result;
    };
  }

  /**
   * Migrate existing tasks to include velocity metadata
   * @param {boolean} dryRun - If true, only show what would be changed
   */
  async migrateTasksToVelocity(dryRun = false) {
    try {
      console.log('[Velocity] Starting velocity metadata migration...');

      const tasks = await this.velocityService.loadTasks();
      let migrationCount = 0;
      let enhancementCount = 0;

      const migrateTasks = (taskList) => {
        taskList.forEach(task => {
          // Add velocity metadata if missing
          if (!task.velocity_metadata) {
            task.velocity_metadata = {
              complexity_score: this.estimateComplexity(task),
              estimated_hours: null,
              actual_hours: null,
              velocity_points: this.estimateComplexity(task),
              blocked_time: 0,
              status_history: []
            };
            migrationCount++;
          }

          // Add timestamps if missing
          if (!task.created_at) {
            task.created_at = new Date().toISOString();
            enhancementCount++;
          }

          if (!task.last_updated) {
            task.last_updated = new Date().toISOString();
            enhancementCount++;
          }

          // Initialize status history if empty
          if (!task.velocity_metadata.status_history) {
            task.velocity_metadata.status_history = [];
          }

          if (task.velocity_metadata.status_history.length === 0 && task.status) {
            task.velocity_metadata.status_history.push({
              status: task.status,
              timestamp: task.last_updated || new Date().toISOString(),
              duration_hours: null
            });
            enhancementCount++;
          }

          // Migrate subtasks
          if (task.subtasks && Array.isArray(task.subtasks)) {
            migrateTasks(task.subtasks);
          }
        });
      };

      migrateTasks(tasks);

      console.log(`[Velocity] Migration summary:`);
      console.log(`  Tasks with new velocity metadata: ${migrationCount}`);
      console.log(`  Enhanced fields added: ${enhancementCount}`);

      if (!dryRun && (migrationCount > 0 || enhancementCount > 0)) {
        await this.velocityService.saveTasks(tasks);
        console.log('[Velocity] Migration completed successfully!');
      } else if (dryRun) {
        console.log('[Velocity] Dry run completed - no changes made');
      } else {
        console.log('[Velocity] No migration needed - all tasks already have velocity metadata');
      }

      return { migrationCount, enhancementCount };

    } catch (error) {
      console.error('[Velocity] Migration failed:', error.message);
      throw error;
    }
  }
}

module.exports = VelocityIntegration;
