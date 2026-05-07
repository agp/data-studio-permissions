# Research Summary: Data Studio Bulk Permissions

## Findings

### Data Studio vs Looker (important distinction)
- **Looker** — enterprise BI platform with a full REST API covering users, content, permissions, folders
- **Data Studio** — free Google report tool with a limited API; the two are unrelated for this purpose

### Storage
Data Studio reports are stored in a proprietary storage service managed by Data Studio, not in Google Drive. They do not appear in Drive search results and cannot be accessed via `DriveApp` in Apps Script.

### UI Limitations
No bulk permission management exists in the Data Studio UI, including in Data Studio Pro. Each report must be shared individually through the Share button.

### API
A Data Studio REST API exists at `https://datastudio.googleapis.com/v1`. It provides permission read/write endpoints but **no endpoint to list all assets owned by a user**. This is the critical limitation for bulk operations — there is no programmatic way to discover all your reports; IDs must be known in advance.

Official reference: https://developers.google.com/looker-studio/integrate/api/reference

Permissions-specific docs:
- GET: https://developers.google.com/looker-studio/integrate/api/reference/permissions/get
- PATCH: https://developers.google.com/looker-studio/integrate/api/reference/permissions/patch

## Viable Automation Path

1. Maintain a list of report IDs (manually, or sourced from a Google Sheet)
2. Use Google Apps Script with `UrlFetchApp` to call the Data Studio REST API
3. Authenticate via `ScriptApp.getOAuthToken()` with the `datastudio` OAuth scope
4. PATCH permissions for each report ID in the list
