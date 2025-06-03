/**
 * Velocity Calculator Module
 * Core logic for calculating task velocity metrics and estimates
 */

class VelocityCalculator {
  constructor() {
    this.HOURS_PER_DAY = 8; // Standard work day
    this.MS_PER_HOUR = 1000 * 60 * 60;
    this.MS_PER_DAY = this.MS_PER_HOUR * 24;
  }

  /**
   * Calculate task duration in hours
   * @param {string} startedAt - ISO timestamp when task started
   * @param {string} completedAt - ISO timestamp when task completed
   * @returns {number} Duration in hours
   */
  calculateTaskDuration(startedAt, completedAt) {
    if (!startedAt || !completedAt) {
      return null;
    }

    const start = new Date(startedAt);
    const end = new Date(completedAt);
    const durationMs = end.getTime() - start.getTime();

    return durationMs / this.MS_PER_HOUR;
  }

  /**
   * Calculate velocity rate (complexity points per hour)
   * @param {number} complexityScore - Task complexity points
   * @param {number} actualHours - Time taken to complete
   * @returns {number} Velocity rate
   */
  calculateVelocityRate(complexityScore, actualHours) {
    if (!complexityScore || !actualHours || actualHours <= 0) {
      return null;
    }

    return complexityScore / actualHours;
  }

  /**
   * Calculate daily velocity from completed tasks
   * @param {Array} completedTasks - Array of completed tasks with velocity metadata
   * @param {number} daysPeriod - Number of days to calculate over
   * @returns {number} Daily velocity (complexity points per day)
   */
  calculateDailyVelocity(completedTasks, daysPeriod = 1) {
    if (!completedTasks || completedTasks.length === 0) {
      return 0;
    }

    const totalComplexity = completedTasks.reduce((sum, task) => {
      const complexity = task.velocity_metadata?.complexity_score || task.velocity_metadata?.velocity_points || 5;
      return sum + complexity;
    }, 0);

    return totalComplexity / daysPeriod;
  }

  /**
   * Calculate estimated time to completion for remaining tasks
   * @param {Array} remainingTasks - Array of pending/in-progress tasks
   * @param {number} dailyVelocity - Current daily velocity
   * @returns {Object} ETC estimates
   */
  calculateETC(remainingTasks, dailyVelocity) {
    if (!remainingTasks || remainingTasks.length === 0) {
      return {
        totalComplexity: 0,
        estimatedDays: 0,
        estimatedHours: 0,
        completionDate: new Date()
      };
    }

    const totalComplexity = remainingTasks.reduce((sum, task) => {
      const complexity = task.velocity_metadata?.complexity_score || task.velocity_metadata?.velocity_points || 5;
      return sum + complexity;
    }, 0);

    const estimatedDays = dailyVelocity > 0 ? totalComplexity / dailyVelocity : 0;
    const estimatedHours = estimatedDays * this.HOURS_PER_DAY;

    const completionDate = new Date();
    completionDate.setDate(completionDate.getDate() + Math.ceil(estimatedDays));

    return {
      totalComplexity,
      estimatedDays: Math.round(estimatedDays * 100) / 100, // Round to 2 decimals
      estimatedHours: Math.round(estimatedHours * 100) / 100,
      completionDate
    };
  }

  /**
   * Calculate velocity trend over time periods
   * @param {Array} velocityHistory - Array of {period, velocity} objects
   * @returns {Object} Trend analysis
   */
  calculateVelocityTrend(velocityHistory) {
    if (!velocityHistory || velocityHistory.length < 2) {
      return {
        trend: 'insufficient_data',
        changePercent: 0,
        direction: 'stable'
      };
    }

    const recent = velocityHistory[velocityHistory.length - 1];
    const previous = velocityHistory[velocityHistory.length - 2];

    if (previous.velocity === 0) {
      return {
        trend: 'new_baseline',
        changePercent: 0,
        direction: recent.velocity > 0 ? 'improving' : 'stable'
      };
    }

    const changePercent = ((recent.velocity - previous.velocity) / previous.velocity) * 100;

    let direction = 'stable';
    if (changePercent > 5) direction = 'improving';
    else if (changePercent < -5) direction = 'declining';

    return {
      trend: 'calculated',
      changePercent: Math.round(changePercent * 100) / 100,
      direction
    };
  }

  /**
   * Calculate cycle time statistics
   * @param {Array} completedTasks - Array of completed tasks
   * @returns {Object} Cycle time stats
   */
  calculateCycleTimeStats(completedTasks) {
    if (!completedTasks || completedTasks.length === 0) {
      return {
        average: 0,
        median: 0,
        min: 0,
        max: 0,
        count: 0
      };
    }

    const cycleTimes = completedTasks
      .map(task => {
        if (task.started_at && task.completed_at) {
          return this.calculateTaskDuration(task.started_at, task.completed_at);
        }
        return null;
      })
      .filter(time => time !== null)
      .sort((a, b) => a - b);

    if (cycleTimes.length === 0) {
      return {
        average: 0,
        median: 0,
        min: 0,
        max: 0,
        count: 0
      };
    }

    const sum = cycleTimes.reduce((acc, time) => acc + time, 0);
    const average = sum / cycleTimes.length;
    const median = cycleTimes.length % 2 === 0
      ? (cycleTimes[cycleTimes.length / 2 - 1] + cycleTimes[cycleTimes.length / 2]) / 2
      : cycleTimes[Math.floor(cycleTimes.length / 2)];

    return {
      average: Math.round(average * 100) / 100,
      median: Math.round(median * 100) / 100,
      min: cycleTimes[0],
      max: cycleTimes[cycleTimes.length - 1],
      count: cycleTimes.length
    };
  }

  /**
   * Calculate lead time (creation to completion)
   * @param {string} createdAt - ISO timestamp when task was created
   * @param {string} completedAt - ISO timestamp when task completed
   * @returns {number} Lead time in hours
   */
  calculateLeadTime(createdAt, completedAt) {
    if (!createdAt || !completedAt) {
      return null;
    }

    const created = new Date(createdAt);
    const completed = new Date(completedAt);
    const leadTimeMs = completed.getTime() - created.getTime();

    return leadTimeMs / this.MS_PER_HOUR;
  }

  /**
   * Calculate work in progress metrics
   * @param {Array} tasks - All tasks
   * @returns {Object} WIP metrics
   */
  calculateWIPMetrics(tasks) {
    const wipTasks = tasks.filter(task => task.status === 'in-progress');
    const totalComplexity = wipTasks.reduce((sum, task) => {
      const complexity = task.velocity_metadata?.complexity_score || task.velocity_metadata?.velocity_points || 5;
      return sum + complexity;
    }, 0);

    return {
      count: wipTasks.length,
      totalComplexity,
      averageComplexity: wipTasks.length > 0 ? totalComplexity / wipTasks.length : 0,
      tasks: wipTasks.map(task => ({
        id: task.id,
        title: task.title,
        complexity: task.velocity_metadata?.complexity_score || task.velocity_metadata?.velocity_points || 5,
        startedAt: task.started_at
      }))
    };
  }

  /**
   * Update task velocity metadata when status changes
   * @param {Object} task - Task object
   * @param {string} newStatus - New status
   * @param {string} timestamp - Current timestamp
   * @returns {Object} Updated task with velocity metadata
   */
  updateTaskVelocityMetadata(task, newStatus, timestamp = new Date().toISOString()) {
    // Initialize velocity metadata if it doesn't exist
    if (!task.velocity_metadata) {
      task.velocity_metadata = {
        complexity_score: 5,
        estimated_hours: null,
        actual_hours: null,
        velocity_points: 5,
        blocked_time: 0,
        status_history: []
      };
    }

    // Update timestamps based on status
    if (newStatus === 'in-progress' && !task.started_at) {
      task.started_at = timestamp;
    }

    if (newStatus === 'done' && !task.completed_at) {
      task.completed_at = timestamp;

      // Calculate actual hours if we have start and end times
      if (task.started_at) {
        task.velocity_metadata.actual_hours = this.calculateTaskDuration(task.started_at, task.completed_at);
      }
    }

    // Always update last_updated
    task.last_updated = timestamp;

    // Ensure status_history exists
    if (!task.velocity_metadata.status_history) {
      task.velocity_metadata.status_history = [];
    }

    // Add to status history
    const lastEntry = task.velocity_metadata.status_history[task.velocity_metadata.status_history.length - 1];

    // Update duration of previous status
    if (lastEntry && lastEntry.duration_hours === null) {
      const previousTimestamp = new Date(lastEntry.timestamp);
      const currentTimestamp = new Date(timestamp);
      lastEntry.duration_hours = (currentTimestamp.getTime() - previousTimestamp.getTime()) / this.MS_PER_HOUR;
    }

    // Add new status entry
    task.velocity_metadata.status_history.push({
      status: newStatus,
      timestamp: timestamp,
      duration_hours: null // Will be calculated when status changes again
    });

    return task;
  }
}

module.exports = VelocityCalculator;
