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
| `id-token: write` | connected mode through a CI connection (the `org` input) | the scan falls back to the baseline rules with the notice `connected_fallback`, or fails when the repository requires connected mode (see "Connected mode") |

In the default mode no secret is needed. The check result is always the scan's own result: a failed upload or comment never fails it.

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
| `org` | empty | Your Spellwarden organisation slug. Turns on connected mode through a CI connection: the job needs `permissions: id-token: write` (see "Connected mode"). |
| `api-key` | empty | A CI key (access CI) from Settings, API keys, for pipelines that cannot use a CI connection. Pass it from a secret. Use `org` or `api-key`, never both. |
| `upload` | `true` | In connected mode, `false` keeps the results on the runner instead of uploading them. The default `true` changes nothing: `connected.upload` in `.spellwarden/config.yml` still decides, and the upload is on when the file says nothing. |
| `default-branch` | empty | The default branch, for scheduled runs whose event payload does not name it. |
| `requirements-file` | empty | A test hook for the scanner's own release tests. Leave it empty. |

An input the Action does not accept (for example `fail-on: severe`, an `org` that is not a slug, or an `api-key` that is not a CI key) stops the job with an error that names the input, and exit code `2`. The error never shows the value of `api-key`.

The inputs `org`, `api-key`, `upload` and `default-branch` need `v1.2.0` or later and change nothing while `org` and `api-key` are empty.

## Outputs

| Output | Meaning |
|---|---|
| `exit-code` | `0` passed, `1` failed on findings, `2` incomplete or invalid (an unreadable file, a broken configuration, a bad input, no Python), `3` the lock file is absent or out of date. |
| `findings` | The number of findings not accepted in the baseline. |
| `sarif-file` | The path of the SARIF file, empty when none was written. |
| `connected` | `true` when the scan ran in connected mode, `fallback` when connected mode was not available and the scan used the baseline rules only, `false` otherwise. |
| `dashboard-url` | The address of the repository in your Spellwarden organisation when the results were uploaded, empty otherwise. |

The outputs are set even when the job fails before the scan (`2`, `0`, empty, `false` and empty).

## What it finds

38 rules: the 28 skill and MCP rules of the hosted product and ten rules for configuration files, such as a remote MCP server over plain HTTP, a credential written into a server configuration, a server launched from an unpinned package, a hook that pipes a downloaded script to a shell, or settings that switch off approval prompts. The [rule documentation](https://github.com/spellwarden-ai/spellwarden#rules) lists every rule with its severity and its OWASP and NIST mappings.

## Lock file and baseline

The lock file `.spellwarden/lock.json` records a hash of every skill, configuration document and plugin source the scanner found. With the lock committed, any change to them shows up as a failed check (exit code `3`) until someone reviews it and updates the lock. Create or update it with:

```sh
pipx run spellwarden==1.2.0 lock
```

The baseline `.spellwarden/baseline.yml` records findings your team accepted, each with a reason, the date it was added and an expiry date (at most 365 days, and 30 days for the rules that indicate malicious intent). Accepted findings stay visible in every report, marked as accepted. To accept every current finding once, when you adopt the Action:

```sh
pipx run spellwarden==1.2.0 baseline add --all --reason "Accepted when we adopted Spellwarden" --days 90
```

## Pull requests: settings and baseline from the base commit

On a pull request the scanner reads `.spellwarden/config.yml` and `.spellwarden/baseline.yml` from the commit the pull request targets, never from the pull request itself. Otherwise a pull request could add a risky server together with a setting that excludes it, or accept its own finding, and pass its own check. A change to either file therefore applies once it is merged, and the report says so with the notice `settings_from_base`. To accept a finding a pull request introduces, merge the baseline entry first, in a pull request of its own. The lock file is still read from the pull request, so a change to agent content shows up in review.

The default `actions/checkout` (depth 1, `persist-credentials: true`) works: the scanner fetches that one commit itself. If your workflow sets `persist-credentials: false` on a private repository, also set `fetch-depth: 0`; otherwise the scan uses the default settings and no baseline, with the notice `base_unavailable`. This protection assumes the workflow file itself is protected (a required workflow or ruleset, or CODEOWNERS review of `.github/workflows/`), because a pull request runs its own workflow file and could change the Action's inputs.

## Network access

On the network, the Action contacts the Python package index (PyPI) to install the scanner and dash.spellwarden.ai for the usage ping while telemetry is on, and, in connected mode, your code host's token endpoint and the Spellwarden API at dash.spellwarden.ai (or the proxy you configure). With `probe: true` it also contacts the remote MCP servers of the configuration.

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

**Outside the recipe in "Connected mode", never run this Action under `pull_request_target` with the pull request's code checked out.** That event runs with a write token and your secrets, and the scanner would read files written by the author of the pull request. The recipe is safe because its job checks out the code without credentials, runs nothing but this Action, and grants only the permissions it lists.

## Connected mode

Connected mode links the scan to your Spellwarden organisation. The organisation's CI policy decides which rules and which policy pack the run applies, the registry gate (Enterprise plan) fails a run that adds or changes a skill, MCP server, plugin or marketplace that the private registry does not admit, and the results go to the Repositories page of the dashboard. It needs a Team plan (a trial counts). Without `org` or `api-key`, and without `connected.required` in the settings file, the Action is the free scanner of the sections above, unchanged. The scanner does all of the work: the Action passes your inputs on and adds nothing. The scanner's README describes the [rules, the gate and every error code](https://github.com/spellwarden-ai/spellwarden#connected-mode).

### Turning it on with a CI connection

A CI connection is the recommended way. An administrator adds your GitHub account or organisation under Settings, CI connections in the dashboard; that page also shows the audience the token must carry (`https://dash.spellwarden.ai/ci/<slug>`), which the scanner requests itself. The workflow then proves who it is with the OIDC token GitHub issues, and no secret is stored in the repository. Pass the organisation's slug (the part of the dashboard address after `dash.spellwarden.ai/`) as `org`, and grant the job `id-token: write`:

```yaml
on: [push, pull_request]
permissions:
  contents: read
  id-token: write          # the OIDC token of the CI connection
  pull-requests: write     # the comment
jobs:
  spellwarden:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>
        with:
          fetch-depth: 0   # recommended, see below
      - uses: spellwarden-ai/scan@<sha>  # v1.2.0
        with:
          org: acme
```

`upload: false` keeps the results on the runner, whatever the settings file says. Leaving `upload` at its default leaves the choice to `connected.upload` in `.spellwarden/config.yml`. `default-branch` names the default branch for scheduled runs, whose event payload does not.

### Turning it on with a CI key

For a pipeline that cannot use a CI connection, create a key with access CI under Settings, API keys, store it as a secret and pass it as `api-key` instead of `org`:

```yaml
      - uses: spellwarden-ai/scan@<sha>  # v1.2.0
        with:
          api-key: ${{ secrets.SPELLWARDEN_API_KEY }}
```

A key is weaker than a connection, and you should know what it does not protect:

- The key is a secret that every workflow of the repository can read; a CI connection has none.
- Results uploaded with a key are shown as reported with a CI key. They are not counted as the repository's own state and do not count in the trust score.
- The first upload binds the repository to the key. After the old key is revoked, the next upload rebinds it.
- A key for read or write access is refused.

The Action checks `org` and `api-key` before it installs anything and refuses a value of the wrong shape, or both set, without printing the key. The key is masked in the log and reaches only the validation step and the scan step; the comment and result steps never see it.

### Pull requests from forks and outside contributions

GitHub gives a `pull_request` run from a fork no secrets and no OIDC token. That run cannot connect, so it falls back to the baseline rules (or fails, if the repository requires connected mode, see below). To scan outside contributions with your organisation's policy, use two jobs, so that each request is scanned once, by the job that has a credential. The `pull_request` job scans requests from the same repository. The `pull_request_target` job runs with the base repository's secrets and token: it checks out the head commit with `persist-credentials: false`, runs nothing but the Spellwarden Action, and grants only these permissions. The scanner treats `pull_request_target` as a request of the base repository, never as a fork run: it connects, gates and uploads, and the Action posts the comment.

```yaml
on:
  pull_request:
  pull_request_target:
jobs:
  same-repository:
    if: github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
      pull-requests: write
    steps:
      - uses: actions/checkout@<sha>
        with:
          fetch-depth: 0
      - uses: spellwarden-ai/scan@<sha>  # v1.2.0
        with:
          org: acme
  outside-contribution:
    if: github.event_name == 'pull_request_target' && github.event.pull_request.head.repo.full_name != github.repository
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
      pull-requests: write
    steps:
      - uses: actions/checkout@<sha>
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          persist-credentials: false
      - uses: spellwarden-ai/scan@<sha>  # v1.2.0
        with:
          org: acme
```

Dependabot pull requests run in the `same-repository` job and use the exemption described below. Do not add other steps to the `outside-contribution` job: they would run with the base repository's secrets next to code written by the author of the pull request.

### Recommended checkout and the base revision

Use `fetch-depth: 0` on the checkout. On a pull request the scanner reads the `connected` part of `.spellwarden/config.yml` (`pack` and `required`) and the baseline entries that accept registry findings from the base revision, never from the pull request, so a pull request cannot weaken connected mode by editing them. It also uses the base revision to judge only what the request adds or changes. When the base commit is not in the clone, the scanner uses the default settings and judges every item, with the notices `base_unavailable` and `gate_scope_all`. With `persist-credentials: false`, as in the recipe above, the scanner cannot fetch the base commit itself, which is why the full history helps.

### connected.required and the Dependabot exemption

When a run cannot connect (no OIDC token because the job lacks `id-token: write`, an empty key secret, a fork pull request, or the service cannot be reached before the first answer), the scan continues with the baseline rules, says so in the first line of its output and sets the `connected` output to `fallback`. A repository that must not scan without its organisation's policy sets `connected.required: true` in `.spellwarden/config.yml`; such a run then exits `2` with the error `connected_required`, and the comment says what to fix. After the first authenticated answer every connected failure exits `2` whatever `required` says, except a failed upload, which is only a notice.

One exemption: a Dependabot pull request whose diff puts nothing the gate would judge in scope runs in free mode with the notice `dependabot_free_mode`, so routine dependency updates do not need the `pull_request_target` job.

The `connected:` key of the settings file is refused by scanner versions before 1.2.0, so requiring connected mode presupposes 1.2.0 everywhere the repository is scanned: this Action at `v1.2.0` or later, the GitLab component at its 1.2.0, and any local `spellwarden` command.

### What leaves the runner

Only these: the token request to GitHub's token endpoint, the exchange of that token for a short-lived CI token, the session and policy requests, the registry check and the upload. No whole file is ever sent. A finding carries an excerpt of at most 300 characters of the matched line, with credentials masked. A server address leaves only as a hash, and the link that asks for its admission carries the address without user name, query or fragment. The upload sends the run (repository, commits, branch names, pull request number, run link) and the report, reduced. No credential is written to the log, the summary, a comment, a report, an output or the upload.

### Line endings

A package's identity is a hash over its bytes. A checkout that rewrites line endings (Windows `core.autocrlf`) produces a different package from the one the registry admitted, and the gate then reports it as not admitted. Check out the repository without line-ending conversion.

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

The Action's version is the scanner's:

| Action | Scanner |
|---|---|
| `v1.0.0` | runs `spellwarden` 1.0.0 |
| `v1.2.0` | runs `spellwarden` 1.2.0 and adds connected mode |

The JSON report, the lock file, the baseline and the settings file have [published JSON Schemas](https://github.com/spellwarden-ai/spellwarden/tree/main/schemas).

## Licence

Apache-2.0, see `LICENSE`.
