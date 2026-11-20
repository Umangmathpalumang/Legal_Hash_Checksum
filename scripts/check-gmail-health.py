#!/usr/bin/env python3
"""Probe existing Gmail credentials; notify only the site owner, never a campaign."""
import argparse
import ast
import base64
import fcntl
import json
import os
from pathlib import Path
import shlex
import smtplib
import ssl
import subprocess
import sys
import tempfile
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from urllib import error, parse, request


OWNER = "umangmathpal@gmail.com"
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REMOTE_PATH = "/home/ubuntu/.local/lib/lhc-mail-health/check-gmail-health.py"
STATE_DIR = Path.home() / ".local/state/lhc-mail-health"
MAC_ROOT = "/Users/umang/Desktop/legalchecksum/Legal_Hash_Checksum-ui"
MAC_PYTHON = "/Users/umang/.pyenv/versions/3.10.11/bin/python"
LABELS = {"feedback": "Website feedback (Gmail app password)",
          "outreach": "Scheduled outreach (Gmail OAuth)"}
REMINDER_SECONDS = 24 * 60 * 60


def feedback_settings():
    try:
        pid = subprocess.check_output(
            ["/bin/systemctl", "show", "hashverify.service", "--property=MainPID", "--value"],
            text=True, timeout=10,
        ).strip()
        if not pid.isdigit() or int(pid) == 0:
            return "service_unavailable", None
        raw = Path("/proc/{}/environ".format(pid)).read_bytes()
        env = dict(p.split(b"=", 1) for p in raw.split(b"\0") if b"=" in p)
        sender = env.get(b"GMAIL_USER", b"").decode().strip()
        password = env.get(b"GMAIL_PASS", b"").decode()
        if not sender or not password:
            return "config_error", None
        return "ok", (sender, password)
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        return "service_unavailable", None


def smtp_connection(settings):
    connection = smtplib.SMTP_SSL(
        "smtp.gmail.com", 465, timeout=12, context=ssl.create_default_context())
    try:
        connection.ehlo()
        connection.login(*settings)
        return connection
    except Exception:
        connection.close()
        raise


def check_feedback():
    status, settings = feedback_settings()
    if status != "ok":
        return status, None
    try:
        with smtp_connection(settings):
            pass
        return "ok", settings
    except smtplib.SMTPAuthenticationError:
        return "auth_failed", None
    except (OSError, smtplib.SMTPException):
        return "network_error", None


def check_outreach():
    try:
        root = Path.home() / "lhc"
        token_path = root / "token.json"
        if token_path.is_symlink():
            return "config_error", None
        token = json.loads(token_path.read_text())
        client = json.loads((root / "credentials.json").read_text()).get("installed", {})
        if (token.get("token_uri") != TOKEN_URL or client.get("token_uri") != TOKEN_URL
                or token.get("client_id") != client.get("client_id")
                or set(token.get("scopes", [])) != {SEND_SCOPE}):
            return "config_error", None
        # Validate the existing sender without importing or executing any mailer.
        senders = set()
        for name in ("allahabad_emailer.py", "calcutta_emailer.py", "lhc_emailer.py"):
            for node in ast.parse((root / name).read_text()).body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                    if any(isinstance(t, ast.Name) and t.id == "SENDER_EMAIL" for t in node.targets):
                        senders.add(node.value.value)
        if {s for s in senders if isinstance(s, str) and s.endswith("@gmail.com")} != {OWNER}:
            return "config_error", None
        data = {k: token[k] for k in ("client_id", "client_secret", "refresh_token")}
        if not all(data.values()):
            return "config_error", None
        data["grant_type"] = "refresh_token"
        req = request.Request(TOKEN_URL, data=parse.urlencode(data).encode())
        with request.urlopen(req, timeout=12) as response:
            result = json.load(response)
        if not result.get("access_token"):
            return "config_error", None
        # Access token stays in memory. No credential file is modified.
        return "ok", result["access_token"]
    except error.HTTPError as exc:
        try:
            reason = json.loads(exc.read()).get("error")
        except (ValueError, OSError):
            reason = None
        return ("auth_failed" if reason in ("invalid_grant", "invalid_client", "unauthorized_client")
                else "network_error"), None
    except (OSError, error.URLError):
        return "network_error", None
    except (ValueError, KeyError, TypeError, SyntaxError):
        return "config_error", None


def recovery_body(checks):
    lines = ["Legal Hash Checksum email authentication check", "",
             "Checked at: " + time.strftime("%Y-%m-%d %H:%M:%S %Z"), ""]
    for name, status in sorted(checks.items()):
        lines.append("{}: {}".format(LABELS[name], status))
    lines += ["", "If an authentication check failed, open Terminal on your Mac."]
    if checks.get("outreach") == "auth_failed":
        lines += ["", "Renew the existing outreach sign-in:",
                  MAC_PYTHON + " " + MAC_ROOT + "/scripts/reauthorize-outreach-gmail.py --reauthorize",
                  "Sign in with " + OWNER + ". This helper does not send a campaign batch."]
    if checks.get("feedback") == "auth_failed":
        lines += ["", "Replace the rejected website feedback app password:",
                  "1. Open https://myaccount.google.com/apppasswords and create an app password for lch-feedback.",
                  "2. Run:", MAC_PYTHON + " " + MAC_ROOT + "/scripts/update-feedback-gmail.py",
                  "3. Paste the new app password into the hidden Terminal prompt, not into chat or email."]
    lines += ["", "A network or service failure does not mean a password must be replaced.",
              "Check again from your Mac:",
              MAC_PYTHON + " " + MAC_ROOT + "/scripts/check-gmail-health.py --remote",
              "", "This monitor never runs a campaign or changes credentials, recipients, or campaign history.",
              "If both Gmail credentials fail, neither can deliver an email alert. The Codex check provides a separate notification."]
    return "\n".join(lines)


def send_owner_email(subject, body, checks, smtp_settings, oauth_access):
    """Use one working transport. Never retry an ambiguous delivery on the other."""
    msg = EmailMessage()
    msg["To"] = OWNER
    msg["Subject"] = "[Legal Hash Checksum] " + subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="legalhashchecksum.com")
    msg.set_content(body)
    try:
        if checks.get("feedback") == "ok" and smtp_settings:
            msg["From"] = smtp_settings[0]
            with smtp_connection(smtp_settings) as connection:
                refused = connection.send_message(msg, from_addr=smtp_settings[0], to_addrs=[OWNER])
            return "accepted_smtp" if not refused else "failed"
        if checks.get("outreach") == "ok" and oauth_access:
            msg["From"] = OWNER
            payload = json.dumps({"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).encode()
            req = request.Request(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send", data=payload,
                headers={"Authorization": "Bearer " + oauth_access, "Content-Type": "application/json"})
            with request.urlopen(req, timeout=12) as response:
                result = json.load(response)
            return "accepted_oauth" if result.get("id") else "failed"
        return "unavailable"
    except (OSError, ValueError, smtplib.SMTPException):
        return "failed"


def notification_kind(previous, checks, now):
    signature = "|".join(k + ":" + v for k, v in sorted(checks.items()) if v != "ok")
    if signature:
        if (signature != previous.get("notified_signature")
                or now - previous.get("last_notified_at", 0) >= REMINDER_SECONDS):
            return "failure", signature
    elif previous.get("notified_signature"):
        return "recovery", ""
    return None, signature


def save_state(state):
    fd, path = tempfile.mkstemp(prefix=".state-", dir=str(STATE_DIR))
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, STATE_DIR / "state.json")
    finally:
        if os.path.exists(path):
            os.unlink(path)


def read_state():
    try:
        return json.loads((STATE_DIR / "state.json").read_text())
    except (OSError, ValueError):
        return {}


def public_status(state, now):
    age = max(0, int(now - state.get("checked_at", 0)))
    return {"checks": state.get("checks", {}), "age_seconds": age,
            "stale": age > 2 * 60 * 60, "email_alert": state.get("email_alert", "none"),
            "pending_notification": state.get("pending_notification", False)}


def run_check(notify=False, test_email=False):
    STATE_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    with (STATE_DIR / "check.lock").open("a") as lock:
        os.chmod(STATE_DIR / "check.lock", 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "check_already_running"}))
            return 0
        previous = read_state()
        feedback, smtp_settings = check_feedback()
        outreach, oauth_access = check_outreach()
        checks = {"feedback": feedback, "outreach": outreach}
        now = time.time()
        kind, signature = notification_kind(previous, checks, now)
        state = {"checked_at": now, "checks": checks,
                 "notified_signature": previous.get("notified_signature", ""),
                 "last_notified_at": previous.get("last_notified_at", 0),
                 "email_alert": previous.get("email_alert", "none"),
                 "pending_notification": bool(kind)}
        if test_email:
            state["test_email"] = send_owner_email(
                "Email monitoring is enabled (setup test)",
                "Hourly VPS checks are enabled for feedback SMTP and outreach OAuth.\n"
                "You will receive an incident alert, at most one reminder per 24 hours for the same failure, "
                "and a recovery message.\n\n" + recovery_body(checks),
                checks, smtp_settings, oauth_access)
        if notify and kind:
            subject = "Email authentication needs attention" if signature else "Email authentication recovered"
            delivery = send_owner_email(subject, recovery_body(checks), checks, smtp_settings, oauth_access)
            state["email_alert"] = delivery
            if delivery.startswith("accepted_"):
                state.update(notified_signature=signature, last_notified_at=now, pending_notification=False)
        save_state(state)
        result = public_status(state, now)
        if test_email:
            result["test_email"] = state["test_email"]
        print(json.dumps(result))
        if test_email and not state["test_email"].startswith("accepted_"):
            return 2
        return 0 if all(v == "ok" for v in checks.values()) else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true", help="Run the installed VPS checker over SSH")
    parser.add_argument("--status", action="store_true", help="Read the last check; no network calls to Gmail")
    parser.add_argument("--notify", action="store_true", help="Email the owner only for an incident/recovery")
    parser.add_argument("--test-email", action="store_true", help="Send one setup test to the fixed owner address")
    args = parser.parse_args()
    if args.status and (args.notify or args.test_email):
        parser.error("--status cannot send notifications")
    if args.remote:
        flags = [flag for flag in ("--status", "--notify", "--test-email") if getattr(args, flag[2:].replace("-", "_"))]
        try:
            result = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "cedrf",
                 "python3 " + shlex.quote(REMOTE_PATH) + " " + " ".join(flags)],
                capture_output=True, text=True, timeout=100)
            # Forward only parsed status, never SSH or third-party exception output.
            data = json.loads(result.stdout)
            print(json.dumps(data))
            return result.returncode
        except (OSError, ValueError, subprocess.SubprocessError):
            print(json.dumps({"error": "VPS check unavailable; no secrets displayed"}))
            return 3
    try:
        if args.status:
            result = public_status(read_state(), time.time())
            print(json.dumps(result))
            return 2 if (result["stale"] or result["pending_notification"]
                         or any(v != "ok" for v in result["checks"].values())) else 0
        return run_check(args.notify, args.test_email)
    except Exception:
        print(json.dumps({"error": "Email health check failed; no secrets displayed"}))
        return 3


if __name__ == "__main__":
    sys.exit(main())
