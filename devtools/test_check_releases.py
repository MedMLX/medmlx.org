"""Regression contracts for rejecting instructions that drift from a release."""

import json
import subprocess
import unittest
from pathlib import Path
from typing import Self, cast
from unittest.mock import patch
from urllib.request import Request

from devtools.check_releases import (
    Card,
    Example,
    Model,
    Reference,
    Release,
    ReleaseError,
    fetch_text,
    installation_requirements,
    resolve_installation,
    size_label,
    verify_reference,
    verify_release,
)

PYPI = "https://pypi.org/pypi/example/json"
SOURCE = "https://raw.githubusercontent.com/MedMLX/example/v1.2.3/"
README = """# Example

```sh
uv venv --python 3.13
source .venv/bin/activate
uv pip install "example>=1.2.3"
```
"""
PROJECT = """[project]
name = "example"
version = "1.2.3"
requires-python = ">=3.13,<3.15"
readme = "README.md"
[project.optional-dependencies]
video = []
"""


class ReleaseChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.release = Release("example", "1.2.3", "MedMLX/example")
        self.info: dict[str, object] = {
            "name": "example",
            "version": "1.2.3",
            "requires_python": "<3.15,>=3.13",
            "description": README,
            "provides_extra": ["video"],
        }
        self.files: list[dict[str, object]] = [{"yanked": False}, {"yanked": True}]
        self.sources = {"pyproject.toml": PROJECT, "README.md": README}
        self.examples = [
            Example("example", "README.md", 'uv pip install "example>=1.2.3"')
        ]

    def fetch(self, url: str) -> str:
        """Replace only the external IO boundary with literal release data."""
        if url == PYPI:
            return json.dumps({"info": self.info, "urls": self.files})
        if url.startswith(SOURCE) and url.removeprefix(SOURCE) in self.sources:
            return self.sources[url.removeprefix(SOURCE)]
        raise ReleaseError(f"Cannot fetch {url}: HTTP 404")

    def verify(self) -> None:
        verify_release(self.release, "3.13", self.examples, self.fetch)

    def test_new_pypi_release_requires_review(self) -> None:
        self.verify()
        self.info["version"] = "1.2.4"
        with self.assertRaisesRegex(
            ReleaseError, r"site reviews 1\.2\.3, PyPI publishes 1\.2\.4"
        ):
            self.verify()

    def test_model_card_checks_context_and_release_not_just_a_memory_number(self) -> None:
        excerpt = 'Peak MLX memory is 4 GB for a 128³ crop, excluding preprocessing.'
        readme = README + '\nPeak MLX memory is 4 GB for a 128³ crop,\nexcluding preprocessing.\n'
        self.sources['README.md'] = readme
        self.info['description'] = readme
        self.release = Release('example', '1.2.3', 'MedMLX/example', Card('1.2.3', (excerpt,)))
        self.verify()  # README wrapping does not change the supported fact.
        for version, text, error in [
            ('1.2.2', excerpt, 'reviewed for the displayed release'),
            ('1.2.3', excerpt.replace('128³', '256³'), 'excerpt is absent'),
            ('1.2.3', 'Minimum RAM is 4 GB.', 'excerpt is absent'),
            ('1.2.3', 'https://huggingface.co/MedMLX/unreviewed', 'excerpt is absent'),
        ]:
            with self.subTest(version=version, excerpt=text):
                self.release = Release('example', '1.2.3', 'MedMLX/example', Card(version, (text,)))
                with self.assertRaisesRegex(ReleaseError, error):
                    self.verify()

    def test_yanked_release_is_rejected_even_if_its_version_matches(self) -> None:
        self.verify()  # A single yanked file does not invalidate usable files.
        self.files = [{"yanked": True}]
        with self.assertRaisesRegex(ReleaseError, "has no non-yanked distributions"):
            self.verify()

    def test_documented_python_must_satisfy_pypi(self) -> None:
        self.info["requires_python"] = ">=3.14"
        with self.assertRaisesRegex(
            ReleaseError, r"Python 3\.13 does not satisfy >=3\.14"
        ):
            self.verify()

    def test_repository_release_metadata_must_match_pypi(self) -> None:
        cases = [
            (
                PROJECT.replace('version = "1.2.3"', 'version = "1.2.2"'),
                "tag version differs",
            ),
            (PROJECT.replace("<3.15", "<3.14"), "tag Python requirement differs"),
            (PROJECT.replace("video = []", "images = []"), "tag extras differ"),
        ]
        for project, message in cases:
            with self.subTest(contract=message):
                self.sources["pyproject.toml"] = project
                with self.assertRaisesRegex(ReleaseError, message):
                    self.verify()

    def test_readme_changes_cannot_silently_diverge_from_pypi(self) -> None:
        self.sources["README.md"] = README.replace("example>=1.2.3", "example>=1.2.4")
        with self.assertRaisesRegex(
            ReleaseError, "README differs from the published PyPI description"
        ):
            self.verify()

    def test_install_extra_must_exist_in_the_matching_release(self) -> None:
        self.sources["README.md"] = README.replace(
            "example>=1.2.3", "example[unknown]>=1.2.3"
        )
        self.info["description"] = self.sources["README.md"]
        self.examples = [
            Example("example", "README.md", 'uv pip install "example[unknown]>=1.2.3"')
        ]
        with self.assertRaisesRegex(
            ReleaseError, r"example\[unknown\]>=1.2.3 is incompatible"
        ):
            self.verify()

    def test_source_checkout_formatting_preserves_argv_but_invented_flags_fail(
        self,
    ) -> None:
        self.sources["docs/usage.md"] = """```bash
uv run example report \\
  --input scan.nii.gz --output-dir outputs --prompt "Describe the scan"
```
"""
        self.examples = [
            Example(
                "example",
                "docs/usage.md",
                "example report --input=scan.nii.gz --output-dir=outputs",
            )
        ]
        self.verify()
        self.examples = [
            Example("example", "docs/usage.md", "example report --invented=outputs")
        ]
        with self.assertRaisesRegex(
            ReleaseError, r"command is absent from the release's docs/usage.md"
        ):
            self.verify()

    def test_detailed_commands_may_live_in_the_readme_without_a_docs_page(
        self,
    ) -> None:
        readme = README + '\n```sh\nexample report --input scan.nii.gz\n```\n'
        self.sources["README.md"] = readme
        self.info["description"] = readme
        command = "example report --input=scan.nii.gz"
        self.examples = [Example("example", "docs/usage.md", command)]
        self.verify()
        self.examples = [Example("example", "docs/usage.md", "example report --absent")]
        with self.assertRaisesRegex(
            ReleaseError, r"absent from the release's docs/usage.md and README.md"
        ):
            self.verify()

    def test_missing_release_tag_cannot_fall_back_to_main(self) -> None:
        del self.sources["pyproject.toml"]
        with self.assertRaisesRegex(ReleaseError, r"v1\.2\.3/pyproject.toml: HTTP 404"):
            self.verify()

    def test_dynamic_version_is_read_without_executing_the_package(self) -> None:
        self.sources["pyproject.toml"] = (
            PROJECT.replace('version = "1.2.3"', 'dynamic = ["version"]')
            + """
[tool.setuptools.dynamic]
version = {attr = "example.version.__version__"}
"""
        )
        self.sources["example/version.py"] = (
            '__version__ = "1.2.3"\nraise RuntimeError("Do not execute source")\n'
        )
        self.verify()
        self.sources["example/version.py"] = '__version__ = "1.2.2"\n'
        with self.assertRaisesRegex(ReleaseError, "tag version differs"):
            self.verify()

    def test_only_installs_are_resolved_and_the_reviewed_version_is_required(
        self,
    ) -> None:
        releases = [self.release, Release("medmlx", "0.4.1", "MedMLX/medmlx")]
        examples = [
            Example(
                "medmlx", "README.md", 'uv tool install --python 3.13 "medmlx[all,mcp]"'
            ),
            Example("medmlx", "README.md", 'uv add "medmlx[all,mcp]"'),
            Example("example", "README.md", 'uv pip install \\\n  "example>=1.2.3"'),
            Example(
                "example",
                "docs/usage.md",
                "example download \\\n  --revision abc123 --model-dir models",
            ),
        ]
        self.assertEqual(
            installation_requirements(releases, examples),
            {"medmlx[all,mcp]==0.4.1", "example==1.2.3"},
        )

    def test_install_lines_must_name_the_same_packages_as_the_release(self) -> None:
        readme = README.replace('"example>=1.2.3"', '"example>=1.2.3" huggingface-hub')
        self.sources["README.md"] = readme
        self.info["description"] = readme
        with self.assertRaisesRegex(ReleaseError, "site install differs"):
            self.verify()
        self.examples = [
            Example(
                "example", "README.md", 'uv pip install "example>=1.2.3" huggingface-hub'
            )
        ]
        self.verify()

    def test_github_token_reaches_only_github_and_never_follows_redirects(self) -> None:
        sent: list[object] = []

        class Response:
            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def read(self) -> bytes:
                return b"ok"

        def capture(request: object, timeout: float) -> Response:
            sent.append(request)
            return Response()

        with (
            patch.dict("os.environ", {"GITHUB_TOKEN": "secret"}),
            patch("devtools.check_releases.urlopen", side_effect=capture),
        ):
            fetch_text(SOURCE + "README.md")
            fetch_text(PYPI)
        github, pypi = cast(list[Request], sent)
        self.assertEqual(github.unredirected_hdrs["Authorization"], "Bearer secret")
        self.assertNotIn("Authorization", github.headers)
        self.assertFalse(pypi.has_header("Authorization"))

    def test_small_weights_are_listed_in_megabytes(self) -> None:
        self.assertEqual(size_label(17_400_000_000), "17.4 GB")
        self.assertEqual(size_label(100_000_000), "0.1 GB")
        self.assertEqual(size_label(23_456_789), "23 MB")
        self.assertEqual(size_label(400_000), "1 MB")

    def test_companion_packages_resolve_with_a_reviewed_release_only(self) -> None:
        releases = [self.release]
        companion = Example(
            "example", "README.md", 'uv pip install "example>=1.2.3" huggingface-hub'
        )
        self.assertEqual(
            installation_requirements(releases, [companion]),
            {"example==1.2.3\nhuggingface-hub"},
        )
        alone = Example("example", "README.md", "uv pip install huggingface-hub")
        with self.assertRaisesRegex(ReleaseError, "Unreviewed install requirement"):
            installation_requirements(releases, [alone])

    def test_install_resolution_is_isolated_and_conflicts_block_export(self) -> None:
        def conflict(
            args: list[str], **options: object
        ) -> subprocess.CompletedProcess[str]:
            self.assertEqual(args[:4], ["uv", "--no-config", "pip", "compile"])
            self.assertEqual(
                args[4:12],
                [
                    "--default-index",
                    "https://pypi.org/simple",
                    "--python-version",
                    "3.13",
                    "--python-platform",
                    "aarch64-apple-darwin",
                    "--only-binary",
                    ":all:",
                ],
            )
            self.assertEqual(Path(args[-1]).read_text(), "example[video]==1.2.3\n")
            self.assertIs(options["check"], False)
            environment = cast(dict[str, str], options["env"])
            self.assertEqual(environment["MACOSX_DEPLOYMENT_TARGET"], "14.0")
            self.assertNotIn("UV_INDEX", environment)
            return subprocess.CompletedProcess(
                args, 1, "", "No solution: conflicting dependencies"
            )

        # Only the external command boundary is replaced; command construction,
        # requirement-file writing and failure propagation run unchanged.
        with (
            patch.dict("os.environ", {"UV_INDEX": "https://example.invalid/private"}),
            patch("devtools.check_releases.subprocess.run", side_effect=conflict),
            self.assertRaisesRegex(
                ReleaseError,
                "Cannot resolve example.*No solution: conflicting dependencies",
            ),
        ):
            resolve_installation("example[video]==1.2.3", "3.13", "14.0")


REVISION = "0123456789abcdef0123456789abcdef01234567"
WEIGHTS = f"https://huggingface.co/api/models/MedMLX/Example/revision/{REVISION}?blobs=true"
CLI = """import argparse

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers()
    download = commands.add_parser("download")
    download.add_argument(
        "--repo", default="MedMLX/Example"
    )
    download.add_argument("--revision", required=True)
    report = commands.add_parser("report")
    report.add_argument("--input", required=True)
    region = report.add_mutually_exclusive_group()
    region.add_argument("--anatomy-region", choices=["chest", "abdomen"])
    report.add_argument("--precision", choices=tuple(PROFILES))
    report.add_argument("--enable-thinking", action="store_true")
    raise RuntimeError("Do not execute source")
"""
DOWNLOAD = f"example download \\\n  --repo MedMLX/Example \\\n  --revision {REVISION}"


class ModelChecks(unittest.TestCase):
    """A detailed model page must match its release CLI, docs and pinned weights."""

    def setUp(self) -> None:
        self.release = Release("example", "1.2.3", "MedMLX/example")
        self.readme = README + "\nAllow more than 3.0 GB of unified memory.\n"
        self.info: dict[str, object] = {
            "name": "example",
            "version": "1.2.3",
            "requires_python": "<3.15,>=3.13",
            "description": self.readme,
            "provides_extra": ["video"],
        }
        self.sources = {
            "pyproject.toml": PROJECT + '[project.scripts]\nexample = "example.cli:main"\n',
            "README.md": self.readme,
            "src/example/cli.py": CLI,
        }
        self.weights: dict[str, object] = {
            "sha": REVISION,
            "siblings": [{"rfilename": "a", "size": 1_200_000_000}, {"rfilename": "b", "size": 230_000_000}],
        }
        self.weights_url = "https://huggingface.co/MedMLX/Example"
        self.weights_size = "1.4 GB"
        self.download = DOWNLOAD
        self.commands = [
            DOWNLOAD,
            "example report --input='ct.nii.gz' --anatomy-region='abdomen' --enable-thinking",
        ]

    def fetch(self, url: str) -> str:
        """Replace only the external IO boundary with literal release data."""
        if url == PYPI:
            return json.dumps({"info": self.info, "urls": [{"yanked": False}]})
        if url == WEIGHTS:
            return json.dumps(self.weights)
        if url.startswith(SOURCE) and url.removeprefix(SOURCE) in self.sources:
            return self.sources[url.removeprefix(SOURCE)]
        raise ReleaseError(f"Cannot fetch {url}: HTTP 404")

    def verify(self) -> None:
        model = Model(
            "example", self.weights_url, self.weights_size, "3.0 GB", self.download, tuple(self.commands)
        )
        verify_release(self.release, "3.13", [], self.fetch, (model,))

    def test_commands_must_use_options_and_choices_the_release_declares(self) -> None:
        self.verify()
        cases = [
            ("example report --input=ct.nii.gz --invented", "--invented is not an option of example report"),
            ("example report --input=ct.nii.gz --anatomy-region=pelvis", "pelvis is not a release choice"),
            ("example convert --input=ct.nii.gz", "subcommand the release does not declare"),
            ("other report --input=ct.nii.gz", "does not run a console script"),
            # A download option is not valid for the report subcommand.
            ("example report --input=ct.nii.gz --revision=abc", "--revision is not an option of example report"),
        ]
        for command, message in cases:
            with self.subTest(command=command):
                self.commands = [command]
                with self.assertRaisesRegex(ReleaseError, message):
                    self.verify()

    def test_computed_choices_and_flat_layouts_are_accepted(self) -> None:
        self.sources["example/cli.py"] = self.sources.pop("src/example/cli.py")
        self.commands = ["example report --input=ct.nii.gz --precision=bfloat16"]
        self.verify()

    def test_pinned_weights_must_exist_and_match_the_listed_size(self) -> None:
        self.verify()
        self.weights_size = "1.5 GB"
        with self.assertRaisesRegex(ReleaseError, r"site lists 1\.5 GB of weights; .* holds 1\.4 GB"):
            self.verify()
        self.weights_size = "1.4 GB"
        self.download = DOWNLOAD.replace(REVISION, "f" * 40)
        with self.assertRaisesRegex(ReleaseError, "Cannot fetch .*HTTP 404"):
            self.verify()

    def test_weights_link_and_revision_must_match_the_download_command(self) -> None:
        cases = [
            (DOWNLOAD.replace("MedMLX/Example", "MedMLX/Other"), "differs from download --repo"),
            (DOWNLOAD.replace(REVISION, "main"), "must pin a full Hugging Face commit"),
            (f"example download --revision {REVISION}", "must set --repo"),
        ]
        for download, message in cases:
            with self.subTest(contract=message):
                self.download = download
                with self.assertRaisesRegex(ReleaseError, message):
                    self.verify()

    def test_peak_memory_must_appear_in_the_release_docs(self) -> None:
        self.info["description"] = self.sources["README.md"] = README
        with self.assertRaisesRegex(ReleaseError, r"peak memory 3\.0 GB is absent"):
            self.verify()


if __name__ == "__main__":
    unittest.main()


class ReferenceChecks(unittest.TestCase):
    CLI = """
commands = parser.add_subparsers(dest="command", required=True)
commands.add_parser("runtime", help="Probe the runtime.")
run = commands.add_parser("run")
run.add_argument("--root")
"""

    def verify(self, commands: tuple[str, ...], functions: tuple[str, ...], example: str) -> None:
        sources = {"src/example/cli.py": self.CLI, "src/example/__init__.py": '__all__ = ["run"]\n'}
        reference = Reference("example", "example", "example", commands, functions)
        verify_reference(
            reference, [Example("example", "README.md", example)], {"example": "example.cli:main"},
            sources.__getitem__,
        )

    def test_listed_commands_and_functions_must_exist_in_the_release(self) -> None:
        # A subcommand with no options is declared without keeping its parser.
        self.verify(("runtime", "run"), ("run",), "import example\nexample run --root work")
        with self.assertRaisesRegex(ReleaseError, "does not declare"):
            self.verify(("serve",), ("run",), "example run")
        with self.assertRaisesRegex(ReleaseError, "does not export: describe"):
            self.verify(("run",), ("describe",), "example run")
        with self.assertRaisesRegex(ReleaseError, "--force is not an option"):
            self.verify(("run",), ("run",), "example run --force")

