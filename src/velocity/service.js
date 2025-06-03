/**
 * Velocity Service Module
 * High-level service for velocity tracking operations
 */

const fs = require('fs').promises;
const path = require('path');
const VelocityCalculator = require('./calculator');

class VelocityService {
  constructor(tasksFilePath = 'tasks/tasks.json') {
    this.tasksFilePath = tasksFilePath;
    this.calculator = new VelocityCalculator();
  }

  /**
   * Load tasks from file
   * @returns {Array} Array of tasks
   */
  async loadTasks() {
    try {
      const data = await fs.readFile(this.tasksFilePath, 'utf8');
      const tasks = JSON.parse(data);

      // Handle both array format and object format
      if (Array.isArray(tasks)) {
        return tasks;
      } else if (tasks && typeof tasks === 'object') {
        // If it's an object, look for common task array properties
        return tasks.tasks || tasks.data || Object.values(tasks).filter(item =>
          item && typeof item === 'object' && item.id !== undefined
        );
      }

      return [];
    } catch (error) {
      console.warn(`[Velocity] Warning: Could not load tasks from ${this.tasksFilePath}:`, error.message);
      return [];
    }
  }

  /**
   * Save tasks to JSON file
   * @param {Array} tasks - Array of tasks to save
   */
  async saveTasks(tasks) {
    try {
      const data = { tasks };
      await fs.writeFile(this.tasksFilePath, JSON.stringify(data, null, 2));
    } catch (error) {
      console.error('Error saving tasks:', error.message);
      throw error;
    }
  }

  /**
   * Update task status and velocity metadata
   * @param {number} taskId - Task ID
   * @param {string} newStatus - New status
   * @param {string} timestamp - Optional timestamp
   * @returns {Object} Updated task
   */
  async updateTaskStatus(taskId, newStatus, timestamp = new Date().toISOString()) {
    const tasks = await this.loadTasks();
    const task = this.findTaskById(tasks, taskId);

    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    const oldStatus = task.status;
    task.status = newStatus;

    // Update velocity metadata
    this.calculator.updateTaskVelocityMetadata(task, newStatus, timestamp);

    await this.saveTasks(tasks);

    return {
      task,
      statusChange: {
        from: oldStatus,
        to: newStatus,
        timestamp
      }
    };
  }

  /**
   * Find task by ID (supports nested subtasks)
   * @param {Array} tasks - Array of tasks
   * @param {string|number} taskId - Task ID (can be "15.1" format)
   * @returns {Object|null} Found task or null
   */
  findTaskById(tasks, taskId) {
    const idStr = String(taskId);

    // Handle subtask IDs like "15.1"
    if (idStr.includes('.')) {
      const [parentId, subtaskId] = idStr.split('.');
      const parentTask = tasks.find(t => t.id === parseInt(parentId));
      if (parentTask && parentTask.subtasks) {
        return parentTask.subtasks.find(st => st.id === parseInt(subtaskId));
      }
      return null;
    }

    // Handle regular task IDs
    return tasks.find(t => t.id === parseInt(taskId));
  }

  /**
   * Get velocity metrics for a time period
   * @param {Object} options - Options for velocity calculation
   * @returns {Object} Velocity metrics
   */
  async getVelocityMetrics(options = {}) {
    const {
      days = 7,
      includeSubtasks = true,
      status = ['done'],
      endDate = new Date()
    } = options;

    const tasks = await this.loadTasks();
    const allTasks = includeSubtasks ? this.flattenTasks(tasks) : tasks;

    // Filter tasks by status and date range
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - days);

    const filteredTasks = allTasks.filter(task => {
      if (!status.includes(task.status)) return false;

      if (task.completed_at) {
        const completedDate = new Date(task.completed_at);
        return completedDate >= startDate && completedDate <= endDate;
      }

      return false;
    });

    // Calculate metrics
    const dailyVelocity = this.calculator.calculateDailyVelocity(filteredTasks, days);
    const cycleTimeStats = this.calculator.calculateCycleTimeStats(filteredTasks);
    const wipMetrics = this.calculator.calculateWIPMetrics(allTasks);

    // Get remaining tasks for ETC calculation
    const remainingTasks = allTasks.filter(task =>
      ['pending', 'in-progress'].includes(task.status)
    );
    const etc = this.calculator.calculateETC(remainingTasks, dailyVelocity);

    return {
      period: {
        days,
        startDate: startDate.toISOString(),
        endDate: endDate.toISOString()
      },
      velocity: {
        daily: dailyVelocity,
        weekly: dailyVelocity * 7,
        monthly: dailyVelocity * 30
      },
      completed: {
        count: filteredTasks.length,
        totalComplexity: filteredTasks.reduce((sum, task) => {
          return sum + (task.velocity_metadata?.complexity_score || task.velocity_metadata?.velocity_points || 5);
        }, 0)
      },
      cycleTime: cycleTimeStats,
      workInProgress: wipMetrics,
      estimates: etc,
      tasks: filteredTasks.map(task => ({
        id: task.id,
        title: task.title,
        complexity: task.velocity_metadata?.complexity_score || task.velocity_metadata?.velocity_points || 5,
        cycleTime: task.started_at && task.completed_at
          ? this.calculator.calculateTaskDuration(task.started_at, task.completed_at)
          : null,
        leadTime: task.created_at && task.completed_at
          ? this.calculator.calculateLeadTime(task.created_at, task.completed_at)
          : null
      }))
    };
  }

  /**
   * Get velocity trend analysis
   * @param {number} weeks - Number of weeks to analyze
   * @returns {Object} Trend analysis
   */
  async getVelocityTrend(weeks = 4) {
    const tasks = await this.loadTasks();
    const allTasks = this.flattenTasks(tasks);

    const velocityHistory = [];
    const endDate = new Date();

    for (let i = weeks - 1; i >= 0; i--) {
      const weekEnd = new Date(endDate);
      weekEnd.setDate(weekEnd.getDate() - (i * 7));

      const weekStart = new Date(weekEnd);
      weekStart.setDate(weekStart.getDate() - 7);

      const weekTasks = allTasks.filter(task => {
        if (task.status !== 'done' || !task.completed_at) return false;

        const completedDate = new Date(task.completed_at);
        return completedDate >= weekStart && completedDate <= weekEnd;
      });

      const weeklyVelocity = this.calculator.calculateDailyVelocity(weekTasks, 7);

      velocityHistory.push({
        period: `Week ${weeks - i}`,
        startDate: weekStart.toISOString(),
        endDate: weekEnd.toISOString(),
        velocity: weeklyVelocity,
        tasksCompleted: weekTasks.length,
        totalComplexity: weekTasks.reduce((sum, task) => {
          return sum + (task.velocity_metadata?.complexity_score || task.velocity_metadata?.velocity_points || 5);
        }, 0)
      });
    }

    const trend = this.calculator.calculateVelocityTrend(velocityHistory);

    return {
      weeks,
      history: velocityHistory,
      trend,
      summary: {
        averageVelocity: velocityHistory.reduce((sum, week) => sum + week.velocity, 0) / weeks,
        totalTasksCompleted: velocityHistory.reduce((sum, week) => sum + week.tasksCompleted, 0),
        totalComplexityCompleted: velocityHistory.reduce((sum, week) => sum + week.totalComplexity, 0)
      }
    };
  }

  /**
   * Flatten tasks to include subtasks
   * @param {Array} tasks - Array of tasks
   * @returns {Array} Flattened array including subtasks
   */
  flattenTasks(tasks) {
    const flattened = [];

    tasks.forEach(task => {
      flattened.push(task);

      if (task.subtasks && Array.isArray(task.subtasks)) {
        task.subtasks.forEach(subtask => {
          // Add parent reference for context
          flattened.push({
            ...subtask,
            parentId: task.id,
            id: `${task.id}.${subtask.id}`
          });
        });
      }
    });

    return flattened;
  }

  /**
   * Generate velocity report
   * @param {Object} options - Report options
   * @returns {Object} Comprehensive velocity report
   */
  async generateVelocityReport(options = {}) {
    const {
      period = 'week',
      includeDetails = true,
      format = 'json'
    } = options;

    const days = period === 'week' ? 7 : period === 'month' ? 30 : 7;

    const [metrics, trend] = await Promise.all([
      this.getVelocityMetrics({ days }),
      this.getVelocityTrend(4)
    ]);

    const report = {
      generatedAt: new Date().toISOString(),
      period: period,
      summary: {
        currentVelocity: metrics.velocity.daily,
        tasksCompleted: metrics.completed.count,
        averageCycleTime: metrics.cycleTime.average,
        workInProgress: metrics.workInProgress.count,
        estimatedCompletion: metrics.estimates.completionDate
      },
      metrics,
      trend
    };

    if (includeDetails) {
      report.recommendations = this.generateRecommendations(metrics, trend);
    }

    return report;
  }

  /**
   * Generate recommendations based on velocity data
   * @param {Object} metrics - Current velocity metrics
   * @param {Object} trend - Velocity trend data
   * @returns {Array} Array of recommendations
   */
  generateRecommendations(metrics, trend) {
    const recommendations = [];

    // WIP recommendations
    if (metrics.workInProgress.count > 5) {
      recommendations.push({
        type: 'wip_limit',
        priority: 'high',
        message: `Consider reducing Work in Progress. Current WIP: ${metrics.workInProgress.count} tasks.`,
        action: 'Focus on completing existing tasks before starting new ones.'
      });
    }

    // Velocity trend recommendations
    if (trend.trend.direction === 'declining') {
      recommendations.push({
        type: 'velocity_decline',
        priority: 'medium',
        message: `Velocity has declined by ${Math.abs(trend.trend.changePercent)}% recently.`,
        action: 'Review recent blockers and process improvements.'
      });
    } else if (trend.trend.direction === 'improving') {
      recommendations.push({
        type: 'velocity_improvement',
        priority: 'low',
        message: `Great job! Velocity has improved by ${trend.trend.changePercent}%.`,
        action: 'Document what\'s working well to maintain this improvement.'
      });
    }

    // Cycle time recommendations
    if (metrics.cycleTime.average > 24) { // More than 3 work days
      recommendations.push({
        type: 'cycle_time',
        priority: 'medium',
        message: `Average cycle time is ${metrics.cycleTime.average.toFixed(1)} hours.`,
        action: 'Consider breaking down large tasks into smaller, more manageable pieces.'
      });
    }

    return recommendations;
  }
}

module.exports = VelocityService;
