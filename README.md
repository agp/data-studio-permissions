# Data Studio permission updater

A small Python CLI for bulk-managing sharing permissions on Looker Studio (Data Studio) reports via the [Data Studio REST API](https://developers.google.com/looker-studio/integrate/api/reference). The Data Studio UI has no bulk permission management, so this script iterates over a maintained list of report IDs and adds, revokes, audits, or inspects permissions in one shot.

## Why this exists

- The Data Studio UI only lets you share **one report at a time**.
- The Data Studio REST API exposes per-report permission endpoints but has **no list endpoint**, so report IDs must be maintained manually (see `reports.json`).

See `research-summary.md` for the longer write-up of what was tried and ruled out.

## Setup

### 1. Install dependencies

This project uses [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

### 2. Enable the Data Studio API

In the [Google Cloud Console](https://console.cloud.google.com/):

1. Pick (or create) a project.
2. **APIs & Services → Library** → search **Data Studio API** → **Enable**.

### 3. Create OAuth credentials

1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. Application type: **Desktop app**.
3. Download the JSON and save it as `credentials.json` in the project root.

### 4. Configure the OAuth consent screen

Under **APIs & Services → OAuth consent screen** (or **Audience** in the redesigned UI):

- If your project is in a Google Workspace org and only you (or your org) needs access, set **User type: Internal**. Refresh tokens never expire and no app verification is required.
- Otherwise, set User type: External and click **Publish app**. While the app is in *Testing*, refresh tokens expire after **7 days**, which will force a fresh consent flow each week.

Add the scope `https://www.googleapis.com/auth/datastudio` to the consent screen.

### 5. First run

```bash
uv run permissions.py
```

A browser window opens for consent. On success, `token.json` is written next to `credentials.json` and reused on subsequent runs. The script will silently refresh expired access tokens; you'll only be prompted again if the refresh token itself becomes invalid (revoked access, 6+ months unused, scope change, or Testing-status expiry).

## Usage

All commands default to the **test reports** list (`test_reports` in `reports.json`). Add `--all-reports` to target the production list, or `--report NAME_OR_ID` to target just one report from `reports.json`.

```bash
# Print current permissions for every report
uv run permissions.py

# Add a member as VIEWER (default role)
uv run permissions.py --add-member alice@example.com

# Add a member as EDITOR
uv run permissions.py --add-member alice@example.com --role EDITOR

# Add many members at once, each with its own role, from a JSON file
uv run permissions.py --add-members-file            # reads members.json
uv run permissions.py --add-members-file team.json  # or any path you pass

# Revoke all permissions for a member
uv run permissions.py --revoke-member alice@example.com

# Audit: list reports that are missing a member matching the given email or substring
uv run permissions.py --check-missing @example.com

# Target a single report by name or ID (from reports.json) instead of the whole list
uv run permissions.py --add-member alice@example.com --report "Q4 Revenue Dashboard"
# ...or a full report UUID that isn't in reports.json
uv run permissions.py --report xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Apply any of the above to the full production list
uv run permissions.py --add-member alice@example.com --all-reports
```

### Flags

| Flag | Purpose |
|---|---|
| *(none)* | Print current permissions for each report |
| `--add-member EMAIL` | Add `EMAIL` as a member (role from `--role`) |
| `--add-members-file [FILE]` | Add every member listed in `FILE` (default: `members.json`), each with its own role |
| `--revoke-member EMAIL` | Revoke all permissions for `EMAIL` |
| `--check-missing EMAIL` | Print reports where no member matches `EMAIL` (substring match — pass `@domain.com` to audit a whole domain) |
| `--role {VIEWER,EDITOR}` | Role to assign with `--add-member` (default: `VIEWER`) |
| `--report REPORT` | Target a single report by name or ID from `reports.json`, or a full report UUID not in the file (mutually exclusive with `--all-reports`) |
| `--all-reports` | Target the production `reports` list instead of `test_reports` |

## Maintaining `reports.json`

`reports.json` is gitignored (it holds your real report names and IDs). Copy the committed template to create it:

```bash
cp reports.example.json reports.json
```

`reports.json` has two top-level keys:

| Key | Targeted when |
|---|---|
| `reports` | `--all-reports` is passed |
| `test_reports` | default (no flag) |

Both map a human-readable name to the report ID. Report IDs come from the URL:

```
https://datastudio.google.com/reporting/{REPORT_ID}/page/...
```

Example:

```json
{
  "reports": {
    "Q4 Revenue Dashboard": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  },
  "test_reports": {
    "Sandbox": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
  }
}
```

To add a report: append an entry under the appropriate key. Use `test_reports` for anything you want to validate against before running with `--all-reports`.

## Bulk-adding members (`--add-members-file`)

To add several people in one run, list them in a JSON file. Copy `members.example.json` to `members.json` and edit:

```json
{
  "members": [
    { "email": "alice@example.com", "role": "VIEWER" },
    { "email": "bob@example.com", "role": "EDITOR" },
    { "email": "carol@example.com" }
  ]
}
```

- `role` is optional per entry and defaults to `VIEWER`; it must be `VIEWER` or `EDITOR`.
- A bare top-level list (without the `"members"` wrapper) is also accepted.
- Members are grouped by role, so each report takes one API call per distinct role rather than one per person.

Then run it against the target reports:

```bash
uv run permissions.py --add-members-file              # reads members.json
uv run permissions.py --add-members-file team.json    # or a custom path
uv run permissions.py --add-members-file --all-reports
```

`members.json` is gitignored (it may contain real addresses); `members.example.json` is the committed template.

## Files

| File | Purpose |
|---|---|
| `permissions.py` | The CLI |
| `reports.json` | Report ID lists (`reports`, `test_reports`) — **gitignored** |
| `reports.example.json` | Template for `reports.json` (copy and fill in your report IDs) |
| `members.example.json` | Template for `--add-members-file` (copy to `members.json`) |
| `credentials.json` | OAuth client secrets — **do not commit** |
| `token.json` | Cached user credentials — **do not commit** |
| `research-summary.md` | Background on why this approach was chosen |
| `CLAUDE.md` | Project notes for Claude Code |

## Troubleshooting

**`RefreshError` / consent prompt every run.** Your OAuth client is probably still in *Testing* publishing status, which caps refresh tokens at 7 days. Publish the app, or switch to User type: Internal if you have Workspace.

**`403` / API not enabled.** Confirm the Data Studio API is enabled in the same Cloud project your `credentials.json` was created in. The `project_id` field inside `credentials.json` tells you which project that is.

**`404` on a report.** The account that authenticated needs at least view access on the report. The API can only see reports the signed-in user can already see.
