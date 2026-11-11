#!/usr/bin/env python3
"""Rotate the Legal Hash Checksum feedback password without logging it or sending mail."""

import getpass
import re
import shlex
import subprocess
import sys
import warnings


REMOTE = r'''
from pathlib import Path
import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

service = "hashverify.service"
env_file = Path.home() / "hashverify" / ".env"

def inherited():
    pid = subprocess.check_output(
        ["/bin/systemctl", "show", service, "--property=MainPID", "--value"],
        text=True,
    ).strip()
    data = Path(f"/proc/{pid}/environ").read_bytes()
    return dict(part.split(b"=", 1) for part in data.split(b"\0") if b"=" in part)

def setting(source, name):
    pattern = rf"(?m)^[ \t]*{name}[ \t]*=[ \t]*([^\r\n]*)"
    matches = list(re.finditer(pattern, source))
    if len(matches) != 1:
        raise RuntimeError("Expected one definition for the feedback setting.")
    return matches[0]

def install(contents):
    fd, name = tempfile.mkstemp(prefix=".feedback-env-", dir=env_file.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as tmp:
            tmp.write(contents)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(name, env_file)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def restart():
    subprocess.run(["sudo", "-n", "/bin/systemctl", "restart", service],
                   check=True, timeout=25)

def ready(password):
    for _ in range(24):
        try:
            with urlopen("http://127.0.0.1:8506/health", timeout=1) as response:
                if json.load(response).get("status") == "ok" and inherited().get(b"GMAIL_PASS") == password:
                    return True
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        time.sleep(0.5)
    return False

new_password = sys.stdin.read().strip()
if not re.fullmatch(r"[A-Za-z0-9]{16}", new_password):
    sys.exit("Enter a 16-character Google app password. No settings changed.")
try:
    info = env_file.lstat()
    if env_file.is_symlink() or not env_file.is_file() or info.st_uid != os.getuid():
        sys.exit("The service configuration file has changed. No settings changed.")
    with env_file.open(encoding="utf-8", newline="") as f:
        original = f.read()
    current = inherited()
    secret = setting(original, "GMAIL_PASS")
    old_password = secret[1].strip().strip(chr(34) + chr(39)).encode()
    sender = setting(original, "GMAIL_USER")[1].strip().strip(chr(34) + chr(39))
    if current.get(b"GMAIL_PASS") != old_password or current.get(b"GMAIL_USER") != sender.encode():
        sys.exit("The running Gmail settings differ from the .env file. No settings changed.")
    if new_password.encode() == old_password:
        sys.exit("Enter a newly created app password. No settings changed.")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10,
                              context=ssl.create_default_context()) as server:
            server.ehlo()
            if "PLAIN" not in server.esmtp_features.get("auth", "").upper().split():
                sys.exit("Gmail did not offer the expected sign-in method. No settings changed.")
            server.user, server.password = sender, new_password
            server.auth("PLAIN", server.auth_plain)
    except (OSError, smtplib.SMTPException) as exc:
        code = getattr(exc, "smtp_code", None)
        sys.exit(f"Gmail did not accept the sign-in ({code or type(exc).__name__}). No settings changed.")

    if env_file.read_bytes() != original.encode():
        sys.exit("The service configuration changed during the check. No settings changed.")
    changed = original[:secret.start(1)] + new_password + original[secret.end(1):]
    install(changed)
    try:
        restart()
        if not ready(new_password.encode()):
            raise RuntimeError("Health check failed.")
    except (OSError, RuntimeError, subprocess.SubprocessError):
        if env_file.read_bytes() != changed.encode():
            sys.exit("The service configuration changed during recovery. Check the service before retrying.")
        install(original)
        restart()
        sys.exit("The app did not start with the new password. The previous settings were restored.")
    print("Gmail accepted the new password. The VPS service is healthy. No email was sent.")
except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
    sys.exit("Could not complete the update. Check the service status before retrying.")
'''


def main():
    if not sys.stdin.isatty():
        sys.exit("Run this script in an interactive Terminal window.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = "".join(getpass.getpass("Paste the new Google app password (hidden): ").split())
    if not re.fullmatch(r"[A-Za-z0-9]{16}", password):
        sys.exit("Enter the 16-character Google app password. No settings changed.")
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "cedrf",
         "python3 -c " + shlex.quote(REMOTE)],
        input=password + "\n", text=True,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
