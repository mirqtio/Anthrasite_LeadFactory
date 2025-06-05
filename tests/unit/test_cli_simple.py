"""
Simple CLI tests that verify the CLI functionality works.
"""

import os
import subprocess

import pytest


class TestCLIFunctionality:
    """Test CLI functionality through subprocess calls."""

    def setup_method(self):
        """Set up test fixtures."""
        self.project_root = os.path.join(os.path.dirname(__file__), "..", "..")
        self.cli_command = ["python3", "-m", "leadfactory.cli.main"]

    def test_cli_help_command(self):
        """Test that CLI help command works."""
        result = subprocess.run(
            self.cli_command + ["--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout to prevent hangs
        )
        assert result.returncode == 0
        assert "Anthrasite Lead Factory CLI" in result.stdout
        assert "pipeline" in result.stdout
        assert "admin" in result.stdout
        assert "dev" in result.stdout

    def test_cli_version_command(self):
        """Test that CLI version command works."""
        result = subprocess.run(
            self.cli_command + ["--version"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

    def test_pipeline_help_command(self):
        """Test that pipeline help command works."""
        result = subprocess.run(
            self.cli_command + ["pipeline", "--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "Pipeline operations" in result.stdout
        assert "scrape" in result.stdout
        assert "enrich" in result.stdout
        assert "dedupe" in result.stdout
        assert "email" in result.stdout

    def test_admin_help_command(self):
        """Test that admin help command works."""
        result = subprocess.run(
            self.cli_command + ["admin", "--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "Administrative operations" in result.stdout

    def test_dev_help_command(self):
        """Test that dev help command works."""
        result = subprocess.run(
            self.cli_command + ["dev", "--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "Development and testing operations" in result.stdout

    def test_scrape_help_command(self):
        """Test that scrape help command works."""
        result = subprocess.run(
            self.cli_command + ["pipeline", "scrape", "--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "--limit" in result.stdout
        assert "--zip-code" in result.stdout
        assert "--vertical" in result.stdout

    def test_enrich_help_command(self):
        """Test that enrich help command works."""
        result = subprocess.run(
            self.cli_command + ["pipeline", "enrich", "--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "--limit" in result.stdout
        assert "--id" in result.stdout
        assert "--tier" in result.stdout

    def test_dedupe_help_command(self):
        """Test that dedupe help command works."""
        result = subprocess.run(
            self.cli_command + ["pipeline", "dedupe", "--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "--limit" in result.stdout
        assert "--threshold" in result.stdout

    def test_email_help_command(self):
        """Test that email help command works."""
        result = subprocess.run(
            self.cli_command + ["pipeline", "email", "--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "--limit" in result.stdout
        assert "--id" in result.stdout
        assert "--force" in result.stdout

    def test_verbose_flag(self):
        """Test that verbose flag works."""
        result = subprocess.run(
            self.cli_command + ["--verbose", "--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

    def test_dry_run_flag(self):
        """Test that dry-run flag works."""
        result = subprocess.run(
            self.cli_command + ["--dry-run", "--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0


class TestCLIStructure:
    """Test CLI file structure and basic requirements."""

    def setup_method(self):
        """Set up test fixtures."""
        self.project_root = os.path.join(os.path.dirname(__file__), "..", "..")

    def test_cli_files_exist(self):
        """Test that all required CLI files exist."""
        cli_main = os.path.join(self.project_root, "leadfactory", "cli", "main.py")
        assert os.path.exists(cli_main), "CLI main.py should exist"

        cli_utils = os.path.join(self.project_root, "leadfactory", "cli", "utils.py")
        assert os.path.exists(cli_utils), "CLI utils.py should exist"

        commands_dir = os.path.join(self.project_root, "leadfactory", "cli", "commands")
        assert os.path.exists(commands_dir), "CLI commands directory should exist"

        pipeline_commands = os.path.join(commands_dir, "pipeline_commands.py")
        assert os.path.exists(pipeline_commands), "Pipeline commands should exist"

        admin_commands = os.path.join(commands_dir, "admin_commands.py")
        assert os.path.exists(admin_commands), "Admin commands should exist"

        dev_commands = os.path.join(commands_dir, "dev_commands.py")
        assert os.path.exists(dev_commands), "Dev commands should exist"

    def test_click_dependency_installed(self):
        """Test that Click dependency is available."""
        try:
            import click

            assert click is not None
        except ImportError:
            pytest.fail("Click framework should be installed")

    def test_requirements_has_click(self):
        """Test that requirements.txt includes Click."""
        requirements_path = os.path.join(self.project_root, "requirements.txt")
        assert os.path.exists(requirements_path), "requirements.txt should exist"

        with open(requirements_path) as f:
            requirements_content = f.read()

        assert "click" in requirements_content.lower(), (
            "Click should be in requirements.txt"
        )


if __name__ == "__main__":
    pytest.main([__file__])
