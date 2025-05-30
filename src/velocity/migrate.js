#!/usr/bin/env node

/**
 * Velocity Migration Script
 * Migrates existing tasks to include velocity tracking metadata
 */

const VelocityIntegration = require('./integration');
const chalk = require('chalk');

async function runMigration() {
  console.log(chalk.blue.bold('\n🔄 Velocity Metadata Migration\n'));

  const integration = new VelocityIntegration();

  try {
    // Check if this is a dry run
    const isDryRun = process.argv.includes('--dry-run');

    if (isDryRun) {
      console.log(chalk.yellow('🔍 Running in dry-run mode - no changes will be made\n'));
    }

    // Run migration
    const result = await integration.migrateTasksToVelocity(isDryRun);

    console.log(chalk.green.bold('\n✅ Migration completed successfully!'));
    console.log(`📊 Tasks enhanced with velocity metadata: ${chalk.cyan.bold(result.migrationCount)}`);
    console.log(`🔧 Additional fields added: ${chalk.cyan.bold(result.enhancementCount)}`);

    if (isDryRun) {
      console.log(chalk.yellow('\n💡 Run without --dry-run to apply changes'));
    } else if (result.migrationCount > 0 || result.enhancementCount > 0) {
      console.log(chalk.green('\n🎉 Your tasks now have velocity tracking enabled!'));
      console.log(chalk.gray('You can now use velocity commands like:'));
      console.log(chalk.gray('  node src/velocity/cli.js metrics'));
      console.log(chalk.gray('  node src/velocity/cli.js dashboard'));
    }

  } catch (error) {
    console.error(chalk.red.bold('\n❌ Migration failed:'), error.message);
    process.exit(1);
  }
}

// Show help
function showHelp() {
  console.log(chalk.blue.bold('\n🔄 Velocity Migration Script\n'));
  console.log('Usage:');
  console.log('  node src/velocity/migrate.js [options]\n');
  console.log('Options:');
  console.log('  --dry-run    Show what would be changed without making changes');
  console.log('  --help       Show this help message\n');
  console.log('Examples:');
  console.log('  node src/velocity/migrate.js --dry-run');
  console.log('  node src/velocity/migrate.js\n');
}

// Parse command line arguments
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  showHelp();
} else {
  runMigration().catch(console.error);
}
