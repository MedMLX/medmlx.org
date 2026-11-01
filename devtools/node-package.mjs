#!/usr/bin/env node

// Run package.json scripts through the package manager that the project declares.
//
// The working directory must hold a package.json whose "packageManager" field is
// "npm|pnpm|yarn@<exact version>[+<integrity>]" and exactly one lockfile that
// belongs to that manager. The installed manager must report exactly that version
// before anything is installed or run, so a drifting host tool fails loudly
// instead of rewriting the lockfile.
// An integrity suffix is checked for format only; this wrapper does not verify a digest.
//
// Usage: node devtools/node-package.mjs <command> [script]
//   validate                check the manifest and lockfile, print them as JSON
//   inspect                 validate, then check the installed manager version
//   install                 frozen-lockfile install (npm ci, pnpm --frozen-lockfile,
//                           yarn --immutable, or --frozen-lockfile for yarn 1)
//                           This command does not disable package lifecycle scripts.
//   run <script>            run a script; fail if package.json does not define it
//   run-if-present <script> run a script, or skip with a message if undefined
// Exits 2 on any contract violation; otherwise it passes through the manager's status.

import { existsSync, lstatSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const LOCKFILES = new Map([
  ["pnpm-lock.yaml", "pnpm"],
  ["package-lock.json", "npm"],
  ["yarn.lock", "yarn"],
]);
const EXACT_SEMVER =
  /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*))*)?$/;
const COREPACK_INTEGRITY =
  /^(?:sha224\.[a-f0-9]{56}|sha256\.[a-f0-9]{64}|sha384\.[a-f0-9]{96}|sha512\.[a-f0-9]{128})$/;

/** Report a contract violation and exit with the wrapper's error status. */
function fail(message) {
  console.error(`[node-package] ERROR: ${message}`);
  process.exit(2);
}

/** Return whether a regular, non-symlink file exists at a repository path. */
function hasSafeFile(root, name) {
  const path = resolve(root, name);
  if (!existsSync(path)) return false;
  let stats;
  try {
    stats = lstatSync(path);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    fail(`Cannot inspect ${path}: ${detail}`);
  }
  if (stats.isSymbolicLink()) fail(`${path} must not be a symbolic link.`);
  if (!stats.isFile()) fail(`${path} must be a regular file.`);
  return true;
}

/** Parse package.json and require its top-level value to be an object. */
function readManifest(root) {
  const path = resolve(root, "package.json");
  if (!hasSafeFile(root, "package.json")) fail(`Missing ${path}.`);
  try {
    const manifest = JSON.parse(readFileSync(path, "utf8"));
    if (
      manifest === null ||
      Array.isArray(manifest) ||
      typeof manifest !== "object"
    ) {
      fail("package.json must contain a JSON object.");
    }
    return manifest;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    fail(`Cannot parse package.json: ${detail}`);
  }
}

/** Validate and split the declared package manager and exact version. */
function parsePackageManager(value) {
  if (typeof value !== "string" || !value.includes("@")) {
    fail('package.json must declare "packageManager" as "name@version".');
  }
  const separator = value.indexOf("@");
  const name = value.slice(0, separator);
  const descriptor = value.slice(separator + 1).split("+");
  const version = descriptor[0];
  const integrity = descriptor[1];
  if (![...LOCKFILES.values()].includes(name)) {
    fail(`Unsupported package manager '${name}'. Use npm, pnpm, or yarn.`);
  }
  if (!version) fail(`packageManager '${value}' is missing a version.`);
  if (!EXACT_SEMVER.test(version)) {
    fail(
      `packageManager version '${version}' must be an exact semantic version.`,
    );
  }
  if (
    descriptor.length > 2 ||
    (descriptor.length === 2 && !integrity) ||
    (integrity && !COREPACK_INTEGRITY.test(integrity))
  ) {
    fail(`packageManager integrity suffix in '${value}' is invalid.`);
  }
  return { descriptor: value, name, version };
}

/** Match the declared manager to the repository's sole lockfile. */
function loadContract(root) {
  const manifest = readManifest(root);
  const present = [...LOCKFILES].filter(([file]) => hasSafeFile(root, file));
  if (present.length !== 1) {
    fail(`Expected exactly one lockfile; found ${present.length}.`);
  }
  const [lockfile, lockManager] = present[0];
  const declared = parsePackageManager(manifest.packageManager);
  if (declared.name !== lockManager) {
    fail(
      `packageManager '${declared.name}' conflicts with ${lockfile} (${lockManager}).`,
    );
  }
  return {
    manifest,
    lockfile,
    manager: declared.name,
    version: declared.version,
    descriptor: declared.descriptor,
  };
}

/** Require the installed package manager version to match the manifest. */
function verifyInstalledVersion(contract) {
  const result = spawnSync(contract.manager, ["--version"], {
    encoding: "utf8",
    maxBuffer: 64 * 1024,
    timeout: 10_000,
  });
  if (result.error)
    fail(`Cannot execute ${contract.manager}: ${result.error.message}`);
  if (result.status !== 0)
    fail(
      result.signal
        ? `${contract.manager} --version terminated by ${result.signal}.`
        : `${contract.manager} --version exited ${result.status}.`,
    );
  const installed = result.stdout.trim();
  if (installed !== contract.version) {
    fail(
      `Installed ${contract.manager} ${installed} does not match packageManager ${contract.version}.`,
    );
  }
}

/** Run the verified package manager and propagate its exit status. */
function runManager(contract, args) {
  verifyInstalledVersion(contract);
  const result = spawnSync(contract.manager, args, { stdio: "inherit" });
  if (result.error)
    fail(`Cannot execute ${contract.manager}: ${result.error.message}`);
  if (result.signal)
    fail(`${contract.manager} terminated by ${result.signal}.`);
  if (result.status !== 0) process.exit(result.status ?? 2);
}

/** Select the manager's frozen-lockfile install arguments. */
function installArgs(contract) {
  if (contract.manager === "npm") return ["ci"];
  if (contract.manager === "pnpm") return ["install", "--frozen-lockfile"];
  const major = Number.parseInt(contract.version.split(".")[0], 10);
  return ["install", major === 1 ? "--frozen-lockfile" : "--immutable"];
}

/** Run a declared script, or skip it when explicitly marked optional. */
function runScript(contract, script, optional) {
  const command = contract.manifest.scripts?.[script];
  if (typeof command !== "string" || command.length === 0) {
    if (optional) {
      console.log(
        `[node-package] Optional script '${script}' is not defined; skipped.`,
      );
      return;
    }
    fail(`Required package.json script '${script}' is not defined.`);
  }
  runManager(contract, ["run", script]);
}

/** Validate CLI arguments and execute the requested package-manager action. */
function main() {
  const [command, argument, ...extra] = process.argv.slice(2);
  if (!command || extra.length > 0) {
    fail(
      "Usage: node devtools/node-package.mjs validate|install|inspect|run <script>|run-if-present <script>",
    );
  }
  const contract = loadContract(process.cwd());
  if (command === "validate" && argument === undefined) {
    console.log(
      JSON.stringify({
        manager: contract.manager,
        version: contract.version,
        descriptor: contract.descriptor,
        lockfile: contract.lockfile,
      }),
    );
  } else if (command === "inspect" && argument === undefined) {
    verifyInstalledVersion(contract);
    console.log(
      JSON.stringify({
        manager: contract.manager,
        version: contract.version,
        descriptor: contract.descriptor,
        lockfile: contract.lockfile,
      }),
    );
  } else if (command === "install" && argument === undefined) {
    runManager(contract, installArgs(contract));
  } else if (command === "run" && argument) {
    runScript(contract, argument, false);
  } else if (command === "run-if-present" && argument) {
    runScript(contract, argument, true);
  } else {
    fail("Invalid command or argument count.");
  }
}

main();
