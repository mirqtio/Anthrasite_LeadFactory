#!/usr/bin/env node

/**
 * Task Master with Velocity Integration
 * Wrapper that adds velocity tracking to task-master commands
 */

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';
import velocityEnhancedList from './velocity-list.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Get command line arguments
const args = process.argv.slice(2);
const command = args[0];

/**
 * Handle velocity-enhanced commands
 */
async function handleCommand() {
    switch (command) {
        case 'list':
        case 'ls':
            // Use our velocity-enhanced list command
            const listOptions = {};

            // Parse list-specific arguments
            for (let i = 1; i < args.length; i++) {
                if (args[i] === '--status' && args[i + 1]) {
                    listOptions.status = args[i + 1];
                    i++;
                } else if (args[i] === '--with-subtasks') {
                    listOptions.withSubtasks = true;
                } else if (args[i] === '--no-velocity') {
                    listOptions.showVelocity = false;
                }
            }

            await velocityEnhancedList(listOptions);
            break;

        case 'velocity':
            // Handle velocity-specific commands
            const velocityCommand = args[1];
            switch (velocityCommand) {
                case 'dashboard':
                    await runVelocityCommand(['dashboard']);
                    break;
                case 'summary':
                    await runVelocityCommand(['summary']);
                    break;
                case 'metrics':
                    await runVelocityCommand(['metrics']);
                    break;
                case 'trend':
                    await runVelocityCommand(['trend']);
                    break;
                case 'preferences':
                    await runVelocityCommand(['preferences', ...args.slice(2)]);
                    break;
                default:
                    console.log('Available velocity commands:');
                    console.log('  velocity dashboard  - Show velocity dashboard');
                    console.log('  velocity summary    - Show velocity summary');
                    console.log('  velocity metrics    - Show detailed metrics');
                    console.log('  velocity trend      - Show trend analysis');
                    console.log('  velocity preferences - Manage preferences');
                    break;
            }
            break;

        default:
            // Pass through to original task-master for all other commands
            await runTaskMaster(args);
            break;
    }
}

/**
 * Run velocity CLI command
 */
async function runVelocityCommand(velocityArgs) {
    return new Promise((resolve, reject) => {
        const velocityCliPath = resolve(__dirname, '../src/velocity/cli.js');
        const child = spawn('node', [velocityCliPath, ...velocityArgs], {
            stdio: 'inherit',
            cwd: process.cwd()
        });

        child.on('close', (code) => {
            if (code === 0) {
                resolve();
            } else {
                reject(new Error(`Velocity command failed with code ${code}`));
            }
        });
    });
}

/**
 * Run original task-master command
 */
async function runTaskMaster(taskMasterArgs) {
    return new Promise((resolve, reject) => {
        const child = spawn('task-master', taskMasterArgs, {
            stdio: 'inherit',
            cwd: process.cwd()
        });

        child.on('close', (code) => {
            if (code === 0) {
                resolve();
            } else {
                reject(new Error(`Task-master command failed with code ${code}`));
            }
        });
    });
}

// Show help if no command provided
if (!command) {
    console.log('Task Master with Velocity Tracking');
    console.log('');
    console.log('Enhanced Commands:');
    console.log('  list [options]      - List tasks with velocity metrics');
    console.log('  velocity <command>  - Velocity tracking commands');
    console.log('');
    console.log('Standard Commands:');
    console.log('  All other task-master commands work as normal');
    console.log('');
    console.log('Examples:');
    console.log('  task-master-velocity list --status=pending');
    console.log('  task-master-velocity velocity dashboard');
    console.log('  task-master-velocity set-status --id=1 --status=done');
    process.exit(0);
}

// Execute the command
handleCommand().catch(error => {
    console.error('Error:', error.message);
    process.exit(1);
});
