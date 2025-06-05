"""
Tests for the main CLI module.

This module tests the main CLI entry point and command registration.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from leadfactory.cli.main import cli


class TestCLIMain:
    """Test cases for the main CLI module."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_help(self):
        """Test CLI help command."""
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Anthrasite Lead Factory CLI" in result.output
        assert "Commands:" in result.output
        assert "pipeline" in result.output
        assert "admin" in result.output
        assert "dev" in result.output
        assert "analytics" in result.output

    def test_cli_version(self):
        """Test CLI version command."""
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        # Version string should be in output

    def test_cli_verbose_flag(self):
        """Test CLI verbose flag."""
        with patch("leadfactory.cli.main.logging"):
            result = self.runner.invoke(cli, ["--verbose", "--help"])
            assert result.exit_code == 0
            # Logging should be configured with DEBUG level

    def test_cli_dry_run_flag(self):
        """Test CLI dry-run flag."""
        result = self.runner.invoke(cli, ["--dry-run", "--help"])
        assert result.exit_code == 0

    def test_pipeline_group(self):
        """Test pipeline command group."""
        result = self.runner.invoke(cli, ["pipeline", "--help"])
        assert result.exit_code == 0
        assert "Pipeline operations for lead generation" in result.output
        # Check for pipeline subcommands
        assert "scrape" in result.output
        assert "enrich" in result.output
        assert "dedupe" in result.output
        assert "email" in result.output
        assert "score" in result.output
        assert "mockup" in result.output

    def test_admin_group(self):
        """Test admin command group."""
        result = self.runner.invoke(cli, ["admin", "--help"])
        assert result.exit_code == 0
        assert "Administrative operations" in result.output
        # Check for admin subcommands
        assert "db-setup" in result.output
        assert "migrate" in result.output
        assert "backup" in result.output

    def test_dev_group(self):
        """Test dev command group."""
        result = self.runner.invoke(cli, ["dev", "--help"])
        assert result.exit_code == 0
        assert "Development and testing operations" in result.output
        # Check for dev subcommands
        assert "test" in result.output
        assert "lint" in result.output
        assert "format-code" in result.output

    def test_analytics_group(self):
        """Test analytics command group."""
        result = self.runner.invoke(cli, ["analytics", "--help"])
        assert result.exit_code == 0
        assert "Business analytics and metrics" in result.output
        # Check for analytics subcommands
        assert "purchase" in result.output

    def test_invalid_command(self):
        """Test CLI with invalid command."""
        result = self.runner.invoke(cli, ["invalid-command"])
        assert result.exit_code != 0
        assert "Error" in result.output or "No such command" in result.output

    def test_context_passing(self):
        """Test that context is properly set up and passed."""
        # Create a test command to verify context
        @cli.command()
        @click.pass_context
        def test_context(ctx):
            """Test command to verify context."""
            assert isinstance(ctx.obj, dict)
            assert "verbose" in ctx.obj
            assert "dry_run" in ctx.obj
            click.echo("Context OK")

        result = self.runner.invoke(cli, ["--verbose", "--dry-run", "test_context"])
        assert "Context OK" in result.output

    @patch("leadfactory.cli.main.load_dotenv")
    def test_environment_loading(self, mock_load_dotenv):
        """Test that environment variables are loaded."""
        # Import should trigger load_dotenv
        import leadfactory.cli.main
        mock_load_dotenv.assert_called()

    def test_project_path_setup(self):
        """Test that project root is added to sys.path."""
        # This is done at import time in the actual module
        import leadfactory.cli.main
        project_root = Path(leadfactory.cli.main.__file__).resolve().parent.parent.parent
        assert str(project_root) in sys.path

    def test_command_registration(self):
        """Test that all commands are properly registered."""
        # Get all registered commands
        pipeline_commands = cli.commands["pipeline"].commands
        admin_commands = cli.commands["admin"].commands
        dev_commands = cli.commands["dev"].commands
        analytics_commands = cli.commands["analytics"].commands

        # Verify pipeline commands
        assert "scrape" in pipeline_commands
        assert "enrich" in pipeline_commands
        assert "dedupe" in pipeline_commands
        assert "email" in pipeline_commands
        assert "score" in pipeline_commands
        assert "mockup" in pipeline_commands

        # Verify admin commands
        assert "db-setup" in admin_commands
        assert "migrate" in admin_commands
        assert "backup" in admin_commands

        # Verify dev commands
        assert "test" in dev_commands
        assert "lint" in dev_commands
        assert "format-code" in dev_commands

        # Verify analytics commands
        assert "purchase" in analytics_commands

    def test_nested_command_help(self):
        """Test help for nested commands."""
        # Test pipeline scrape help
        result = self.runner.invoke(cli, ["pipeline", "scrape", "--help"])
        assert result.exit_code == 0

        # Test admin db-setup help
        result = self.runner.invoke(cli, ["admin", "db-setup", "--help"])
        assert result.exit_code == 0

        # Test dev test help
        result = self.runner.invoke(cli, ["dev", "test", "--help"])
        assert result.exit_code == 0

    def test_command_execution_with_options(self):
        """Test command execution with global options."""
        with patch("leadfactory.cli.commands.dev_commands.test"):
            # Create a mock command function
            mock_test_cmd = MagicMock()
            mock_test_cmd.name = "test"
            mock_test_cmd.callback = MagicMock()

            # Run with verbose flag
            self.runner.invoke(cli, ["--verbose", "dev", "test"])
            # The actual test command would be executed

    def test_error_propagation(self):
        """Test that errors in commands are properly propagated."""
        # Create a command that raises an error
        @cli.command()
        def error_command():
            """Test command that raises an error."""
            raise click.ClickException("Test error")

        result = self.runner.invoke(cli, ["error-command"])
        assert result.exit_code != 0
        assert "Test error" in result.output

    def test_cli_as_module(self):
        """Test running CLI as a module."""
        with patch("sys.argv", ["leadfactory", "--help"]):
            with patch("leadfactory.cli.main.cli"):
                # Simulate running as __main__
                exec(compile(open("leadfactory/cli/main.py").read(),
                           "leadfactory/cli/main.py", "exec"))
                # This would test the if __name__ == "__main__" block
