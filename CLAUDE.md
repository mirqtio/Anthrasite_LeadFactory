- No task is complete unless all systems tests pass (not just the ones for the task you are working on), and code has been merged to main and validated by checking CI logs in GitHub via CLI. If local tests passed but CI failed, determine why and ensure parity between local and CI instead of looping through slow CI runs.
- If CI runs longer than 10 minutes, it is most likely hung and should be cancelled. Troubleshoot the issue by ensuring local matches CI and everything passes local, then try again.
- Compact every 30 minutes to prevent memory crashes.
