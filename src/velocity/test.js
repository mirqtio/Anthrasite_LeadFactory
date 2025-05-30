/**
 * Simple test for velocity calculation logic
 */

const VelocityCalculator = require('./calculator');
const VelocityService = require('./service');

async function testVelocityCalculator() {
  console.log('🧪 Testing Velocity Calculator...\n');

  const calculator = new VelocityCalculator();

  // Test 1: Task Duration Calculation
  console.log('📊 Test 1: Task Duration Calculation');
  const startTime = '2025-05-29T10:00:00Z';
  const endTime = '2025-05-29T16:30:00Z';
  const duration = calculator.calculateTaskDuration(startTime, endTime);
  console.log(`Duration: ${duration} hours (expected: 6.5)`);
  console.log(`✅ ${duration === 6.5 ? 'PASS' : 'FAIL'}\n`);

  // Test 2: Velocity Rate Calculation
  console.log('📊 Test 2: Velocity Rate Calculation');
  const complexityScore = 7;
  const actualHours = 6.5;
  const velocityRate = calculator.calculateVelocityRate(complexityScore, actualHours);
  console.log(`Velocity Rate: ${velocityRate.toFixed(3)} points/hour (expected: ~1.077)`);
  console.log(`✅ ${Math.abs(velocityRate - 1.077) < 0.01 ? 'PASS' : 'FAIL'}\n`);

  // Test 3: Daily Velocity Calculation
  console.log('📊 Test 3: Daily Velocity Calculation');
  const completedTasks = [
    { velocity_metadata: { complexity_score: 5 } },
    { velocity_metadata: { complexity_score: 7 } },
    { velocity_metadata: { complexity_score: 3 } }
  ];
  const dailyVelocity = calculator.calculateDailyVelocity(completedTasks, 1);
  console.log(`Daily Velocity: ${dailyVelocity} points/day (expected: 15)`);
  console.log(`✅ ${dailyVelocity === 15 ? 'PASS' : 'FAIL'}\n`);

  // Test 4: ETC Calculation
  console.log('📊 Test 4: ETC Calculation');
  const remainingTasks = [
    { velocity_metadata: { complexity_score: 8 } },
    { velocity_metadata: { complexity_score: 5 } }
  ];
  const etc = calculator.calculateETC(remainingTasks, 10); // 10 points per day
  console.log(`ETC: ${etc.estimatedDays} days (expected: 1.3)`);
  console.log(`Total Complexity: ${etc.totalComplexity} (expected: 13)`);
  console.log(`✅ ${etc.totalComplexity === 13 && Math.abs(etc.estimatedDays - 1.3) < 0.01 ? 'PASS' : 'FAIL'}\n`);

  // Test 5: Cycle Time Stats
  console.log('📊 Test 5: Cycle Time Stats');
  const tasksWithTimes = [
    { started_at: '2025-05-29T10:00:00Z', completed_at: '2025-05-29T14:00:00Z' }, // 4 hours
    { started_at: '2025-05-29T09:00:00Z', completed_at: '2025-05-29T15:00:00Z' }, // 6 hours
    { started_at: '2025-05-29T11:00:00Z', completed_at: '2025-05-29T13:00:00Z' }  // 2 hours
  ];
  const cycleStats = calculator.calculateCycleTimeStats(tasksWithTimes);
  console.log(`Average Cycle Time: ${cycleStats.average} hours (expected: 4)`);
  console.log(`Median Cycle Time: ${cycleStats.median} hours (expected: 4)`);
  console.log(`Min: ${cycleStats.min}, Max: ${cycleStats.max} (expected: 2, 6)`);
  console.log(`✅ ${cycleStats.average === 4 && cycleStats.median === 4 ? 'PASS' : 'FAIL'}\n`);

  // Test 6: Status Update
  console.log('📊 Test 6: Status Update with Velocity Metadata');
  const task = {
    id: 15,
    status: 'pending',
    velocity_metadata: {
      complexity_score: 7,
      status_history: []
    }
  };

  const updatedTask = calculator.updateTaskVelocityMetadata(task, 'in-progress', '2025-05-29T10:00:00Z');
  console.log(`Started At: ${updatedTask.started_at}`);
  console.log(`Status History Length: ${updatedTask.velocity_metadata.status_history.length}`);
  console.log(`✅ ${updatedTask.started_at && updatedTask.velocity_metadata.status_history.length === 1 ? 'PASS' : 'FAIL'}\n`);

  console.log('🎉 Velocity Calculator Tests Complete!\n');
}

async function testVelocityService() {
  console.log('🧪 Testing Velocity Service...\n');

  try {
    const service = new VelocityService('tasks/tasks.json');

    // Test loading tasks
    console.log('📊 Test 1: Load Tasks');
    const tasks = await service.loadTasks();
    console.log(`Loaded ${tasks.length} tasks`);
    console.log(`✅ ${tasks.length > 0 ? 'PASS' : 'FAIL'}\n`);

    // Test finding task by ID
    console.log('📊 Test 2: Find Task by ID');
    const task15 = service.findTaskById(tasks, 15);
    console.log(`Found Task 15: ${task15 ? task15.title : 'Not found'}`);
    console.log(`✅ ${task15 && task15.title.includes('Velocity') ? 'PASS' : 'FAIL'}\n`);

    // Test finding subtask by ID
    console.log('📊 Test 3: Find Subtask by ID');
    const subtask151 = service.findTaskById(tasks, '15.1');
    console.log(`Found Subtask 15.1: ${subtask151 ? subtask151.title : 'Not found'}`);
    console.log(`✅ ${subtask151 && subtask151.title.includes('Data Model') ? 'PASS' : 'FAIL'}\n`);

    // Test flattening tasks
    console.log('📊 Test 4: Flatten Tasks');
    const flattened = service.flattenTasks(tasks);
    console.log(`Original tasks: ${tasks.length}, Flattened: ${flattened.length}`);
    console.log(`✅ ${flattened.length > tasks.length ? 'PASS' : 'FAIL'}\n`);

    console.log('🎉 Velocity Service Tests Complete!\n');

  } catch (error) {
    console.error('❌ Velocity Service Test Failed:', error.message);
  }
}

// Run tests
async function runAllTests() {
  console.log('🚀 Starting Velocity Calculation Tests\n');
  console.log('=' .repeat(50));

  await testVelocityCalculator();
  await testVelocityService();

  console.log('=' .repeat(50));
  console.log('✅ All tests completed!');
}

// Export for use in other modules or run directly
if (require.main === module) {
  runAllTests().catch(console.error);
}

module.exports = { testVelocityCalculator, testVelocityService, runAllTests };
