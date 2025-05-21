#!/usr/bin/env python3
"""
Script to fix PEP8 issues in test_dedupe_simple.py.
"""


def fix_dedupe_simple():
    """Fix PEP8 issues in test_dedupe_simple.py."""
    file_path = "tests/test_dedupe_simple.py"

    with open(file_path, "r") as f:
        lines = f.readlines()

    fixed_lines = []
    for line in lines:
        # Fix trailing whitespace
        line = line.rstrip() + "\n"

        # Fix long lines with comments about mocking
        if "Since we're mocking process_duplicate_pair, manually update the database" in line:
            line = line.replace(
                "Since we're mocking process_duplicate_pair, manually update the database",
                "Since we're mocking process_duplicate_pair, manually update the DB",
            )

        if "to reflect what would have happened if the function was actually called" in line:
            line = line.replace(
                "to reflect what would have happened if the function was actually called",
                "to reflect what would happen if function was actually called",
            )

        if "Update the businesses table to show one business was merged into the other" in line:
            line = line.replace(
                "Update the businesses table to show one business was merged into the other",
                "Update businesses table to show one business merged into other",
            )

        # Fix long lines with candidate_duplicate_pairs
        if (
            "(business1_id, business2_id, similarity_score, status, verified_by_llm, llm_confidence, llm_reasoning)"
            in line
        ):
            line = line.replace(
                "(business1_id, business2_id, similarity_score, status, verified_by_llm, llm_confidence, llm_reasoning)",
                "(business1_id, business2_id, similarity_score, status, verified_by_llm,\n         llm_confidence, llm_reasoning)",
            )

        # Fix long assertion messages
        if "Expected flag_for_review not to be called for processed businesses" in line:
            line = line.replace(
                "Expected flag_for_review not to be called for processed businesses",
                "Expected flag_for_review not to be called for processed businesses"[:88],
            )

        if "Expected a 'Deduplication completed' message, got: {log_messages}" in line:
            line = line.replace(
                "Expected a 'Deduplication completed' message, got: {log_messages}",
                "Expected 'Deduplication completed' message, got: {log_messages}",
            )

        fixed_lines.append(line)

    with open(file_path, "w") as f:
        f.writelines(fixed_lines)

    print(f"Fixed PEP8 issues in {file_path}")


if __name__ == "__main__":
    fix_dedupe_simple()
