"""Move each reviewed release pin to the latest PyPI version that passes the release check.

For every package in site/releases.js whose PyPI version is newer, this rewrites the
pin, the version of each model card for that package and the card's links into the
old tag. It then runs devtools/check_releases.py, which compares the site with the
new tag's README and metadata. A package that fails is put back to its previous pin
and the check runs again, so the site only ever names releases whose instructions
the check found in the release itself. A held package still fails the check as a
stale pin, which blocks `make pages` until someone updates the site for it. Exits 0
when every pin is current and the check passes; otherwise prints each held package
with the failure its new release produced and exits 1.
"""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "site/releases.js"
CARDS = ROOT / "site/model-cards.js"
PIN = re.compile(r"^  '?([a-z0-9-]+)'?: \{ version: '([^']+)', repository: '([^']+)' \},$", re.MULTILINE)


@dataclass(frozen=True)
class Bump:
    name: str
    repository: str
    old: str
    new: str


def latest(name: str) -> str:
    request = Request(f"https://pypi.org/pypi/{name}/json", headers={"User-Agent": "medmlx-site"})
    with urlopen(request, timeout=30) as response:
        data: dict[str, dict[str, str]] = json.load(response)
    return data["info"]["version"]


def card_slugs(name: str) -> list[str]:
    """Catalog slugs whose model card reviews this package (nnU-Net and SIAM share one)."""
    script = (
        "import { additionalRuntimes } from './site/models.js';"
        "console.log(JSON.stringify(additionalRuntimes.map(r => [r.slug, r.distribution])));"
    )
    output = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout
    pairs: list[list[str]] = json.loads(output)
    return [slug for slug, distribution in pairs if distribution == name]


def apply(bump: Bump, forward: bool) -> None:
    old, new = (bump.old, bump.new) if forward else (bump.new, bump.old)
    releases = RELEASES.read_text()
    pin = re.compile(rf"^(  '?{re.escape(bump.name)}'?: \{{ version: '){re.escape(old)}'", re.MULTILINE)
    releases, count = pin.subn(rf"\g<1>{new}'", releases)
    if count != 1:
        raise ValueError(f"{bump.name}: pin {old} not found in site/releases.js")
    RELEASES.write_text(releases)
    cards = CARDS.read_text()
    for slug in card_slugs(bump.name):
        header = f'  "{slug}": {{\n    "version": "{old}",'
        if header in cards:
            cards = cards.replace(header, f'  "{slug}": {{\n    "version": "{new}",')
    for kind in ("blob", "tree"):
        cards = cards.replace(f"github.com/{bump.repository}/{kind}/v{old}/",
                              f"github.com/{bump.repository}/{kind}/v{new}/")
    CARDS.write_text(cards)


def release_check() -> tuple[bool, str]:
    result = subprocess.run(["make", "--no-print-directory", "release-check"], cwd=ROOT,
                            capture_output=True, text=True, check=False)
    return result.returncode == 0, result.stdout + result.stderr


def failed_packages(output: str, names: set[str]) -> set[str]:
    return {name for name in names if re.search(rf"^  {re.escape(name)}: ", output, re.MULTILINE)}


def main() -> int:
    pins = PIN.findall(RELEASES.read_text())
    if not pins:
        raise ValueError("No release pins found in site/releases.js")
    bumps = [Bump(name, repository, old, new) for name, old, repository in pins
             if Version(new := latest(name)) > Version(old)]
    for bump in bumps:
        apply(bump, forward=True)
    held: dict[str, str] = {}
    while True:
        passed, output = release_check()
        if passed:
            break
        pending = {bump.name for bump in bumps if bump.name not in held}
        failing = failed_packages(output, pending)
        if not failing:
            # Held packages now fail only as stale pins; anything else is unexplained.
            stale = {name for name in held
                     if re.search(rf"^  {re.escape(name)}: site reviews ", output, re.MULTILINE)}
            other = [line for line in re.findall(r"^  (\S.*)$", output, re.MULTILINE)
                     if not any(line.startswith(f"{name}: site reviews ") for name in stale)]
            if other or not held:
                print(output, file=sys.stderr)
                return 1
            break
        for bump in bumps:
            if bump.name in failing:
                apply(bump, forward=False)
                lines = re.findall(rf"^  {re.escape(bump.name)}: (.*(?:\n(?!  \S).*)*)", output, re.MULTILINE)
                held[bump.name] = lines[0].strip() if lines else "release check failed"
    for bump in bumps:
        if bump.name not in held:
            print(f"bumped {bump.name} {bump.old} -> {bump.new}")
    for name, reason in held.items():
        bump = next(item for item in bumps if item.name == name)
        print(f"held {name} at {bump.old}; {bump.new} needs review: {reason}")
    if not bumps:
        print("every pin is the latest release")
    return 1 if held else 0


if __name__ == "__main__":
    raise SystemExit(main())
