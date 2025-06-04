"""
Automated tests for roadmap documentation validation.

This module provides comprehensive testing for the project roadmap documentation
to ensure accuracy, format consistency, and integration with the project structure.
"""

import re
import unittest
from pathlib import Path
from unittest.mock import patch


class TestRoadmapDocumentation(unittest.TestCase):
    """Test suite for roadmap documentation validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.docs_dir = Path(__file__).parent.parent.parent / "docs"
        self.roadmap_file = self.docs_dir / "project-roadmap.md"

        # Ensure the roadmap file exists
        if not self.roadmap_file.exists():
            self.fail(f"Roadmap file not found: {self.roadmap_file}")

        with open(self.roadmap_file, 'r', encoding='utf-8') as f:
            self.roadmap_content = f.read()

    def test_roadmap_file_exists(self):
        """Test that the roadmap file exists and is readable."""
        self.assertTrue(self.roadmap_file.exists(), "Roadmap file should exist")
        self.assertTrue(self.roadmap_file.is_file(), "Roadmap should be a file")
        self.assertGreater(len(self.roadmap_content), 1000, "Roadmap should have substantial content")

    def test_required_sections_present(self):
        """Test that all required sections are present in the roadmap."""
        required_sections = [
            "# Anthrasite LeadFactory Project Roadmap",
            "## Table of Contents",
            "## Executive Summary",
            "## Business Model Evolution",
            "## Completed: Phase 0",
            "## Current Phase",
            "## Next Phase",
            "## Future Phases",
            "## Strategic Priorities",
            "## Success Metrics & KPIs",
            "## Risk Management"
        ]

        for section in required_sections:
            with self.subTest(section=section):
                self.assertIn(section, self.roadmap_content,
                             f"Required section '{section}' not found in roadmap")

    def test_business_model_evolution_content(self):
        """Test that business model evolution section reflects audit-first model."""
        audit_first_keywords = [
            "audit-first",
            "revenue generation",
            "direct audit sales",
            "Customer Lifetime Value",
            "conversion funnel",
            "Stripe integration"
        ]

        for keyword in audit_first_keywords:
            with self.subTest(keyword=keyword):
                self.assertIn(keyword.lower(), self.roadmap_content.lower(),
                             f"Audit-first keyword '{keyword}' not found in roadmap")

    def test_current_tasks_referenced(self):
        """Test that current tasks (31, 32) are properly referenced."""
        task_references = [
            "Task 31",
            "Task 32",
            "Purchase Metrics",
            "Roadmap Documentation"
        ]

        for task_ref in task_references:
            with self.subTest(task_ref=task_ref):
                self.assertIn(task_ref, self.roadmap_content,
                             f"Current task reference '{task_ref}' not found")

    def test_next_priority_tasks_identified(self):
        """Test that next priority tasks (29, 30) are properly identified."""
        next_tasks = [
            "Task 29",
            "Task 30",
            "YAML Scoring Rules",
            "NodeCapability Defaults"
        ]

        for task in next_tasks:
            with self.subTest(task=task):
                self.assertIn(task, self.roadmap_content,
                             f"Next priority task '{task}' not found")

    def test_timeline_consistency(self):
        """Test that timeline references are consistent and realistic."""
        # Check for timeline references
        timeline_patterns = [
            r"Q[1-4]\s+2025",
            r"2026",
            r"June\s+2025",
            r"Timeline.*Q[1-4]\s+2025"
        ]

        for pattern in timeline_patterns:
            with self.subTest(pattern=pattern):
                self.assertTrue(re.search(pattern, self.roadmap_content),
                               f"Timeline pattern '{pattern}' not found")

    def test_markdown_format_validation(self):
        """Test markdown formatting is correct."""
        # Check for proper heading hierarchy
        heading_pattern = r'^#{1,6}\s+.+$'
        headings = re.findall(heading_pattern, self.roadmap_content, re.MULTILINE)
        self.assertGreater(len(headings), 10, "Should have multiple headings")

        # Check for proper table formatting
        table_pattern = r'\|.*\|.*\|'
        tables = re.findall(table_pattern, self.roadmap_content)
        self.assertGreater(len(tables), 0, "Should have at least one table")

        # Check for proper link formatting
        link_pattern = r'\[.*\]\(#.*\)'
        links = re.findall(link_pattern, self.roadmap_content)
        self.assertGreater(len(links), 5, "Should have multiple internal links")

    def test_table_of_contents_links(self):
        """Test that Table of Contents links are valid."""
        # Extract TOC links
        toc_links = re.findall(r'\[.*\]\(#([^)]+)\)', self.roadmap_content)

        # Check that each TOC link has a corresponding heading
        for link_anchor in toc_links:
            # Convert anchor to expected heading format
            expected_heading = link_anchor.replace('-', ' ').title()

            # Check if a similar heading exists (case insensitive)
            heading_found = False
            for line in self.roadmap_content.split('\n'):
                if line.startswith('#') and expected_heading.lower() in line.lower():
                    heading_found = True
                    break

            with self.subTest(anchor=link_anchor):
                self.assertTrue(heading_found,
                               f"TOC link '{link_anchor}' has no corresponding heading")

    def test_mermaid_diagram_syntax(self):
        """Test that Mermaid diagram syntax is valid."""
        mermaid_pattern = r'```mermaid\n(.*?)```'
        mermaid_blocks = re.findall(mermaid_pattern, self.roadmap_content, re.DOTALL)

        self.assertGreater(len(mermaid_blocks), 0, "Should have at least one Mermaid diagram")

        for block in mermaid_blocks:
            with self.subTest(block=block[:50]):
                # Basic validation - should contain gantt keywords
                self.assertIn('gantt', block.lower(), "Mermaid block should contain gantt diagram")
                self.assertIn('title', block.lower(), "Mermaid diagram should have a title")

    def test_success_metrics_specificity(self):
        """Test that success metrics are specific and measurable."""
        metrics_keywords = [
            "Target",
            "%",
            "$",
            "CLV",
            "CAC",
            "MRR",
            "99.9%"
        ]

        # Find the Success Metrics section
        metrics_section_match = re.search(
            r'## Success Metrics & KPIs.*?(?=## |\Z)',
            self.roadmap_content,
            re.DOTALL
        )

        self.assertIsNotNone(metrics_section_match, "Success Metrics section should exist")
        metrics_content = metrics_section_match.group(0)

        for keyword in metrics_keywords:
            with self.subTest(keyword=keyword):
                self.assertIn(keyword, metrics_content,
                             f"Success metrics should contain '{keyword}'")

    def test_document_metadata(self):
        """Test that document metadata is present and current."""
        metadata_patterns = [
            r'Document created:.*2025',
            r'Last updated:.*2025',
            r'Business Model Updated:.*Audit-First'
        ]

        for pattern in metadata_patterns:
            with self.subTest(pattern=pattern):
                self.assertTrue(re.search(pattern, self.roadmap_content),
                               f"Document metadata pattern '{pattern}' not found")

    def test_cross_references_to_other_docs(self):
        """Test that cross-references to other documentation are valid."""
        # This is a basic test - in a full implementation, we'd check if referenced files exist
        doc_references = re.findall(r'\[.*\]\(([^#)]+\.md)\)', self.roadmap_content)

        for doc_ref in doc_references:
            with self.subTest(doc_ref=doc_ref):
                referenced_file = self.docs_dir / doc_ref
                self.assertTrue(referenced_file.exists() or doc_ref.startswith('http'),
                               f"Referenced document '{doc_ref}' should exist or be a URL")

    def test_spelling_and_grammar_basic(self):
        """Basic spelling and grammar validation."""
        # Check for common spelling errors in business/tech context
        common_errors = [
            ('recieve', 'receive'),
            ('seperate', 'separate'),
            ('occured', 'occurred'),
            ('developement', 'development'),
            ('busines', 'business')
        ]

        for wrong, correct in common_errors:
            with self.subTest(error=wrong):
                self.assertNotIn(wrong, self.roadmap_content.lower(),
                                f"Common spelling error '{wrong}' found (should be '{correct}')")

    def test_content_completeness(self):
        """Test that the roadmap content is comprehensive and complete."""
        # Check word count
        word_count = len(self.roadmap_content.split())
        self.assertGreater(word_count, 2000,
                          "Roadmap should be comprehensive (>2000 words)")

        # Check for key business concepts
        business_concepts = [
            "revenue", "customer", "profit", "market", "competitive",
            "scalability", "performance", "security", "compliance"
        ]

        for concept in business_concepts:
            with self.subTest(concept=concept):
                self.assertIn(concept.lower(), self.roadmap_content.lower(),
                             f"Business concept '{concept}' should be covered")


class TestDocumentationIntegration(unittest.TestCase):
    """Test integration between roadmap and project structure."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent.parent
        self.roadmap_file = self.project_root / "docs" / "project-roadmap.md"

        with open(self.roadmap_file, 'r', encoding='utf-8') as f:
            self.roadmap_content = f.read()

    def test_task_references_align_with_task_files(self):
        """Test that task references in roadmap align with actual task files."""
        # This test would check if referenced tasks exist in the task management system
        task_references = re.findall(r'Task (\d+)', self.roadmap_content)

        self.assertGreater(len(task_references), 0,
                          "Should reference specific task numbers")

        # Check for key tasks mentioned in the roadmap
        key_tasks = ['29', '30', '31', '32']
        for task_num in key_tasks:
            with self.subTest(task=task_num):
                self.assertIn(f'Task {task_num}', self.roadmap_content,
                             f"Task {task_num} should be referenced in roadmap")

    def test_technology_stack_alignment(self):
        """Test that technology references align with actual implementation."""
        tech_references = [
            "Prometheus", "Stripe", "PDF", "CLI", "Supabase",
            "YAML", "SendGrid", "GPT-4", "Python"
        ]

        for tech in tech_references:
            with self.subTest(tech=tech):
                self.assertIn(tech, self.roadmap_content,
                             f"Technology '{tech}' should be mentioned in roadmap")


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
