"""
Bulk Data Studio permission updater.

Setup:
  uv sync          # install dependencies
  uv run permissions.py                          # print current permissions (default)
  uv run permissions.py --add-member EMAIL       # add the given member as VIEWER (use --role EDITOR to override)
  uv run permissions.py --revoke-member EMAIL    # revoke all permissions for the given member
  uv run permissions.py --check-missing          # print only reports missing given member or part of member email
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

import requests
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


def get_credentials() -> Credentials:
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
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


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--add-member", metavar="EMAIL", help="Add the given email as a member (role set by --role)")
    group.add_argument("--revoke-member", metavar="EMAIL", help="Revoke all permissions for the given email")
    group.add_argument("--check-missing", metavar="EMAIL", help="Print only reports missing a member with the given email or email domain")
    parser.add_argument("--role", choices=ROLES, default="VIEWER", help="Role to assign with --add-member (default: VIEWER)")
    parser.add_argument("--all-reports", action="store_true", help="Run against the full reports list (default: test report only)")
    args = parser.parse_args()

    creds = get_credentials()
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {creds.token}"})

    reports = REPORTS if args.all_reports else TEST_REPORTS
    for report_name, report_id in reports.items():
        if args.add_member:
            add_member(session, report_id, args.add_member, args.role)
        elif args.revoke_member:
            revoke_member(session, report_id, args.revoke_member)
        elif args.check_missing:
            check_missing_member(session, report_name, report_id, args.check_missing)
        else:
            get_permissions(session, report_name, report_id)


if __name__ == "__main__":
    main()
