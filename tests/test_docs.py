"""Documentation checks: relative links resolve, and what the README shows exists.

The editor's docs test caught a `.gitignore` that silently dropped every new
docs image; the same class of failure is cheap to prevent here.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def relative_targets(text: str):
    for match in LINK.finditer(text):
        target = match.group(1).split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        yield target


class DocsTest(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue((ROOT / "README.md").is_file())

    def test_relative_links_resolve(self):
        readme = ROOT / "README.md"
        for target in relative_targets(readme.read_text(encoding="utf-8")):
            self.assertTrue((ROOT / target).exists(), f"README links to a missing file: {target}")

    def test_readme_images_resolve(self):
        readme = ROOT / "README.md"
        for match in IMAGE.finditer(readme.read_text(encoding="utf-8")):
            target = match.group(1)
            if target.startswith(("http://", "https://")):
                continue
            self.assertTrue((ROOT / target).is_file(), f"missing image: {target}")

    def test_version_matches_the_changelog(self):
        from hyprtk_shot import __version__

        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(__version__, changelog)

    def test_installer_mentions_the_binary(self):
        install = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("hyprtk-shot", install)
        self.assertIn("--uninstall", install)
        self.assertIn("--system", install)


if __name__ == "__main__":
    unittest.main()
