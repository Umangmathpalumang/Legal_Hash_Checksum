#!/usr/bin/env python3
"""Repair known campaign code defects only. Never import or run a campaign."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


SEND = "https://www.googleapis.com/auth/gmail.send"
READ = "https://www.googleapis.com/auth/gmail.readonly"
FILES = ("allahabad_emailer.py", "calcutta_emailer.py", "lhc_emailer.py")
RECIPIENT_HELPER = '''def _valid_recipient(value):
  # Validate one existing addr-spec; never guess or rewrite a contact address.
  from email.errors import HeaderParseError
  from email.headerregistry import Address
  if not isinstance(value, str) or "\\r" in value or "\\n" in value:
    return False
  try:
    address = Address(addr_spec=value)
    return bool(address.username and address.domain and "." in address.domain)
  except (ValueError, TypeError, IndexError, HeaderParseError):
    return False


'''


def replace_node(source, node, replacement):
    lines = source.encode().splitlines(keepends=True)
    start = sum(map(len, lines[:node.lineno - 1])) + node.col_offset
    end = sum(map(len, lines[:node.end_lineno - 1])) + node.end_col_offset
    raw = source.encode()
    return (raw[:start] + replacement.encode() + raw[end:]).decode()


def patch_scopes(source):
    tree = ast.parse(source)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "get_gmail_service"]
    if len(functions) != 1:
        raise ValueError("Unexpected Gmail connection function; review before patching")
    assignments = []
    for node in ast.walk(functions[0]):
        targets = node.targets if isinstance(node, ast.Assign) else []
        if any(isinstance(t, ast.Name) and t.id == "SCOPES" for t in targets):
            assignments.append(node)
    if not assignments:
        # Calcutta has an already-correct module-level SCOPES constant.
        assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "SCOPES" for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError("Unexpected scope definition; review before patching")
    node = assignments[0]
    current = ast.literal_eval(node.value)
    if current == [SEND]:
        return source
    if current != [SEND, READ]:
        raise ValueError("Unrecognized Gmail permissions; no expansion allowed")
    result = replace_node(source, node.value, repr([SEND]))
    compile(result, "<patched campaign>", "exec")
    return result


def patch_recipients(source):
    tree = ast.parse(source)
    if any(isinstance(n, ast.FunctionDef) and n.name == "_valid_recipient" for n in tree.body):
        if "if not _valid_recipient(email):" not in source or "if not _valid_recipient(to_email):" not in source:
            raise ValueError("Incomplete recipient guard; review before patching")
        return source
    header = "def create_message(sender_email, to_email, subject, body_text):\n"
    guard = '    if not email or "@" not in email:\n      continue'
    if source.count(header) != 1 or source.count(guard) != 1:
        raise ValueError("Unexpected Calcutta recipient code; review before patching")
    source = source.replace(header, RECIPIENT_HELPER + header
                            + '  if not _valid_recipient(to_email):\n'
                            + '    raise ValueError("Recipient must be one valid email address")\n', 1)
    source = source.replace(guard,
                            '    if not _valid_recipient(email):\n'
                            + '      if email:\n'
                            + '        logging.warning("Skipping invalid recipient in workbook row %d; contact unchanged", row)\n'
                            + '      continue', 1)
    compile(source, "<patched Calcutta campaign>", "exec")
    return source


def protected_hashes(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()
            if p.is_file() and (p.suffix in (".json", ".xlsx") or p.name == "blacklist.txt")}


def repair(root, apply=False):
    original = {name: (root / name).read_text() for name in FILES}
    updated = {name: patch_scopes(value) for name, value in original.items()}
    updated["calcutta_emailer.py"] = patch_recipients(updated["calcutta_emailer.py"])
    changed = [name for name in FILES if updated[name] != original[name]]
    result = {"changed_code_files": changed, "applied": False}
    if apply and changed:
        before = protected_hashes(root)
        backup = root / ".runtime-repair-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup.mkdir(parents=True, mode=0o700)
        for name in changed:
            source = root / name
            if source.is_symlink() or source.read_text() != original[name]:
                raise ValueError("Campaign code changed during review; retry the check")
            shutil.copy2(source, backup / name)
            os.chmod(backup / name, 0o600)
        for name in changed:
            fd, staged = tempfile.mkstemp(prefix=".campaign-fix-", dir=str(root))
            try:
                with os.fdopen(fd, "w") as stream:
                    stream.write(updated[name])
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(staged, (root / name).stat().st_mode & 0o777)
                if (root / name).read_text() != original[name]:
                    raise ValueError("Campaign code changed before install")
                os.replace(staged, root / name)
            finally:
                if os.path.exists(staged):
                    os.unlink(staged)
        result.update(applied=True, backup_directory=str(backup),
                      contacts_history_credentials_unchanged=before == protected_hashes(root))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Install code fixes with private rollback copies")
    args = parser.parse_args()
    if args.remote:
        command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "cedrf", "python3 -"]
        if args.apply:
            command[-1] += " --apply"
        try:
            result = subprocess.run(command, input=Path(__file__).read_text(), text=True,
                                    capture_output=True, timeout=35)
            print(json.dumps(json.loads(result.stdout)))
            return result.returncode
        except (OSError, ValueError, subprocess.SubprocessError):
            print(json.dumps({"error": "VPS repair unavailable; no secrets displayed"}))
            return 3
    try:
        print(json.dumps(repair(Path.home() / "lhc", args.apply)))
        return 0
    except Exception:
        print(json.dumps({"error": "Campaign code differs from the reviewed version; inspect before retrying"}))
        return 3


if __name__ == "__main__":
    sys.exit(main())
