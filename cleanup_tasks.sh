#!/bin/bash

# Script to clean up auto-generated tasks
echo "Starting cleanup of auto-generated tasks..."

# Read task IDs from file and remove them
while IFS= read -r task_id; do
    if [ ! -z "$task_id" ]; then
        echo "Removing task $task_id..."
        task-master remove-task --id="$task_id" -y
    fi
done < tasks_to_remove.txt

echo "Cleanup complete!"
