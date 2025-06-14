#!/bin/bash
# Script to reproduce CI linting locally for diagnostics

# Output directory for diagnostic results
OUTDIR="ci_lint_diagnostics"
mkdir -p $OUTDIR

echo "Generating list of files to check..."
# Generate a cleaner list of files to check, ensuring they exist
find . \( -name ".venv" -o -name "venv" \) -prune -o -type f -name "*.py" -print | \
  grep -v "tests/" | grep -v ".cursor/" | grep -v ".github/workflows/" | \
  grep -v "bin/enrich.py" | grep -v "bin/dedupe.py" | \
  grep -v ".git/" | grep -v "archive/" > $OUTDIR/all_files.txt

# Create a clean file list with only existing files
> $OUTDIR/files_to_check.txt
while read -r file; do
  if [ -f "$file" ]; then
    echo "$file" >> $OUTDIR/files_to_check.txt
  else
    echo "Warning: File does not exist: $file" >&2
  fi
done < $OUTDIR/all_files.txt

FILES_TO_LINT=$(cat $OUTDIR/files_to_check.txt | tr '\n' ' ')
if [ -z "$FILES_TO_LINT" ]; then
  echo "No files to lint based on files_to_check.txt. Exiting."
  exit 0
fi

echo "Running Ruff..."
ruff check --ignore F722 $FILES_TO_LINT --fix > $OUTDIR/ruff_output.txt 2>&1
echo "Ruff exit code: $?" >> $OUTDIR/ruff_output.txt

echo "Running Black..."
black --quiet $FILES_TO_LINT > $OUTDIR/black_output.txt 2>&1
echo "Black exit code: $?" >> $OUTDIR/black_output.txt

echo "Running Bandit..."
bandit -r . -x tests,venv,.venv -ll > $OUTDIR/bandit_output.txt 2>&1
echo "Bandit exit code: $?" >> $OUTDIR/bandit_output.txt

echo "Running Flake8..."
flake8 $FILES_TO_LINT > $OUTDIR/flake8_output.txt 2>&1
echo "Flake8 exit code: $?" >> $OUTDIR/flake8_output.txt

echo "Running Mypy..."
# Run mypy on specific directories instead of individual files
mypy bin/ utils/ scripts/ --config-file=mypy.ini > $OUTDIR/mypy_output.txt 2>&1
MYPY_EXIT=$?
echo "Mypy exit code: $MYPY_EXIT" >> $OUTDIR/mypy_output.txt

echo "Diagnostic run complete. Check the $OUTDIR directory for detailed outputs."
echo "Summary of exit codes:"
for tool in ruff black bandit flake8 mypy; do
  exitcode=$(grep "exit code" $OUTDIR/${tool}_output.txt | awk '{print $NF}')
  echo "$tool: $exitcode"
done
