"""
Tests for pipeline CLI commands.

This module tests all pipeline-related CLI commands including scrape, enrich,
dedupe, email, score, and mockup operations.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import click
import pytest
from click.testing import CliRunner

from leadfactory.cli.commands import pipeline_commands


class TestPipelineCommands:
    """Test cases for pipeline CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("leadfactory.cli.commands.pipeline_commands.get_storage")
    @patch("leadfactory.cli.commands.pipeline_commands.scrape_business")
    def test_scrape_command_basic(self, mock_scrape, mock_get_storage):
        """Test basic scrape command."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_scrape.return_value = {"id": 1, "name": "Test Business"}

        result = self.runner.invoke(
            pipeline_commands.scrape,
            ["--url", "https://example.com"]
        )

        assert result.exit_code == 0
        mock_scrape.assert_called_once()
        assert "Scraped business" in result.output

    @patch("leadfactory.cli.commands.pipeline_commands.get_storage")
    @patch("leadfactory.cli.commands.pipeline_commands.scrape_business")
    def test_scrape_command_with_options(self, mock_scrape, mock_get_storage):
        """Test scrape command with various options."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_scrape.return_value = {"id": 1, "name": "Test Business"}

        result = self.runner.invoke(
            pipeline_commands.scrape,
            [
                "--url", "https://example.com",
                "--source", "yelp",
                "--category", "restaurant",
                "--force"
            ]
        )

        assert result.exit_code == 0

    def test_scrape_command_batch_file(self):
        """Test scrape command with batch file."""
        with self.runner.isolated_filesystem():
            # Create a test batch file
            batch_file = Path("urls.txt")
            batch_file.write_text("https://example1.com\nhttps://example2.com\n")

            with patch("leadfactory.cli.commands.pipeline_commands.scrape_business") as mock_scrape:
                mock_scrape.return_value = {"id": 1, "name": "Test"}

                result = self.runner.invoke(
                    pipeline_commands.scrape,
                    ["--batch", str(batch_file)]
                )

                assert result.exit_code == 0
                assert mock_scrape.call_count == 2

    @patch("leadfactory.cli.commands.pipeline_commands.get_storage")
    @patch("leadfactory.cli.commands.pipeline_commands.enrich_business")
    def test_enrich_command(self, mock_enrich, mock_get_storage):
        """Test enrich command."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.get_business_by_id.return_value = {"id": 1, "name": "Test"}
        mock_enrich.return_value = {"id": 1, "enriched": True}

        result = self.runner.invoke(
            pipeline_commands.enrich,
            ["--business-id", "1"]
        )

        assert result.exit_code == 0
        mock_enrich.assert_called_once()

    @patch("leadfactory.cli.commands.pipeline_commands.get_storage")
    def test_enrich_command_batch(self, mock_get_storage):
        """Test enrich command with batch processing."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.get_businesses_by_criteria.return_value = [
            {"id": 1, "name": "Business 1"},
            {"id": 2, "name": "Business 2"}
        ]

        with patch("leadfactory.cli.commands.pipeline_commands.enrich_business") as mock_enrich:
            mock_enrich.return_value = {"enriched": True}

            result = self.runner.invoke(
                pipeline_commands.enrich,
                ["--batch", "--limit", "10"]
            )

            assert result.exit_code == 0
            assert mock_enrich.call_count >= 2

    @patch("leadfactory.cli.commands.pipeline_commands.DedupeService")
    def test_dedupe_command(self, mock_dedupe_class):
        """Test dedupe command."""
        mock_dedupe = MagicMock()
        mock_dedupe_class.return_value = mock_dedupe
        mock_dedupe.run_deduplication.return_value = {
            "duplicates_found": 5,
            "businesses_merged": 3
        }

        result = self.runner.invoke(
            pipeline_commands.dedupe,
            ["--strategy", "conservative"]
        )

        assert result.exit_code == 0
        mock_dedupe.run_deduplication.assert_called_once()

    def test_dedupe_command_dry_run(self):
        """Test dedupe command in dry-run mode."""
        with patch("leadfactory.cli.commands.pipeline_commands.DedupeService") as mock_dedupe_class:
            mock_dedupe = MagicMock()
            mock_dedupe_class.return_value = mock_dedupe
            mock_dedupe.preview_deduplication.return_value = {
                "potential_duplicates": 10
            }

            result = self.runner.invoke(
                pipeline_commands.dedupe,
                ["--dry-run"]
            )

            assert result.exit_code == 0
            mock_dedupe.preview_deduplication.assert_called_once()

    @patch("leadfactory.cli.commands.pipeline_commands.get_storage")
    @patch("leadfactory.cli.commands.pipeline_commands.EmailService")
    def test_email_command(self, mock_email_class, mock_get_storage):
        """Test email command."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.get_businesses_for_email.return_value = [
            {"id": 1, "email": "test@example.com", "name": "Test Business"}
        ]

        mock_email_service = MagicMock()
        mock_email_class.return_value = mock_email_service
        mock_email_service.send_email.return_value = True

        result = self.runner.invoke(
            pipeline_commands.email,
            ["--template", "default", "--limit", "10"]
        )

        assert result.exit_code == 0
        mock_email_service.send_email.assert_called()

    def test_email_command_test_mode(self):
        """Test email command in test mode."""
        with patch("leadfactory.cli.commands.pipeline_commands.EmailService") as mock_email_class:
            mock_email_service = MagicMock()
            mock_email_class.return_value = mock_email_service

            result = self.runner.invoke(
                pipeline_commands.email,
                ["--test", "--test-email", "test@example.com"]
            )

            assert result.exit_code == 0
            mock_email_service.send_test_email.assert_called_once()

    @patch("leadfactory.cli.commands.pipeline_commands.get_storage")
    @patch("leadfactory.cli.commands.pipeline_commands.ScoringEngine")
    def test_score_command(self, mock_scoring_class, mock_get_storage):
        """Test score command."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.get_business_by_id.return_value = {
            "id": 1, "name": "Test Business", "vertical": "restaurant"
        }

        mock_scoring = MagicMock()
        mock_scoring_class.return_value = mock_scoring
        mock_scoring.score_business.return_value = {
            "score": 85,
            "confidence": 0.9
        }

        result = self.runner.invoke(
            pipeline_commands.score,
            ["--business-id", "1"]
        )

        assert result.exit_code == 0
        mock_scoring.score_business.assert_called_once()

    def test_score_command_batch(self):
        """Test score command with batch processing."""
        with patch("leadfactory.cli.commands.pipeline_commands.get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_get_storage.return_value = mock_storage
            mock_storage.get_businesses_by_criteria.return_value = [
                {"id": 1, "name": "Business 1"},
                {"id": 2, "name": "Business 2"}
            ]

            with patch("leadfactory.cli.commands.pipeline_commands.ScoringEngine") as mock_scoring_class:
                mock_scoring = MagicMock()
                mock_scoring_class.return_value = mock_scoring
                mock_scoring.score_business.return_value = {"score": 75}

                result = self.runner.invoke(
                    pipeline_commands.score,
                    ["--batch", "--vertical", "restaurant"]
                )

                assert result.exit_code == 0
                assert mock_scoring.score_business.call_count >= 2

    @patch("leadfactory.cli.commands.pipeline_commands.get_storage")
    @patch("leadfactory.cli.commands.pipeline_commands.MockupService")
    def test_mockup_command(self, mock_mockup_class, mock_get_storage):
        """Test mockup command."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.get_business_by_id.return_value = {
            "id": 1,
            "name": "Test Business",
            "website": "https://example.com"
        }
        mock_storage.get_business_asset.return_value = {
            "url": "https://example.com/screenshot.png"
        }

        mock_mockup = MagicMock()
        mock_mockup_class.return_value = mock_mockup
        mock_mockup.generate_mockup.return_value = {
            "mockup_url": "https://example.com/mockup.png"
        }

        result = self.runner.invoke(
            pipeline_commands.mockup,
            ["--business-id", "1"]
        )

        assert result.exit_code == 0
        mock_mockup.generate_mockup.assert_called_once()

    def test_mockup_command_batch(self):
        """Test mockup command with batch processing."""
        with patch("leadfactory.cli.commands.pipeline_commands.get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_get_storage.return_value = mock_storage
            mock_storage.get_businesses_needing_mockups.return_value = [
                {"id": 1, "name": "Business 1"},
                {"id": 2, "name": "Business 2"}
            ]

            with patch("leadfactory.cli.commands.pipeline_commands.MockupService") as mock_mockup_class:
                mock_mockup = MagicMock()
                mock_mockup_class.return_value = mock_mockup
                mock_mockup.generate_mockup.return_value = {"mockup_url": "https://example.com/mockup.png"}

                result = self.runner.invoke(
                    pipeline_commands.mockup,
                    ["--batch", "--limit", "10"]
                )

                assert result.exit_code == 0
                assert mock_mockup.generate_mockup.call_count >= 2

    def test_command_error_handling(self):
        """Test error handling in pipeline commands."""
        with patch("leadfactory.cli.commands.pipeline_commands.scrape_business") as mock_scrape:
            mock_scrape.side_effect = Exception("Scraping failed")

            result = self.runner.invoke(
                pipeline_commands.scrape,
                ["--url", "https://example.com"]
            )

            assert result.exit_code != 0
            assert "Error" in result.output

    def test_progress_reporting(self):
        """Test progress reporting in batch operations."""
        with patch("leadfactory.cli.commands.pipeline_commands.get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_get_storage.return_value = mock_storage

            # Return many businesses to test progress
            mock_storage.get_businesses_by_criteria.return_value = [
                {"id": i, "name": f"Business {i}"} for i in range(100)
            ]

            with patch("leadfactory.cli.commands.pipeline_commands.enrich_business") as mock_enrich:
                mock_enrich.return_value = {"enriched": True}

                result = self.runner.invoke(
                    pipeline_commands.enrich,
                    ["--batch", "--show-progress"]
                )

                # Progress indicators should be in output
                assert "Processing" in result.output or "Progress" in result.output

    def test_output_formats(self):
        """Test different output formats."""
        with patch("leadfactory.cli.commands.pipeline_commands.scrape_business") as mock_scrape:
            mock_scrape.return_value = {"id": 1, "name": "Test Business"}

            # Test JSON output
            result = self.runner.invoke(
                pipeline_commands.scrape,
                ["--url", "https://example.com", "--output-format", "json"]
            )

            assert result.exit_code == 0
            # Output should be valid JSON
            output_data = json.loads(result.output.strip())
            assert isinstance(output_data, dict)

    def test_parallel_processing(self):
        """Test parallel processing option."""
        with patch("leadfactory.cli.commands.pipeline_commands.get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_get_storage.return_value = mock_storage
            mock_storage.get_businesses_by_criteria.return_value = [
                {"id": i, "name": f"Business {i}"} for i in range(10)
            ]

            with patch("leadfactory.cli.commands.pipeline_commands.enrich_business") as mock_enrich:
                mock_enrich.return_value = {"enriched": True}

                result = self.runner.invoke(
                    pipeline_commands.enrich,
                    ["--batch", "--parallel", "--workers", "4"]
                )

                assert result.exit_code == 0
