import re
from pathlib import Path

import branding
from bot import REQUIRED_PERMISSIONS
from version import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?", __version__)


def test_changelog_latest_entry_matches_version():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## \[([^\]]+)\]", text, flags=re.M)
    assert headings and headings[0] == __version__


def test_readme_invite_permissions_match_code():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"permissions={REQUIRED_PERMISSIONS.value}" in readme


def test_bot_description_fits_developer_portal_limit():
    assert 0 < len(branding.DESCRIPTION) <= 400
