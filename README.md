# Spellwarden Scan

A GitHub Action that checks the agent content in a repository on every pull request: agent skills (`SKILL.md` packages), Claude Code plugin marketplaces and manifests, MCP server configurations (`.mcp.json`, `.vscode/mcp.json`, `.cursor/mcp.json`) and Claude Code settings and hook files. It runs the same open-source rules as the hosted Spellwarden product, on your runner. It reports findings as code scanning alerts, in one pull request comment it keeps up to date, and in the job summary. It fails the check at the severity you choose.

The scanner is [`spellwarden`](https://github.com/spellwarden-ai/spellwarden) (Apache-2.0). The Action installs the exact release named in `requirements.txt`, checking every file against its pinned hash.

## Quick start

```yaml
on: [pull_request]
permissions:
  contents: read
  security-events: write   # code scanning alerts
  pull-requests: write     # the comment
jobs:
  spellwarden:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>   # the defaults (depth 1, persisted credentials) let the scanner fetch the base commit
      - uses: spellwarden-ai/scan@<sha>  # v1.0.0
```

Pin the Action by the commit of a release tag, as above, never by a branch. "Verifying a release" below shows how to check that the commit is the signed release.

## Permissions

Your workflow grants permissions; the Action never asks for more. It needs:

| Permission | For | When it is missing |
|---|---|---|
| `contents: read` | reading the checkout | the job cannot run |
| `security-events: write` | uploading the SARIF file to code scanning | a warning (`sarif_upload_failed`); the check result does not change |
| `pull-requests: write` | the pull request comment | a notice (`comment_permission`); the check result does not change |

No secret is needed. The check result is always the scan's own result: a failed upload or comment never fails it.

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `path` | `.` | The directory to scan. Paths in the lock, the baseline and the report are relative to it. |
| `fail-on` | `high` | The lowest severity that fails the check: `critical`, `high`, `medium`, `low` or `never`. |
| `locked` | `auto` | `auto` checks the lock file when `.spellwarden/lock.json` exists, `true` requires it, `false` skips it. |
| `probe` | `false` | `true` probes each remote MCP server in the configuration from the runner (see "Probing"). |
| `probe-private` | `false` | `true` lets the probe reach the configured servers' own private addresses (never a link-local address, and never one a server's answer or redirect points to), honoured only on a push, schedule or manual run of a protected branch or tag. |
| `comment` | `true` | Keep one comment with the report on the pull request. |
| `sarif-upload` | `true` | Upload the SARIF file to code scanning. |
| `telemetry` | `true` | `false` switches off the usage ping (see "Usage ping"). |
| `token` | `${{ github.token }}` | The token for the comment and the upload. |
| `requirements-file` | empty | A test hook for the scanner's own release tests. Leave it empty. |

An input the Action does not accept (for example `fail-on: severe`) stops the job with an error that names the input, and exit code `2`.

## Outputs

| Output | Meaning |
|---|---|
| `exit-code` | `0` passed, `1` failed on findings, `2` incomplete or invalid (an unreadable file, a broken configuration, a bad input, no Python), `3` the lock file is absent or out of date. |
| `findings` | The number of findings not accepted in the baseline. |
| `sarif-file` | The path of the SARIF file, empty when none was written. |

The outputs are set even when the job fails before the scan (`2`, `0` and empty).

## What it finds

38 rules: the 28 skill and MCP rules of the hosted product and ten rules for configuration files, such as a remote MCP server over plain HTTP, a credential written into a server configuration, a server launched from an unpinned package, a hook that pipes a downloaded script to a shell, or settings that switch off approval prompts. The [rule documentation](https://github.com/spellwarden-ai/spellwarden#rules) lists every rule with its severity and its OWASP and NIST mappings.

## Lock file and baseline

The lock file `.spellwarden/lock.json` records a hash of every skill, configuration document and plugin source the scanner found. With the lock committed, any change to them shows up as a failed check (exit code `3`) until someone reviews it and updates the lock. Create or update it with:

```sh
pipx run spellwarden==1.0.0 lock
```

The baseline `.spellwarden/baseline.yml` records findings your team accepted, each with a reason, the date it was added and an expiry date (at most 365 days, and 30 days for the rules that indicate malicious intent). Accepted findings stay visible in every report, marked as accepted. To accept every current finding once, when you adopt the Action:

```sh
pipx run spellwarden==1.0.0 baseline add --all --reason "Accepted when we adopted Spellwarden" --days 90
```

## Pull requests: settings and baseline from the base commit

On a pull request the scanner reads `.spellwarden/config.yml` and `.spellwarden/baseline.yml` from the commit the pull request targets, never from the pull request itself. Otherwise a pull request could add a risky server together with a setting that excludes it, or accept its own finding, and pass its own check. A change to either file therefore applies once it is merged, and the report says so with the notice `settings_from_base`. To accept a finding a pull request introduces, merge the baseline entry first, in a pull request of its own. The lock file is still read from the pull request, so a change to agent content shows up in review.

The default `actions/checkout` (depth 1, `persist-credentials: true`) works: the scanner fetches that one commit itself. If your workflow sets `persist-credentials: false` on a private repository, also set `fetch-depth: 0`; otherwise the scan uses the default settings and no baseline, with the notice `base_unavailable`. This protection assumes the workflow file itself is protected (a required workflow or ruleset, or CODEOWNERS review of `.github/workflows/`), because a pull request runs its own workflow file and could change the Action's inputs.

## Usage ping

When the scan runs in CI and telemetry is on, the scanner sends one request per run to `https://dash.spellwarden.ai/api/public/ping`. It holds exactly five fields: the schema number, the scanner version, the rules version, the CI kind (`github`, `gitlab` or `other`) and a hashed installation identity. No file, path, finding or repository name is sent. Runs on a developer's machine send nothing.

The ping is **pseudonymous, not anonymous**. The identity is the SHA-256 of `spellwarden-ping-v1:github:<host>:<numeric owner id>`. Anyone who knows an owner's id can compute the same hash. One identity stands for one account or organisation on one GitHub host: the same company on GitHub and on GitLab counts twice, and GitHub Enterprise Server is its own identity. Renaming the account does not change it, because the owner id is stable.

The server keeps one row per identity and ISO week: the number of runs, when it was first and last seen, the last scanner and rules versions, and the CI kind. Rows are deleted 400 days after their week ends. The row holds no address: the rate limiter keeps the sending address for one hour, and like every request to the service the ping appears in the technical logs, kept for 90 days, with the address it arrived from (usually one of the content delivery network's). We use the count to see how many teams run the scanner in CI.

To switch it off, set the input `telemetry: false`, or `DO_NOT_TRACK=1` or `SPELLWARDEN_TELEMETRY=off` in the job, or `telemetry: false` in `.spellwarden/config.yml` (on a pull request, the file of the base commit).

## Probing MCP servers

With `probe: true`, the scanner sends the unauthenticated MCP handshake to each remote server in the configuration, from the runner, and reports its transport, authentication mode, protocol version and readiness for the 2026-07-28 protocol. It sends no header, token, environment value or argument from your configuration, only the protocol's own requests to the configured URL. It follows the hosted product's rules: HTTPS only, at most 9 requests per server, 50 servers and 300 requests per run, 120 seconds in all.

Private addresses (`10.0.0.0/8` and the like) are refused unless `probe-private: true` is set. Even then it applies only on a push, schedule or manual run (`workflow_dispatch`) of a protected branch or tag: on a pull request, or after a comment or another workflow's run, whoever wrote the change controls the endpoints in it. It then allows only the private addresses of the configured servers themselves, never a link-local address such as the cloud metadata service, and never an address that a server's answer or redirect points to. On a pull request from a fork, probing is switched off altogether.

## Pull requests from forks and Dependabot

GitHub gives these runs a read-only token. The scan, the summary and the check result work as usual. The comment and the code scanning upload are skipped with a notice.

**Never run this Action under `pull_request_target` with the pull request's code checked out.** That event runs with a write token and your secrets, and the scanner would read files written by the author of the pull request.

## Supported runners

Linux, macOS and Windows runners with Python 3.11 or newer. GitHub-hosted runners have it. Elsewhere, add `actions/setup-python` before this step. The Action installs the scanner into its own virtual environment and does not change the job's Python.

## Verifying a release

Each release tag `vX.Y.Z` is signed with the maintainer's SSH key. The `vX` tag moves to the latest release of that major version. To check a tag against the published signing key:

```sh
git clone https://github.com/spellwarden-ai/scan && cd scan
curl -fsSLO https://raw.githubusercontent.com/spellwarden-ai/spellwarden/main/allowed_signers
git -c gpg.ssh.allowedSignersFile=allowed_signers verify-tag v1.0.0
```

The release manifest attached to the scanner's GitHub release ties the Action commit, the GitLab component commit, the PyPI files and the container image together. It is itself attested; the scanner's README has the commands.

## Versions

The Action's version is the scanner's: `v1.0.0` runs `spellwarden` 1.0.0. The JSON report, the lock file, the baseline and the settings file have [published JSON Schemas](https://github.com/spellwarden-ai/spellwarden/tree/main/schemas).

## Licence

Apache-2.0, see `LICENSE`.
