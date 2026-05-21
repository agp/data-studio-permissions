# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This project automates bulk sharing permission updates for Data Studio reports via the Data Studio REST API and Google Apps Script.

## Background

See `research-summary.md` for full context. Key facts established in prior research:

- Data Studio has **no bulk permission management in the UI** — reports must be shared one at a time
- Data Studio reports are **not stored in Google Drive** as accessible Drive files — `DriveApp` cannot enumerate or modify them
- The **Data Studio REST API** (`datastudio.googleapis.com/v1`) is the correct interface for programmatic permission management
- There is **no asset list endpoint** in the API — report IDs must be supplied explicitly

## API Reference

**Base URL:** `https://datastudio.googleapis.com/v1`

**Full reference:** https://developers.google.com/looker-studio/integrate/api/reference

**Permissions endpoints:**

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/v1/assets/{assetName}/permissions` | Get permissions for a report |
| PATCH | `/v1/assets/{assetName}/permissions` | Update/replace permissions |
| POST | `/v1/assets/{assetName}/permissions:addMembers` | Add members to a report |
| POST | `/v1/assets/{assetName}/permissions:revokeAllPermissions` | Revoke members' permissions |

`{assetName}` = report ID from the Data Studio URL.

**OAuth scope:** `https://www.googleapis.com/auth/datastudio`

## Development Setup

```bash
uv sync          # install dependencies into .venv
uv run permissions.py  # run the script
uv add <package> # add a new dependency
```

## Implementation Approach

The intended implementation is a **Python script** using the `requests` library (or `google-api-python-client`) to call the Data Studio REST API, iterating over a manually maintained list of report IDs.

Authentication uses OAuth2 via `google-auth-oauthlib` for user credentials, or a service account if the reports are owned by a Google Workspace service account.

See `permissions.py` for the working code scaffold.

## reports.json Structure

`reports.json` contains two top-level keys:

| Key | Purpose |
|---|---|
| `reports` | Production reports — targeted when `--all-reports` is passed |
| `test_reports` | Sandbox/test reports — targeted by default (no flag needed) |

Both are objects mapping a human-readable report name to its Data Studio report ID (the alphanumeric UUID in the report URL). Example:

```json
{
  "reports": {
    "My Report": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  },
  "test_reports": {
    "Test Permissions Report": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
  }
}
```

To add a report, append an entry to the appropriate key. Report IDs come from the Data Studio URL:
`https://datastudio.google.com/reporting/{REPORT_ID}/page/...`

`reports.json` is gitignored (real report names/IDs); `reports.example.json` is the committed template (`cp reports.example.json reports.json`).

### Report scope flags

| Flag | Scope |
|---|---|
| *(none)* | `test_reports` only |
| `--all-reports` | full `reports` list |
| `--report NAME_OR_ID` | a single report resolved from `reports.json` by name or ID |

`--report` and `--all-reports` are mutually exclusive. `resolve_report()` searches both `reports` and `test_reports` and exits with an error if the value matches neither a name nor an ID — it does not accept arbitrary IDs absent from the file.

## Members File (`--add-members-file`)

`--add-members-file [FILE]` bulk-adds members from a JSON file (default `members.json`). The file is either a `{"members": [...]}` object or a bare list of entries; each entry is `{"email": ..., "role": ...}` where `role` is optional and defaults to `VIEWER` (must be `VIEWER` or `EDITOR`). Example:

```json
{
  "members": [
    { "email": "alice@example.com", "role": "VIEWER" },
    { "email": "bob@example.com", "role": "EDITOR" },
    { "email": "carol@example.com" }
  ]
}
```

`load_members()` groups emails by role so each report takes one `addMembers` API call per distinct role rather than one per person. It runs before authentication, so a malformed file fails fast without triggering the OAuth flow. `members.json` is gitignored (may contain real addresses); `members.example.json` is the committed template.

## Known Constraints

1. No list endpoint — report IDs must be hardcoded or maintained in a separate source (e.g. a CSV or Google Sheet)
2. API endpoint field names for the PATCH `Permissions` resource body should be verified against official docs before use
3. The Data Studio API must be enabled in the associated Google Cloud project
4. OAuth2 credentials (`credentials.json`) must be downloaded from the Google Cloud Console; the required scope is `https://www.googleapis.com/auth/datastudio`

## What Was Ruled Out

- Google Apps Script — replaced by Python for easier local execution and version control
- `DriveApp.getFilesByType('application/x-looker-studio')` — does not work; reports are not Drive files
- Looker API (enterprise) — separate product, unrelated to Data Studio
- Data Studio UI — no bulk operations exist
