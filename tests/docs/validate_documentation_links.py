#!/usr/bin/env python3
"""
Documentation Link Validation Script

This script validates all internal and external links in the documentation
to ensure they are working and point to valid resources.
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class DocumentationLinkValidator:
    """Validates links in documentation files."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.docs_dir = project_root / "docs"
        self.errors = []
        self.warnings = []

        # Setup requests session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def validate_internal_link(self, link: str, source_file: Path) -> bool:
        """Validate an internal link (anchor or relative path)."""
        if link.startswith("#"):
            # Anchor link - validate against headings in the same file
            return self.validate_anchor_link(link, source_file)
        else:
            # Relative file path
            target_path = (source_file.parent / link).resolve()
            if not target_path.exists():
                self.errors.append(
                    f"Broken internal link in {source_file.name}: {link} -> {target_path}"
                )
                return False
            return True

    def validate_anchor_link(self, anchor: str, file_path: Path) -> bool:
        """Validate an anchor link against headings in the file."""
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Extract headings and convert to anchor format
        headings = re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)
        anchors = []

        for heading in headings:
            # Convert heading to GitHub-style anchor
            anchor_text = heading.lower()
            anchor_text = re.sub(r"[^\w\s-]", "", anchor_text)
            anchor_text = re.sub(r"[-\s]+", "-", anchor_text)
            anchor_text = anchor_text.strip("-")
            anchors.append(f"#{anchor_text}")

        if anchor not in anchors:
            self.errors.append(f"Broken anchor link in {file_path.name}: {anchor}")
            self.warnings.append(f"Available anchors: {', '.join(anchors[:5])}...")
            return False
        return True

    def validate_external_link(self, url: str, source_file: Path) -> bool:
        """Validate an external URL."""
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            if response.status_code >= 400:
                self.errors.append(
                    f"Broken external link in {source_file.name}: {url} (HTTP {response.status_code})"
                )
                return False
            return True
        except requests.RequestException as e:
            self.warnings.append(
                f"Could not validate external link in {source_file.name}: {url} ({str(e)})"
            )
            return False

    def extract_links_from_file(self, file_path: Path) -> list:
        """Extract all markdown links from a file."""
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Find all markdown links [text](url)
        links = re.findall(r"\[([^\]]*)\]\(([^)]+)\)", content)
        return [(text, url) for text, url in links]

    def validate_file(self, file_path: Path) -> dict:
        """Validate all links in a single file."""
        results = {
            "file": file_path.name,
            "total_links": 0,
            "valid_links": 0,
            "broken_links": 0,
            "warnings": 0,
        }

        try:
            links = self.extract_links_from_file(file_path)
            results["total_links"] = len(links)

            for link_text, link_url in links:
                parsed_url = urlparse(link_url)

                if parsed_url.scheme in ("http", "https"):
                    # External link
                    if self.validate_external_link(link_url, file_path):
                        results["valid_links"] += 1
                    else:
                        results["broken_links"] += 1
                elif link_url.startswith("#") or not parsed_url.scheme:
                    # Internal link or anchor
                    if self.validate_internal_link(link_url, file_path):
                        results["valid_links"] += 1
                    else:
                        results["broken_links"] += 1
                else:
                    self.warnings.append(
                        f"Unknown link type in {file_path.name}: {link_url}"
                    )
                    results["warnings"] += 1

        except Exception as e:
            self.errors.append(f"Error processing file {file_path.name}: {str(e)}")

        return results

    def validate_all_documentation(self) -> dict:
        """Validate all documentation files."""
        summary = {
            "total_files": 0,
            "total_links": 0,
            "valid_links": 0,
            "broken_links": 0,
            "warnings": 0,
            "files": [],
        }

        # Find all markdown files in docs directory
        md_files = list(self.docs_dir.glob("**/*.md"))

        for md_file in md_files:
            file_results = self.validate_file(md_file)
            summary["files"].append(file_results)
            summary["total_files"] += 1
            summary["total_links"] += file_results["total_links"]
            summary["valid_links"] += file_results["valid_links"]
            summary["broken_links"] += file_results["broken_links"]
            summary["warnings"] += file_results["warnings"]

        return summary

    def print_report(self, summary: dict):
        """Print validation report."""
        print("📚 Documentation Link Validation Report")
        print("=" * 50)
        print(f"Files processed: {summary['total_files']}")
        print(f"Total links: {summary['total_links']}")
        print(f"✅ Valid links: {summary['valid_links']}")
        print(f"❌ Broken links: {summary['broken_links']}")
        print(f"⚠️  Warnings: {summary['warnings']}")
        print()

        if self.errors:
            print("❌ ERRORS:")
            for error in self.errors:
                print(f"  - {error}")
            print()

        if self.warnings:
            print("⚠️  WARNINGS:")
            for warning in self.warnings[:10]:  # Limit to first 10 warnings
                print(f"  - {warning}")
            if len(self.warnings) > 10:
                print(f"  ... and {len(self.warnings) - 10} more warnings")
            print()

        # Per-file breakdown
        print("📄 Per-file results:")
        for file_result in summary["files"]:
            status = "✅" if file_result["broken_links"] == 0 else "❌"
            print(
                f"  {status} {file_result['file']}: "
                f"{file_result['valid_links']}/{file_result['total_links']} valid"
            )


def main():
    """Main entry point."""
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent.parent

    validator = DocumentationLinkValidator(project_root)
    summary = validator.validate_all_documentation()
    validator.print_report(summary)

    # Exit with error code if there are broken links
    if summary["broken_links"] > 0:
        print(f"\n❌ Validation failed: {summary['broken_links']} broken links found")
        sys.exit(1)
    else:
        print("\n✅ All documentation links are valid!")
        sys.exit(0)


if __name__ == "__main__":
    main()
