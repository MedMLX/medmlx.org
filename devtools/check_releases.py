"""Verify site instructions against PyPI, each repository's release tag and
the pinned Hugging Face weights.

This is a network check, separate from the hermetic command tests. It never
imports a runtime, installs a model, downloads weights, or executes examples.
With ``--readmes FILE`` a passing check also writes each package's verified
tagged README to FILE as JSON, which the site export publishes for agents.
"""

import ast
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


class ReleaseError(ValueError):
    """A published package and the site's reviewed instructions disagree."""


@dataclass(frozen=True)
class Card:
    """Source excerpts supporting reviewed summaries, plus their weight links."""

    version: str
    excerpts: tuple[str, ...]


@dataclass(frozen=True)
class Release:
    name: str
    version: str
    repository: str
    card: Card | None = None


@dataclass(frozen=True)
class Example:
    distribution: str
    path: str
    command: str


@dataclass(frozen=True)
class RunExample:
    """A model page's `medmlx run` line: the model ID and `--arg` names its release documents.

    `distribution` is the package whose tagged README (plus `docs`) documents the model;
    it differs from the page's package when medmlx itself provides the model.
    """

    distribution: str
    docs: tuple[str, ...]
    model_id: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class Reference:
    """Subcommands and Python functions a reference page lists for a release."""

    distribution: str
    script: str
    module: str
    commands: tuple[str, ...]
    functions: tuple[str, ...]


@dataclass(frozen=True)
class Model:
    """A runtime with a detailed page: its weights, figures and CLI commands."""

    distribution: str
    weights_url: str
    weights_size: str
    peak_memory: str
    download: str
    commands: tuple[str, ...]


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReleaseError("Expected a JSON/TOML object with string keys")
    result = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in result):
        raise ReleaseError("Expected a JSON/TOML object with string keys")
    return cast(dict[str, object], result)


def sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ReleaseError("Expected a JSON/TOML array")
    return cast(list[object], value)


def string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseError("Expected a nonempty string")
    return value


def integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ReleaseError("Expected an integer")
    return value


# Only GitHub receives GITHUB_TOKEN, which lets the check read private MedMLX repos.
GITHUB_HOSTS = {"raw.githubusercontent.com", "api.github.com"}


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "medmlx-site-release-check"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and urlparse(url).hostname in GITHUB_HOSTS:
        # Unredirected, so a redirect to another host never carries the token.
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    try:
        with urlopen(request, timeout=20) as response:
            body: bytes = response.read()
        return body.decode("utf-8")
    except (URLError, TimeoutError, UnicodeError) as error:
        raise ReleaseError(f"Cannot fetch {url}: {error}") from error


def load_catalog() -> tuple[
    str, str, list[Release], list[Example], list[Model], list[Reference], list[RunExample],
    list[tuple[str, str, str]],
]:
    """Read the same modules that render the website, without a browser."""
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            """
import { releases, pythonVersion, macosVersion, medmlxExamples, connectExamples } from './site/releases.js';
import { models, additionalRuntimes, reportCommand, runExamples } from './site/models.js';
import { modelCards } from './site/model-cards.js';
import { mcpExamples } from './site/mcp.js';
import { developerExamples, developerReference } from './site/developer.js';
const runtimes = [...models, ...additionalRuntimes];
// The Reason-CT command form can add every optional report flag.
const formCommands = {
  'mlx-reason-ct': [reportCommand({
    image_path: 'ct.nii.gz', weights_path: 'models', output_dir: 'outputs',
    anatomy_region: 'abdomen', prompt: 'Describe the CT.', enable_thinking: true,
  })],
};
// Cards are keyed by catalog slug. A package with several pages (nnU-Net and SIAM)
// has one card per page, all checked against the same tagged README.
const cards = {};
for (const runtime of additionalRuntimes) {
  const card = modelCards[runtime.slug];
  if (!card) throw new Error(`${runtime.slug}: every additional runtime needs a reviewed model card`);
  const merged = cards[runtime.distribution] ||= { version: card.version, excerpts: [] };
  if (merged.version !== card.version) throw new Error(`${runtime.slug}: cards for one package must review one version`);
  merged.excerpts.push(
    ...[...card.rows.map(([, fact]) => fact), ...card.limitations, ...card.measurements, card.terms]
      .flatMap(fact => {
        if (!fact.text?.trim() || !Array.isArray(fact.sources) || !fact.sources.length) {
          throw new Error(`${runtime.slug}: every model-card summary needs supporting source excerpts`);
        }
        return fact.sources;
      }),
    ...card.weights.map(weight => weight.url),
  );
}
const slugs = new Set(additionalRuntimes.map(runtime => runtime.slug));
const orphan = Object.keys(modelCards).find(slug => !slugs.has(slug));
if (orphan) throw new Error(`${orphan}: model card has no catalog entry`);
const unrun = additionalRuntimes.find(runtime => !runExamples[runtime.slug]);
if (unrun) throw new Error(`${unrun.slug}: every runtime page needs a run example`);
const orphanRun = Object.keys(runExamples).find(slug => !slugs.has(slug));
if (orphanRun) throw new Error(`${orphanRun}: run example has no catalog entry`);
console.log(JSON.stringify({
  python: pythonVersion,
  macos: macosVersion,
  releases,
  cards,
  cardPackages: additionalRuntimes.map(runtime => runtime.distribution),
  weightPins: Object.values(modelCards).flatMap(card => card.weights.filter(weight => weight.revision)
    .map(({ url, revision, size }) => ({ url, revision, size }))),
  packages: [{ distribution: 'medmlx', package: 'https://pypi.org/project/medmlx/' },
    ...new Map(runtimes.map(runtime => [runtime.distribution,
      { distribution: runtime.distribution, package: runtime.links?.package || runtime.package }])).values()],
  examples: [
    ...medmlxExamples,
    ...connectExamples,
    ...mcpExamples.map(({ distribution, path, command }) => ({ distribution, path, command })),
    ...developerExamples,
    ...additionalRuntimes.map(runtime => ({ distribution: runtime.distribution, path: 'README.md', command: runtime.install })),
    // Each run block's medmlx install and setup lines come from the page package's README.
    ...additionalRuntimes.flatMap(runtime => {
      const run = runExamples[runtime.slug];
      return [`uv tool install --python ${pythonVersion} "medmlx[${run.extras}]"`, ...(run.before || [])]
        .map(command => ({ distribution: runtime.distribution, path: 'README.md', command }));
    }),
    ...models.flatMap(model => Object.entries(model.commands).map(([step, command]) => ({
      distribution: model.distribution, path: step === 'install' ? 'README.md' : 'docs/usage.md', command,
    }))),
  ],
  references: [{ distribution: 'medmlx', script: 'medmlx', module: 'medmlx', ...developerReference }],
  runs: additionalRuntimes.map(runtime => {
    const run = runExamples[runtime.slug];
    return { distribution: run.package || runtime.distribution, docs: run.docs ? [run.docs] : [], id: run.id, args: run.args };
  }),
  models: models.map(model => ({
    distribution: model.distribution,
    weights: model.links.weights,
    weightsSize: model.resourceSizes.weights,
    peakMemory: model.resourceSizes.peakMemory,
    download: model.commands.download,
    commands: [
      ...Object.entries(model.commands).filter(([step]) => step !== 'install').map(([, command]) => command),
      ...(formCommands[model.slug] || []),
    ],
  })),
}));
""",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode:
        raise ReleaseError(f"Cannot load site catalog: {result.stderr.strip()}")
    data = mapping(json.loads(result.stdout))
    declared = mapping(data["releases"])
    cards = mapping(data["cards"])
    if set(cards) != {string(name) for name in sequence(data["cardPackages"])}:
        raise ReleaseError("Every additional runtime must have a reviewed model card")
    packages = [mapping(item) for item in sequence(data["packages"])]
    names = [string(item["distribution"]) for item in packages]
    if len(names) != len(set(names)) or set(names) != set(declared):
        raise ReleaseError(
            "Every site package must appear exactly once in site/releases.js"
        )
    for item in packages:
        name = string(item["distribution"])
        if item["package"] != f"https://pypi.org/project/{name}/":
            raise ReleaseError(f"{name}: use the current package URL from packageUrl()")
    releases = [
        Release(
            name,
            string(mapping(value)["version"]),
            string(mapping(value)["repository"]),
            Card(
                string(mapping(cards[name])["version"]),
                tuple(string(text) for text in sequence(mapping(cards[name])["excerpts"])),
            ) if name in cards else None,
        )
        for name, value in declared.items()
    ]
    examples = [
        Example(
            string(item["distribution"]), string(item["path"]), string(item["command"])
        )
        for value in sequence(data["examples"])
        for item in [mapping(value)]
    ]
    models = [
        Model(
            string(item["distribution"]),
            string(item["weights"]),
            string(item["weightsSize"]),
            string(item["peakMemory"]),
            string(item["download"]),
            tuple(string(command) for command in sequence(item["commands"])),
        )
        for value in sequence(data["models"])
        for item in [mapping(value)]
    ]
    references = [
        Reference(
            string(item["distribution"]),
            string(item["script"]),
            string(item["module"]),
            tuple(string(name) for name in sequence(item["commands"])),
            tuple(string(name) for name in sequence(item["functions"])),
        )
        for value in sequence(data["references"])
        for item in [mapping(value)]
    ]
    pins = [
        (string(item["url"]), string(item["revision"]), string(item["size"]))
        for value in sequence(data["weightPins"])
        for item in [mapping(value)]
    ]
    runs = [
        RunExample(
            string(item["distribution"]),
            tuple(string(path) for path in sequence(item["docs"])),
            string(item["id"]),
            run_arguments(string(item["args"])),
        )
        for value in sequence(data["runs"])
        for item in [mapping(value)]
    ]
    return (
        string(data["python"]), string(data["macos"]), releases, examples, models, references, runs, pins
    )


def command_tokens(command: str) -> list[str]:
    # The runtime docs use `uv run` in a source checkout. An activated, installed
    # runtime invokes the same command directly. Compare argv, not formatting.
    command = command.replace("\\\n", " ")
    command = re.sub(r"(?m)^uv run ", "", command)
    tokens: list[str] = []
    for token in shlex.split(command, comments=True):
        if token.startswith("--") and "=" in token:
            tokens.extend(token.split("=", 1))
        else:
            tokens.append(token)
    return tokens


def documented(command: str, document: str) -> bool:
    if command in document:
        return True
    expected = command_tokens(command)
    for block in re.findall(
        r"```(?:sh|bash|shell|console)\n(.*?)```", document, re.DOTALL
    ):
        actual = command_tokens(block)
        if any(
            actual[index : index + len(expected)] == expected
            for index in range(len(actual))
        ):
            return True
    return False


def size_label(total: int) -> str:
    """Format a byte count as the site lists it; small weights read in MB, not 0.0 GB."""
    if total < 100_000_000:
        return f"{max(1, round(total / 1e6))} MB"
    return f"{total / 1e9:.1f} GB"


def documented_install(line: str, document: str) -> bool:
    """Match an install line only when the docs install exactly the same packages.

    Token matching accepts a prefix, which would let the site drop a companion
    package the README installs on the same line.
    """
    expected = shlex.split(line)
    blocks = re.findall(r"```(?:sh|bash|shell|console)\n(.*?)```", document, re.DOTALL)
    candidates = [
        candidate
        for block in blocks
        for candidate in block.replace("\\\n", " ").splitlines()
    ] + re.findall(r"`([^`\n]+)`", document)
    return any(
        INSTALL.match(candidate.strip()) and shlex.split(candidate) == expected
        for candidate in candidates
    )


def project_version(
    project: dict[str, object], config: dict[str, object], source: Callable[[str], str]
) -> str:
    if "version" in project:
        return string(project["version"])
    # MedVLM declares a literal version attribute through setuptools. Read its
    # assignment as data; never import or execute third-party package code.
    tools = mapping(config["tool"])
    setuptools = mapping(tools["setuptools"])
    dynamic = mapping(setuptools["dynamic"])
    attribute = string(mapping(dynamic["version"])["attr"])
    module, variable = attribute.rsplit(".", 1)
    # A src layout declares its package directory under packages.find.where.
    roots: list[str] = []
    packages = setuptools.get("packages")
    if isinstance(packages, dict):
        find = mapping(cast(object, packages)).get("find")
        if isinstance(find, dict):
            where = mapping(cast(object, find)).get("where")
            if isinstance(where, list):
                roots = [string(root) for root in cast(list[object], where)]
    path = module.replace(".", "/") + ".py"
    tree = ast.parse(source(f"{roots[0].rstrip('/')}/{path}" if roots else path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable
            for target in node.targets
        ):
            return string(ast.literal_eval(node.value))
    raise ReleaseError(f"Cannot read declared version attribute {attribute}")


Options = dict[str, dict[str, frozenset[str] | None]]


def cli_options(tree: ast.Module) -> Options:
    """Map argparse subcommands to their options and literal choices, read as data."""
    calls = [
        (node, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
    ]
    parsers: dict[str, str] = {}
    for node, call in calls:
        if (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "add_parser"
            and call.args
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        ):
            name = call.args[0].value
            parsers.update({t.id: name for t in node.targets if isinstance(t, ast.Name)})
    for node, call in calls:
        # Options added through an argument group belong to the group's subcommand.
        if (
            isinstance(call.func, ast.Attribute)
            and call.func.attr in {"add_argument_group", "add_mutually_exclusive_group"}
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id in parsers
        ):
            name = parsers[call.func.value.id]
            parsers.update({t.id: name for t in node.targets if isinstance(t, ast.Name)})
    options: Options = {name: {} for name in parsers.values()}
    # A subcommand with no options is often declared without keeping its parser.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            options.setdefault(node.args[0].value, {})
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in parsers
        ):
            _declare_option(options[parsers[node.func.value.id]], node)
    # A helper function can add shared options to the parser passed as its first
    # argument, as in `_add_argument_options(run, ...)`; credit them to that parser.
    helpers: dict[str, list[ast.Call]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.args.args:
            parameter = node.args.args[0].arg
            helpers[node.name] = [
                call
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "add_argument"
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == parameter
            ]
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in helpers
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in parsers
        ):
            for call in helpers[node.func.id]:
                _declare_option(options[parsers[node.args[0].id]], call)
    return options


def _declare_option(declared: dict[str, frozenset[str] | None], call: ast.Call) -> None:
    """Record an `add_argument` call's option strings with their literal choices."""
    choices: frozenset[str] | None = None
    for keyword in call.keywords:
        if keyword.arg != "choices":
            continue
        try:
            value: object = ast.literal_eval(keyword.value)
        except ValueError:
            continue  # Computed choices cannot be read without running the CLI.
        if isinstance(value, (list, tuple)):
            items = cast(list[object] | tuple[object, ...], value)
            choices = frozenset(str(item) for item in items)
    for argument in call.args:
        if (
            isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
            and argument.value.startswith("-")
        ):
            declared[argument.value] = choices


def verify_command(command: str, scripts: dict[str, object], source: Callable[[str], str]) -> None:
    """Reject subcommands, options and choices the release's CLI does not declare."""
    tokens = command_tokens(command)
    if not tokens or tokens[0] not in scripts:
        raise ReleaseError(f"site command does not run a console script of the release: {command}")
    module = string(scripts[tokens[0]]).split(":", 1)[0].replace(".", "/") + ".py"
    for path in (f"src/{module}", module):
        try:
            text = source(path)
        except ReleaseError:
            continue
        break
    else:
        raise ReleaseError(f"Cannot find the {tokens[0]} CLI source in the release")
    options = cli_options(ast.parse(text))
    if len(tokens) < 2 or tokens[1] not in options:
        raise ReleaseError(f"site command uses a subcommand the release does not declare: {command}")
    declared = options[tokens[1]]
    for index, token in enumerate(tokens[2:], start=2):
        if not token.startswith("-"):
            continue
        if token not in declared:
            raise ReleaseError(f"{token} is not an option of {tokens[0]} {tokens[1]} in the release")
        choices = declared[token]
        if choices is not None and index + 1 < len(tokens) and tokens[index + 1] not in choices:
            raise ReleaseError(f"{tokens[index + 1]} is not a release choice for {token}")


def package_exports(text: str) -> set[str]:
    """Read a package's literal ``__all__`` as data."""
    for node in ast.parse(text).body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
            and isinstance(node.value, ast.List | ast.Tuple)
        ):
            return {
                item.value
                for item in node.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            }
    raise ReleaseError("Cannot read the package's __all__")


def verify_reference(
    reference: Reference, examples: list[Example], scripts: dict[str, object], source: Callable[[str], str]
) -> None:
    """Check a reference page's commands and functions against the release.

    Every example line that runs the release's console script must use declared
    subcommands and options, and every listed function must be exported.
    """
    for example in examples:
        if example.distribution != reference.distribution:
            continue
        for line in example.command.replace("\\\n", " ").splitlines():
            if line.strip().startswith(f"{reference.script} "):
                verify_command(line, scripts, source)
    for name in reference.commands:
        verify_command(f"{reference.script} {name}", scripts, source)
    exported = package_exports(source(f"src/{reference.module}/__init__.py"))
    missing = sorted(set(reference.functions) - exported)
    if missing:
        raise ReleaseError(f"site lists functions the release does not export: {', '.join(missing)}")


def verify_weights(model: Model, fetch: Callable[[str], str]) -> None:
    """Check the pinned Hugging Face revision exists and matches the site's size."""
    tokens = command_tokens(model.download)

    def option(flag: str) -> str:
        if flag not in tokens or tokens.index(flag) + 1 >= len(tokens):
            raise ReleaseError(f"download command must set {flag}")
        return tokens[tokens.index(flag) + 1]

    repository, revision = option("--repo"), option("--revision")
    if model.weights_url != f"https://huggingface.co/{repository}":
        raise ReleaseError(f"weights link {model.weights_url} differs from download --repo {repository}")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ReleaseError("download --revision must pin a full Hugging Face commit")
    data = mapping(json.loads(fetch(
        f"https://huggingface.co/api/models/{repository}/revision/{revision}?blobs=true"
    )))
    if data.get("sha") != revision:
        raise ReleaseError(f"Hugging Face does not serve {repository}@{revision}")
    total = sum(integer(mapping(item).get("size")) for item in sequence(data["siblings"]))
    published = size_label(total)
    if published != model.weights_size:
        raise ReleaseError(
            f"site lists {model.weights_size} of weights; {repository}@{revision[:12]} holds {published}"
        )


def verify_revision(url: str, revision: str, size: str, fetch: Callable[[str], str]) -> None:
    """Check a model card's pinned Hugging Face commit exists and holds the listed size."""
    prefix = "https://huggingface.co/"
    if not url.startswith(prefix) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ReleaseError(f"{url}: a pinned revision needs a Hugging Face link and a full commit")
    repository = url.removeprefix(prefix)
    data = mapping(json.loads(fetch(
        f"https://huggingface.co/api/models/{repository}/revision/{revision}?blobs=true"
    )))
    if data.get("sha") != revision:
        raise ReleaseError(f"Hugging Face does not serve {repository}@{revision}")
    published = size_label(sum(integer(mapping(item).get("size")) for item in sequence(data["siblings"])))
    if published != size:
        raise ReleaseError(f"site lists {size} of weights; {repository}@{revision[:12]} holds {published}")


def run_arguments(arguments: str) -> tuple[str, ...]:
    """Return the names in a `--arg` list such as `a=1 'b=two words' c:='[1]'`."""
    names: list[str] = []
    for token in shlex.split(arguments):
        match = re.match(r"([A-Za-z_]\w*)(?::=|=)", token)
        if not match:
            raise ReleaseError(f"run argument is not NAME=VALUE or NAME:=JSON: {token}")
        names.append(match.group(1))
    return tuple(names)


def verify_run(run: RunExample, documents: str) -> None:
    """Require the model ID and every argument name in the release docs.

    The ID counts in a medmlx command or as inline code (a model table row); an
    argument name counts as inline code, `name=`, `name:` or a JSON key.
    """
    model_id = re.escape(run.model_id)
    if not re.search(rf"medmlx (?:describe|run|readiness|setup) {model_id}(?![\w-])|`{model_id}`", documents):
        raise ReleaseError(f"model ID {run.model_id} is absent from the release docs")
    for name in run.arguments:
        if not re.search(rf"`{name}`|\b{name}=|\b{name}:|\"{name}\"", documents):
            raise ReleaseError(f"{run.model_id} argument {name} is absent from the release docs")


def verify_release(
    release: Release,
    python: str,
    examples: list[Example],
    fetch: Callable[[str], str] = fetch_text,
    models: tuple[Model, ...] = (),
    references: tuple[Reference, ...] = (),
    runs: tuple[RunExample, ...] = (),
) -> tuple[str, str]:
    """Check one release and return its README path and text at the tag."""
    data = mapping(json.loads(fetch(f"https://pypi.org/pypi/{release.name}/json")))
    info = mapping(data["info"])
    if canonicalize_name(string(info["name"])) != canonicalize_name(release.name):
        raise ReleaseError("PyPI returned a different distribution")
    if string(info["version"]) != release.version:
        raise ReleaseError(
            f"site reviews {release.version}, PyPI publishes {info['version']}; "
            "review the release and update site/releases.js"
        )
    files = [mapping(item) for item in sequence(data["urls"])]
    if not files or all(item.get("yanked") is not False for item in files):
        raise ReleaseError(f"PyPI {release.version} has no non-yanked distributions")
    python_requirement = SpecifierSet(string(info["requires_python"]))
    if Version(python) not in python_requirement:
        raise ReleaseError(
            f"documented Python {python} does not satisfy {python_requirement}"
        )

    def source(path: str) -> str:
        return fetch(
            f"https://raw.githubusercontent.com/{release.repository}/v{release.version}/{path}"
        )

    config = mapping(tomllib.loads(source("pyproject.toml")))
    project = mapping(config["project"])
    if canonicalize_name(string(project["name"])) != canonicalize_name(release.name):
        raise ReleaseError("repository tag declares a different distribution")
    if project_version(project, config, source) != release.version:
        raise ReleaseError("repository tag version differs from PyPI")
    if SpecifierSet(string(project["requires-python"])) != python_requirement:
        raise ReleaseError("repository tag Python requirement differs from PyPI")
    extras = set(mapping(project.get("optional-dependencies", {})))
    published_extras = {
        string(value) for value in sequence(info.get("provides_extra") or [])
    }
    if extras != published_extras:
        raise ReleaseError("repository tag extras differ from PyPI")
    readme_path = string(project["readme"])
    readme = source(readme_path)
    if readme.strip() != string(info["description"]).strip():
        raise ReleaseError(
            "repository tag README differs from the published PyPI description"
        )

    if release.card:
        if release.card.version != release.version:
            raise ReleaseError("model card must be reviewed for the displayed release version")
        normalized = " ".join(readme.split())
        for excerpt in release.card.excerpts:
            if " ".join(excerpt.split()) not in normalized:
                raise ReleaseError(f"model-card excerpt is absent from the tagged README: {excerpt}")

    documents = {readme_path: readme}

    def document(path: str) -> str | None:
        """Fetch an optional docs page once; None when the tag doesn't have it."""
        if path not in documents:
            try:
                documents[path] = source(path)
            except ReleaseError:
                return None
        return documents[path]

    for example in examples:
        if example.distribution != release.name:
            continue
        # The README is the user documentation. Older tags kept detailed
        # commands in a docs page, so that page is the fallback.
        found = next(
            (
                path
                for path in dict.fromkeys((readme_path, example.path))
                if (text := document(path)) is not None
                and documented(example.command, text)
            ),
            None,
        )
        if found is None:
            also = "" if example.path == readme_path else f" and {readme_path}"
            raise ReleaseError(
                f"site command is absent from the release's {example.path}{also}: {example.command}"
            )
        for line in example.command.replace("\\\n", " ").splitlines():
            if INSTALL.match(line.strip()) and not documented_install(
                line, documents[found]
            ):
                raise ReleaseError(
                    f"site install differs from the release's {found}: {line.strip()}"
                )
        for token in command_tokens(example.command):
            try:
                requirement = Requirement(token)
            except InvalidRequirement:
                continue
            if canonicalize_name(requirement.name) != canonicalize_name(release.name):
                continue
            if (
                not requirement.extras <= extras
                or Version(release.version) not in requirement.specifier
            ):
                raise ReleaseError(
                    f"site install requirement {token} is incompatible with the release"
                )

    for reference in references:
        if reference.distribution == release.name:
            verify_reference(reference, examples, mapping(project.get("scripts", {})), source)

    for model in models:
        if model.distribution != release.name:
            continue
        scripts = mapping(project.get("scripts", {}))
        for command in model.commands:
            verify_command(command, scripts, source)
        if not any(model.peak_memory in document for document in documents.values()):
            raise ReleaseError(f"peak memory {model.peak_memory} is absent from the release docs")
        verify_weights(model, fetch)

    for run in runs:
        if run.distribution == release.name:
            extra = [source(path) for path in run.docs]
            verify_run(run, "\n".join([readme, *extra]))
    return readme_path, readme


def resolve_installation(requirement: str, python: str, macos: str) -> None:
    """Resolve published wheels without installing packages or building source."""
    with tempfile.TemporaryDirectory(prefix="medmlx-site-resolve-") as directory:
        source = Path(directory) / "install.in"
        output = Path(directory) / "requirements.txt"
        source.write_text(requirement + "\n")
        result = subprocess.run(
            [
                "uv",
                "--no-config",
                "pip",
                "compile",
                "--default-index",
                "https://pypi.org/simple",
                "--python-version",
                python,
                "--python-platform",
                "aarch64-apple-darwin",
                "--only-binary",
                ":all:",
                # Index pages stay cached for minutes after a release.
                "--refresh",
                "--no-header",
                "--no-annotate",
                "--output-file",
                str(output),
                str(source),
            ],
            cwd=directory,
            env={
                **{
                    key: value
                    for key, value in os.environ.items()
                    if not key.startswith(("UV_", "PIP_")) and key != "GITHUB_TOKEN"
                },
                "MACOSX_DEPLOYMENT_TARGET": macos,
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if result.returncode:
            raise ReleaseError(
                f"Cannot resolve {requirement} on macOS {macos} / Python {python}: {result.stderr.strip()}"
            )


INSTALL = re.compile(r"^uv (?:tool install|pip install|add)\s")
# Install options that take a separate value, such as `--python 3.13`.
VALUE_OPTIONS = {"--python", "-p"}


def install_arguments(line: str) -> list[str]:
    """Return the requirement arguments of a `uv` install line, without options."""
    tokens = shlex.split(line)
    start = 3 if tokens[1] in {"tool", "pip"} else 2
    arguments: list[str] = []
    skip = False
    for token in tokens[start:]:
        if skip:
            skip = False
        elif token in VALUE_OPTIONS:
            skip = True
        elif not token.startswith("-"):
            arguments.append(token)
    return arguments


def installation_requirements(
    releases: list[Release], examples: list[Example]
) -> set[str]:
    """Resolve the reviewed version, even when a site's command allows upgrades.

    Each install line is resolved as one requirements file. A line may add
    companion packages its README documents, but must install a reviewed release.
    """
    reviewed = {release.name: release for release in releases}
    requirements: set[str] = set()
    for example in examples:
        for line in example.command.replace("\\\n", " ").splitlines():
            if not INSTALL.match(line.strip()):
                continue
            pinned: list[str] = []
            companions: list[str] = []
            for argument in install_arguments(line):
                requirement = Requirement(argument)
                release = reviewed.get(canonicalize_name(requirement.name))
                if release is None:
                    companions.append(str(requirement))
                    continue
                requirement.specifier = SpecifierSet(f"=={release.version}")
                pinned.append(str(requirement))
            if not pinned:
                raise ReleaseError(f"Unreviewed install requirement: {line.strip()}")
            requirements.add("\n".join(pinned + companions))
    return requirements


def main() -> int:
    match sys.argv[1:]:
        case []:
            readmes_file = None
        case ["--readmes", path]:
            readmes_file = Path(path)
        case _:
            print("Usage: python devtools/check_releases.py [--readmes FILE]", file=sys.stderr)
            return 2
    python, macos, releases, examples, models, references, runs, pins = load_catalog()
    readmes: dict[str, dict[str, str]] = {}
    failures: list[str] = []
    for url, revision, size in pins:
        try:
            verify_revision(url, revision, size, fetch_text)
        except ValueError as error:
            failures.append(str(error))
    with ThreadPoolExecutor(max_workers=6) as pool:
        checks = [
            (
                release,
                pool.submit(
                    verify_release,
                    release,
                    python,
                    examples,
                    fetch_text,
                    tuple(models),
                    tuple(references),
                    tuple(runs),
                ),
            )
            for release in releases
        ]
        for release, check in checks:
            try:
                readme_path, readme = check.result()
                readmes[release.name] = {"path": readme_path, "text": readme}
            except (ValueError, KeyError, SyntaxError) as error:
                failures.append(f"{release.name}: {error}")
    if failures:
        print("Release check failed:\n  " + "\n  ".join(failures), file=sys.stderr)
        return 1
    requirements = installation_requirements(releases, examples)
    with ThreadPoolExecutor(max_workers=6) as pool:
        resolutions = [
            pool.submit(resolve_installation, requirement, python, macos)
            for requirement in sorted(requirements)
        ]
        for resolution in resolutions:
            resolution.result()
    # Written only after every check passes, so the export never publishes an unverified README.
    if readmes_file:
        readmes_file.write_text(json.dumps(readmes), encoding="utf-8")
    print(
        f"Verified {len(releases)} releases, {len(examples)} examples, "
        f"{sum(release.card is not None for release in releases)} model cards, {len(runs)} run commands "
        f"and {len(models) + len(pins)} weight pins "
        "against PyPI, repository tags and Hugging Face; "
        f"resolved {len(requirements)} installs for macOS {macos} arm64 / Python {python}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, subprocess.SubprocessError, OSError) as error:
        raise SystemExit(f"Release check failed: {error}") from error
