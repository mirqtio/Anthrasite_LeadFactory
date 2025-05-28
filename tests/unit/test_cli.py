"""
Unit tests for the CLI module.
"""
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import sys
import os

# Add the project root to the Python path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# Set PYTHONPATH environment variable
os.environ['PYTHONPATH'] = project_root

try:
    from leadfactory.cli.main import cli
    CLI_AVAILABLE = True
except ImportError as e:
    print(f"CLI import failed: {e}")
    CLI_AVAILABLE = False


@pytest.mark.skipif(not CLI_AVAILABLE, reason="CLI modules not available")
class TestCLI:
    """Test suite for CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_help(self):
        """Test that CLI help command works."""
        result = self.runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Anthrasite Lead Factory CLI' in result.output
        assert 'pipeline' in result.output
        assert 'admin' in result.output
        assert 'dev' in result.output

    def test_cli_version(self):
        """Test that CLI version command works."""
        result = self.runner.invoke(cli, ['--version'])
        assert result.exit_code == 0

    def test_pipeline_help(self):
        """Test that pipeline help command works."""
        result = self.runner.invoke(cli, ['pipeline', '--help'])
        assert result.exit_code == 0
        assert 'Pipeline operations' in result.output
        assert 'scrape' in result.output
        assert 'enrich' in result.output
        assert 'dedupe' in result.output
        assert 'email' in result.output

    def test_admin_help(self):
        """Test that admin help command works."""
        result = self.runner.invoke(cli, ['admin', '--help'])
        assert result.exit_code == 0
        assert 'Administrative operations' in result.output

    def test_dev_help(self):
        """Test that dev help command works."""
        result = self.runner.invoke(cli, ['dev', '--help'])
        assert result.exit_code == 0
        assert 'Development and testing operations' in result.output

    @patch('leadfactory.pipeline.scrape.main')
    def test_pipeline_scrape_command(self, mock_scrape_main):
        """Test that pipeline scrape command calls the correct function."""
        mock_scrape_main.return_value = None

        result = self.runner.invoke(cli, ['pipeline', 'scrape', '--limit', '10'])
        assert result.exit_code == 0
        mock_scrape_main.assert_called_once_with(limit=10, zip_code=None, vertical=None)

    @patch('leadfactory.pipeline.scrape.main')
    def test_pipeline_scrape_with_zip_code(self, mock_scrape_main):
        """Test that pipeline scrape command works with zip code."""
        mock_scrape_main.return_value = None

        result = self.runner.invoke(cli, ['pipeline', 'scrape', '--zip-code', '12345'])
        assert result.exit_code == 0
        mock_scrape_main.assert_called_once_with(limit=None, zip_code='12345', vertical=None)

    @patch('leadfactory.pipeline.enrich.main')
    def test_pipeline_enrich_command(self, mock_enrich_main):
        """Test that pipeline enrich command calls the correct function."""
        mock_enrich_main.return_value = None

        result = self.runner.invoke(cli, ['pipeline', 'enrich', '--limit', '5'])
        assert result.exit_code == 0
        mock_enrich_main.assert_called_once_with(limit=5, business_id=None, tier=None)

    @patch('leadfactory.pipeline.dedupe_unified.main')
    def test_pipeline_dedupe_command(self, mock_dedupe_main):
        """Test that pipeline dedupe command calls the correct function."""
        mock_dedupe_main.return_value = None

        result = self.runner.invoke(cli, ['pipeline', 'dedupe', '--limit', '100'])
        assert result.exit_code == 0
        mock_dedupe_main.assert_called_once_with(limit=100, threshold=0.8)

    @patch('leadfactory.pipeline.email_queue.main')
    def test_pipeline_email_command(self, mock_email_main):
        """Test that pipeline email command calls the correct function."""
        mock_email_main.return_value = None

        result = self.runner.invoke(cli, ['pipeline', 'email', '--limit', '20'])
        assert result.exit_code == 0
        mock_email_main.assert_called_once_with(limit=20, business_id=None, force=False)

    def test_verbose_flag(self):
        """Test that verbose flag is properly handled."""
        result = self.runner.invoke(cli, ['--verbose', '--help'])
        assert result.exit_code == 0

    def test_dry_run_flag(self):
        """Test that dry-run flag is properly handled."""
        result = self.runner.invoke(cli, ['--dry-run', '--help'])
        assert result.exit_code == 0

    @patch('leadfactory.pipeline.scrape.main')
    def test_error_handling(self, mock_scrape_main):
        """Test that CLI handles errors gracefully."""
        mock_scrape_main.side_effect = Exception("Test error")

        result = self.runner.invoke(cli, ['pipeline', 'scrape'])
        # Should handle the error gracefully, not crash
        assert result.exit_code != 0 or "Test error" in result.output


# Simple test that doesn't require imports
class TestCLIBasic:
    """Basic CLI tests that work without complex imports."""

    def test_cli_module_exists(self):
        """Test that CLI module files exist."""
        cli_main_path = os.path.join(project_root, 'leadfactory', 'cli', 'main.py')
        assert os.path.exists(cli_main_path), "CLI main module should exist"

        commands_dir = os.path.join(project_root, 'leadfactory', 'cli', 'commands')
        assert os.path.exists(commands_dir), "CLI commands directory should exist"

        pipeline_commands_path = os.path.join(commands_dir, 'pipeline_commands.py')
        assert os.path.exists(pipeline_commands_path), "Pipeline commands module should exist"

    def test_cli_imports_work(self):
        """Test that CLI can be imported."""
        try:
            from leadfactory.cli.main import cli
            assert cli is not None
        except ImportError:
            pytest.fail("CLI module should be importable")


if __name__ == '__main__':
    pytest.main([__file__])
