"""
Bulk Data Studio permission updater.

Setup:
  uv sync          # install dependencies
  uv run permissions.py                          # print current permissions (default)
  uv run permissions.py --add-member EMAIL       # add the given member as VIEWER (use --role EDITOR to override)
  uv run permissions.py --add-members-file [FILE]  # add every member listed in FILE (default: members.json)
  uv run permissions.py --revoke-member EMAIL    # revoke all permissions for the given member
  uv run permissions.py --check-missing          # print only reports missing given member or part of member email
  uv run permissions.py --report NAME_OR_ID      # target a single report by name/ID from reports.json, or a raw report UUID
  uv run permissions.py --all-reports            # run against the full reports list (default is the test report only)
  uv run permissions.py --role ROLE              # role to assign with --add-member (default: VIEWER)
  
Authentication:
  1. Enable the Data Studio API in your Google Cloud project.
  2. Create an OAuth 2.0 Desktop client and download credentials.json.
  3. On first run, a browser window opens for consent; token.json is saved for reuse.

Report IDs are the alphanumeric string in the Data Studio URL:
  https://datastudio.google.com/reporting/{REPORT_ID}/page/...
"""

import argparse
import json
import os
import re

import requests
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/datastudio"]
BASE_URL = "https://datastudio.googleapis.com/v1"

with open("reports.json") as _f:
    _data = json.load(_f)
    REPORTS = _data["reports"]       # name -> id
    TEST_REPORTS = _data["test_reports"]  # name -> id

ROLES = ("VIEWER", "EDITOR")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")


def get_credentials() -> Credentials:
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                refreshed = True
            except RefreshError:
                creds = None
        if not refreshed:
            try:
                os.remove("token.json")
            except FileNotFoundError:
                pass
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds


def add_member(session: requests.Session, report_id: str, email: str, role: str) -> None:
    url = f"{BASE_URL}/assets/{report_id}/permissions:addMembers"
    payload = {"members": [f"user:{email}"], "role": role}
    response = session.post(url, json=payload)
    if response.ok:
        print(f"OK: {report_id}")
    else:
        print(f"FAILED: {report_id} — {response.status_code} — {response.text}")


def load_members(path: str) -> dict:
    """Read a members file and group emails by role.

    Accepts either {"members": [{"email": ..., "role": ...}, ...]} or a bare
    list of those entries. `role` is optional per entry and defaults to VIEWER.
    Returns {role: [email, ...]} so each role can be sent in one API call.
    """
    with open(path) as f:
        data = json.load(f)
    entries = data.get("members", []) if isinstance(data, dict) else data
    members_by_role: dict[str, list[str]] = {}
    for entry in entries:
        email = entry["email"]
        role = entry.get("role", "VIEWER")
        if role not in ROLES:
            raise SystemExit(f"Invalid role {role!r} for {email}; expected one of {ROLES}")
        members_by_role.setdefault(role, []).append(email)
    if not members_by_role:
        raise SystemExit(f"No members found in {path}")
    return members_by_role


def add_members(session: requests.Session, report_id: str, members_by_role: dict) -> None:
    url = f"{BASE_URL}/assets/{report_id}/permissions:addMembers"
    for role, emails in members_by_role.items():
        payload = {"members": [f"user:{e}" for e in emails], "role": role}
        response = session.post(url, json=payload)
        if response.ok:
            print(f"OK: {report_id} — {role}: {', '.join(emails)}")
        else:
            print(f"FAILED: {report_id} — {role} — {response.status_code} — {response.text}")


def revoke_member(session: requests.Session, report_id: str, email: str) -> None:
    url = f"{BASE_URL}/assets/{report_id}/permissions:revokeAllPermissions"
    payload = {"members": [f"user:{email}"]}
    response = session.post(url, json=payload)
    if response.ok:
        print(f"OK: {report_id}")
    else:
        print(f"FAILED: {report_id} — {response.status_code} — {response.text}")


def get_permissions(session: requests.Session, report_name: str, report_id: str) -> None:
    url = f"{BASE_URL}/assets/{report_id}/permissions"
    response = session.get(url)
    if not response.ok:
        print(f"FAILED: {report_name} ({report_id}) — {response.status_code} — {response.text}")
        return
    data = response.json()
    print(f"{report_name} ({report_id}):")
    print(json.dumps(data, indent=2))


def check_missing_member(session: requests.Session, report_name: str, report_id: str, domain: str) -> None:
    url = f"{BASE_URL}/assets/{report_id}/permissions"
    response = session.get(url)
    if not response.ok:
        print(f"FAILED: {report_name} ({report_id}) — {response.status_code} — {response.text}")
        return
    data = response.json()
    members = [
        m
        for role_data in data.get("permissions", {}).values()
        for m in role_data.get("members", [])
    ]
    if not any(domain in m for m in members):
        print(f"MISSING {domain}: {report_name} ({report_id})")


def resolve_report(value: str) -> tuple[str, str]:
    """Resolve a --report argument to (name, id).

    Matches a report name or ID in either reports.json collection (reports or
    test_reports). Falls back to treating the value as a raw report ID when it
    is a well-formed report UUID absent from the file; exits with an error
    otherwise.
    """
    for collection in (REPORTS, TEST_REPORTS):
        if value in collection:
            return value, collection[value]
        for name, report_id in collection.items():
            if report_id == value:
                return name, report_id
    if UUID_RE.match(value):
        return value, value
    raise SystemExit(
        f"Report {value!r} not found in reports.json — pass a name or ID from the file, or a full report UUID"
    )


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--add-member", metavar="EMAIL", help="Add the given email as a member (role set by --role)")
    group.add_argument(
        "--add-members-file",
        nargs="?",
        const="members.json",
        metavar="FILE",
        help="Add every member listed in FILE, each with its own role (default: members.json)",
    )
    group.add_argument("--revoke-member", metavar="EMAIL", help="Revoke all permissions for the given email")
    group.add_argument("--check-missing", metavar="EMAIL", help="Print only reports missing a member with the given email or email domain")
    parser.add_argument("--role", choices=ROLES, default="VIEWER", help="Role to assign with --add-member (default: VIEWER)")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--report", metavar="REPORT", help="Target a single report by name or ID from reports.json, or a full report UUID not in the file")
    scope.add_argument("--all-reports", action="store_true", help="Run against the full reports list (default: test report only)")
    args = parser.parse_args()

    members_by_role = load_members(args.add_members_file) if args.add_members_file else None

    creds = get_credentials()
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {creds.token}"})

    if args.report:
        name, report_id = resolve_report(args.report)
        reports = {name: report_id}
    else:
        reports = REPORTS if args.all_reports else TEST_REPORTS
    for report_name, report_id in reports.items():
        if args.add_member:
            add_member(session, report_id, args.add_member, args.role)
        elif args.add_members_file:
            add_members(session, report_id, members_by_role)
        elif args.revoke_member:
            revoke_member(session, report_id, args.revoke_member)
        elif args.check_missing:
            check_missing_member(session, report_name, report_id, args.check_missing)
        else:
            get_permissions(session, report_name, report_id)


if __name__ == "__main__":
    main()
