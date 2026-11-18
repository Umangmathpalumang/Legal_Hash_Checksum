#!/usr/bin/env python3
"""Check or renew the VPS outreach credential. Never runs an email batch."""
import argparse
import json
import shlex
import subprocess
import sys

REMOTE_READ = r"""
import ast, hashlib, json, os
from pathlib import Path
base = Path.home() / "lhc"
path = base / "token.json"
if path.is_symlink():
    raise SystemExit("Unexpected token file; no changes made.")
raw = path.read_bytes()
old = json.loads(raw)
client = json.loads((base / "credentials.json").read_text())
cfg = client.get("installed", {})
if cfg.get("client_id") != old.get("client_id"):
    raise SystemExit("OAuth client mismatch; no changes made.")
if cfg.get("token_uri") != "https://oauth2.googleapis.com/token":
    raise SystemExit("Unexpected OAuth endpoint; no changes made.")
scopes = old.get("scopes") or []
if set(scopes) != {"https://www.googleapis.com/auth/gmail.send"}:
    raise SystemExit("Unexpected existing Gmail scope; review before reauthorizing.")
senders = set()
for name in ("allahabad_emailer.py", "calcutta_emailer.py", "lhc_emailer.py"):
    for node in ast.parse((base / name).read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if any(isinstance(t, ast.Name) and t.id == "SENDER_EMAIL" for t in node.targets):
                senders.add(node.value.value)
primary = {email for email in senders if email.lower().endswith("@gmail.com")}
if len(primary) != 1:
    raise SystemExit("Cannot identify the original Gmail sender; review before reauthorizing.")
print(json.dumps({"client": client, "token": old, "sha256": hashlib.sha256(raw).hexdigest(),
                  "sender": primary.pop(), "scopes": scopes}))
"""

REMOTE_INSTALL = r"""
import hashlib, json, os, tempfile
from pathlib import Path
from datetime import datetime, timezone
import sys
data = json.load(sys.stdin)
root = Path.home() / "lhc"
p = root / "token.json"
if p.is_symlink():
    raise SystemExit("Unexpected token file; no changes made.")
original = p.read_bytes()
if hashlib.sha256(original).hexdigest() != data["sha256"]:
    raise SystemExit("The token changed during sign-in. Run the check again.")
old, new = json.loads(original), data["token"]
if not new.get("refresh_token") or not new.get("token"):
    raise SystemExit("Google did not supply reusable credentials; no changes made.")
if new.get("client_id") != old.get("client_id") or set(new.get("scopes", [])) != set(old.get("scopes", [])):
    raise SystemExit("OAuth client or scope changed; no changes made.")
if new.get("token_uri") != "https://oauth2.googleapis.com/token":
    raise SystemExit("Unexpected OAuth endpoint; no changes made.")
backup_dir = root / ".oauth-backups"
if backup_dir.is_symlink():
    raise SystemExit("Unexpected backup directory; no changes made.")
backup_dir.mkdir(mode=0o700, exist_ok=True)
os.chmod(backup_dir, 0o700)
fd, backup = tempfile.mkstemp(prefix="token-", suffix=".json", dir=backup_dir)
with os.fdopen(fd, "wb") as stream:
    stream.write(original)
    stream.flush()
    os.fsync(stream.fileno())
fd, staged = tempfile.mkstemp(prefix=".token-", suffix=".json", dir=root)
try:
    with os.fdopen(fd, "w") as stream:
        json.dump(new, stream)
        stream.flush()
        os.fsync(stream.fileno())
    if p.is_symlink() or p.read_bytes() != original:
        raise SystemExit("The token changed during recovery; no changes made.")
    os.replace(staged, p)
finally:
    if os.path.exists(staged):
        os.unlink(staged)
print("Shared Gmail token updated. Sent history, blacklist and schedules were preserved.")
"""


def remote(code, payload=None):
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "cedrf",
         "python3 -c " + shlex.quote(code)],
        input=None if payload is None else json.dumps(payload),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
    )
    if result.returncode:
        # Third-party libraries can include credentials in exception details.
        # Never relay an arbitrary traceback or an SSH response into a log.
        raise RuntimeError("The VPS check/update failed. No credential output was displayed.")
    return result.stdout


def request():
    from google.auth.transport.requests import Request

    class BoundedRequest(Request):
        def __call__(self, *args, **kwargs):
            kwargs["timeout"] = 12
            return super().__call__(*args, **kwargs)
    return BoundedRequest()


def refresh(bundle):
    from google.oauth2.credentials import Credentials
    credentials = Credentials.from_authorized_user_info(bundle["token"], bundle["scopes"])
    credentials.refresh(request())
    return credentials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reauthorize", action="store_true",
                        help="Renew the same send-only grant and restore the existing scheduled campaigns")
    args = parser.parse_args()
    try:
        bundle = json.loads(remote(REMOTE_READ))
        from google.auth.exceptions import RefreshError
        try:
            refresh(bundle)
            print("Gmail accepts the campaign token. No email was sent or token changed.")
            return
        except RefreshError:
            if not args.reauthorize:
                print("Google rejected the outreach refresh token. Browser sign-in is required.")
                print("Run this command again with --reauthorize. No settings changed.")
                raise SystemExit(2)

        if not sys.stdin.isatty():
            raise RuntimeError("Run --reauthorize in an interactive Terminal.")
        from google_auth_oauthlib.flow import InstalledAppFlow
        print(f"Sign in with the existing outreach Gmail account: {bundle['sender']}")
        print("This renews the existing send-only permission; it does not request inbox access.")
        print("Installing the token restores the existing scheduled campaigns. No batch is run here.")
        flow = InstalledAppFlow.from_client_config(
            bundle["client"], bundle["scopes"], autogenerate_code_verifier=True,
        )
        credentials = flow.run_local_server(
            host="localhost", bind_addr="127.0.0.1", port=0, timeout_seconds=300,
            open_browser=True, prompt="consent", login_hint=bundle["sender"],
            authorization_prompt_message="Complete Google sign-in in the browser window.",
            success_message="Authorization received. You can close this window and return to Terminal.",
        )
        if not credentials.refresh_token or not credentials.has_scopes(bundle["scopes"]):
            raise RuntimeError("Google did not grant the existing permission.")
        credentials.refresh(request())  # Verify the new refresh grant before replacing anything.
        installed = json.loads(credentials.to_json())
        if set(installed.get("scopes", [])) != set(bundle["scopes"]):
            raise RuntimeError("Google returned different permissions. No token was installed.")
        result = remote(REMOTE_INSTALL, {"token": installed, "sha256": bundle["sha256"]})
        print(result.strip())
        print("Gmail sign-in and refresh verified. No email was sent by this helper.")
    except SystemExit:
        raise
    except Exception:
        raise SystemExit("Recovery could not complete. No secrets were displayed. Check the account and retry.")


if __name__ == "__main__":
    main()
