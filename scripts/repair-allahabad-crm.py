#!/usr/bin/env python3
"""Recover the Allahabad CRM and repair its code, without sending a batch."""
import argparse
import ast
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import zipfile


VALIDATOR = r'''def _valid_recipient(value):
    from email.errors import HeaderParseError
    from email.headerregistry import Address
    if not isinstance(value, str) or "\r" in value or "\n" in value:
        return False
    try:
        address = Address(addr_spec=value)
        return bool(address.username and address.domain and "." in address.domain)
    except (ValueError, TypeError, IndexError, HeaderParseError):
        return False


'''

ATOMIC_SAVE = '''def _save_crm_atomic(workbook, filename, expected_stat):
    import os
    import tempfile
    import zipfile
    from pathlib import Path
    path = Path(filename)
    fd, staged = tempfile.mkstemp(prefix=".allahabad-crm-", suffix=".xlsx", dir=str(path.parent))
    os.close(fd)
    try:
        workbook.save(staged)
        with zipfile.ZipFile(staged) as archive:
            if archive.testzip() is not None or "xl/workbook.xml" not in archive.namelist():
                raise RuntimeError("CRM output did not validate")
        current = path.stat()
        if (current.st_ino, current.st_size, current.st_mtime_ns) != expected_stat:
            raise RuntimeError("CRM changed while preparing its update")
        with open(staged, "rb") as stream:
            os.fsync(stream.fileno())
        os.replace(staged, path)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)


'''

SELECTION = '''def get_unsent(state):
    bl = load_blacklist()
    candidates = [c for c in CONTACTS if c["email"] not in state and c["email"].lower() not in bl]
    valid = [c for c in candidates if _valid_recipient(c["email"])]
    if len(valid) != len(candidates):
        log.warning("Skipping %d malformed unsent recipients; contact records unchanged", len(candidates) - len(valid))
    return valid'''


def replace_function(source, name, replacement):
    tree = ast.parse(source)
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(matches) != 1:
        raise ValueError("Unexpected campaign function")
    node = matches[0]
    lines = source.splitlines(keepends=True)
    return "".join(lines[:node.lineno - 1]) + replacement + "\n" + "".join(lines[node.end_lineno:])


def patch_crm_fields(source):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "update_excel_crm")
    body = ast.get_source_segment(source, node)
    if "recorded_ist" in body:
        return source
    marker = "                # Add sent date in col F onwards if available\n                break"
    if marker not in body:
        # Synthetic/no-row writers have no status fields to synchronize.
        if "iter_rows" not in body:
            return source
        raise ValueError("Unrecognized CRM row update")
    body = body.replace("        sent_date = sent_at_dt.date()", '''        from datetime import datetime as _dt, timezone, timedelta
        record = load_state().get(contact["email"], {})
        recorded_ist = _dt.fromisoformat(record["sent_at"].replace("Z", "+00:00"))
        if recorded_ist.tzinfo is None:
            recorded_ist = recorded_ist.replace(tzinfo=timezone.utc)
        recorded_ist = recorded_ist.astimezone(timezone(timedelta(hours=5, minutes=30))).replace(tzinfo=None)
        sent_date = recorded_ist.date()''', 1)
    body = body.replace(marker, '''                ws.cell(row=row[0].row, column=7).value = STATUS.get(email_num, "Sent")
                ws.cell(row=row[0].row, column=8).value = recorded_ist
                ws.cell(row=row[0].row, column=8).number_format = "dd-mmm-yyyy hh:mm"
                ws.cell(row=row[0].row, column=9).value = record.get("msg_id")
                break''', 1)
    body = body.replace('sent_at_dt.strftime("%I:%M %p")', 'recorded_ist.strftime("%I:%M %p")', 1)
    body = body.replace('template_used, "Python Script"', 'template_used, "Python Script", record.get("msg_id")', 1)
    return replace_function(source, "update_excel_crm", body)


def patch_code(source):
    tree = ast.parse(source)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if "_save_crm_atomic" in functions:
        if "_valid_recipient" not in functions or "_valid_recipient(c[\"email\"])" not in source:
            raise ValueError("Incomplete prior repair")
        return patch_crm_fields(source)
    current = ast.get_source_segment(source, functions["get_unsent"])
    expected = 'def get_unsent(state):\n    bl = load_blacklist()\n    return [c for c in CONTACTS if c["email"] not in state and c["email"].lower() not in bl]'
    if current != expected or "_valid_recipient" in functions:
        raise ValueError("Recipient code differs from reviewed layout")
    source = replace_function(source, "get_unsent", VALIDATOR + SELECTION)
    marker = "def send_email(service, to_email, subject, body):\n"
    if source.count(marker) != 1:
        raise ValueError("Unexpected send function")
    source = source.replace(marker, marker + '    if not _valid_recipient(to_email):\n        raise ValueError("Recipient must be one valid email address")\n', 1)
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "update_excel_crm")
    crm = ast.get_source_segment(source, node)
    if crm.count('        wb = openpyxl.load_workbook(EXCEL_FILE)') != 1 or crm.count('        wb.save(EXCEL_FILE)') != 1:
        raise ValueError("Unexpected CRM writer")
    crm = crm.replace('        wb = openpyxl.load_workbook(EXCEL_FILE)',
                      '        stat = Path(EXCEL_FILE).stat()\n'
                      '        expected_stat = (stat.st_ino, stat.st_size, stat.st_mtime_ns)\n'
                      '        wb = openpyxl.load_workbook(EXCEL_FILE)', 1)
    crm = crm.replace('        wb.save(EXCEL_FILE)', '        _save_crm_atomic(wb, EXCEL_FILE, expected_stat)', 1)
    source = replace_function(source, "update_excel_crm", ATOMIC_SAVE + crm)
    compile(source, "<reviewed Allahabad campaign>", "exec")
    return patch_crm_fields(source)


def source_contacts(source):
    matches = [n for n in ast.parse(source).body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "CONTACTS" for t in n.targets)]
    if len(matches) != 1:
        raise ValueError("Expected the existing literal contact dataset")
    contacts = ast.literal_eval(matches[0].value)
    if not isinstance(contacts, list) or any(not isinstance(c, dict) or not isinstance(c.get("email"), str) for c in contacts):
        raise ValueError("Unexpected contact schema")
    return contacts


def utc_to_ist(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone(timedelta(hours=5, minutes=30))).replace(tzinfo=None)


def build_workbook(path, contacts, history, blacklist):
    # Runs on the VPS, where Node/artifact-tool is unavailable. Reuse the
    # deployed app's existing openpyxl dependency and keep contacts on the VPS.
    import openpyxl
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Alignment, Font, PatternFill
    ns = {}
    exec(compile(VALIDATOR, "validator", "exec"), ns)
    valid = ns["_valid_recipient"]
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("Allahabad HC Advocates")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "D3"
    for col, width in {"A": 8, "B": 18, "C": 34, "D": 42, "E": 55, "F": 45, "G": 22, "H": 24, "I": 30}.items():
        ws.column_dimensions[col].width = width
    font = Font(name="Arial", size=10)
    heading = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="1E40AF")

    def append(sheet, values, header=False):
        cells = []
        for value in values:
            cell = WriteOnlyCell(sheet, value=value)
            if isinstance(value, str):
                cell.data_type = "s"  # Preserve source text, never interpret it as a formula.
            cell.font = heading if header else font
            cell.alignment = Alignment(vertical="center", wrap_text=False)
            if header:
                cell.fill = fill
            if isinstance(value, datetime):
                cell.number_format = "dd-mmm-yyyy hh:mm"
            cells.append(cell)
        sheet.append(cells)

    append(ws, ["Allahabad HC Advocates"])
    append(ws, ["S.No.", "Roll No.", "Name", "Email", "Address", "Remarks", "Status", "Last sent (IST)", "Gmail message ID"], True)
    for c in contacts:
        sent = history.get(c["email"])
        status = ("Sent" if sent else "Blacklisted" if c["email"].lower() in blacklist
                  else "Invalid address" if not valid(c["email"]) else "Unsent")
        append(ws, [c.get(k) for k in ("sl", "roll", "name", "email", "address", "remarks")]
               + [status, utc_to_ist(sent["sent_at"]) if sent else None, sent.get("msg_id") if sent else None])
    ws.auto_filter.ref = "A2:I{}".format(len(contacts) + 2)
    log = wb.create_sheet("Send Log")
    log.sheet_view.showGridLines = False
    log.freeze_panes = "A2"
    for col, width in {"A": 16, "B": 16, "C": 34, "D": 42, "E": 12, "F": 20, "G": 24, "H": 30}.items():
        log.column_dimensions[col].width = width
    append(log, ["Date", "Time", "Name", "Email", "Email#", "Template", "Via", "Gmail message ID"], True)
    for email, record in sorted(history.items(), key=lambda item: item[1]["sent_at"]):
        sent = utc_to_ist(record["sent_at"])
        # Historical state has no template or sequence field. Keep those blank.
        append(log, [sent.date(), sent.strftime("%I:%M %p"), record.get("name"), email,
                     None, None, "Recovered send history", record.get("msg_id")])
    wb.save(str(path))


def verify_workbook(path, contacts, history):
    import openpyxl
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Workbook ZIP validation failed")
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=False)
    try:
        ws = wb["Allahabad HC Advocates"]
        rows = ws.iter_rows(min_row=3, values_only=True)
        count = 0
        for expected, actual in zip(contacts, rows):
            if list(actual[:6]) != [None if expected.get(k) == "" else expected.get(k)
                                    for k in ("sl", "roll", "name", "email", "address", "remarks")]:
                raise ValueError("Recovered contact differs from source")
            count += 1
        if count != len(contacts) or next(rows, None) is not None:
            raise ValueError("Recovered contact row count differs")
        recovered = Counter((r[3], r[7]) for r in wb["Send Log"].iter_rows(min_row=2, values_only=True))
        expected = Counter((email, v.get("msg_id")) for email, v in history.items())
        if recovered != expected:
            raise ValueError("Recovered history differs from source")
        return {"contact_rows": count, "send_log_rows": sum(recovered.values()), "zip_verified": True}
    finally:
        wb.close()


def reconcile_workbook(original, staged, history):
    """Update only recorded CRM fields; preserve existing contact cells and styles."""
    import openpyxl
    wb = openpyxl.load_workbook(str(original))
    try:
        ws = wb["Allahabad HC Advocates"]
        for row in ws.iter_rows(min_row=3):
            record = history.get(row[3].value)
            if record:
                ws.cell(row=row[0].row, column=7).value = "Sent"
                stamp = ws.cell(row=row[0].row, column=8)
                stamp.value = utc_to_ist(record["sent_at"])
                stamp.number_format = "dd-mmm-yyyy hh:mm"
                ws.cell(row=row[0].row, column=9).value = record.get("msg_id")
        log = wb["Send Log"]
        for row in log.iter_rows(min_row=2):
            record = history.get(row[3].value)
            if record and not log.cell(row=row[0].row, column=8).value:
                log.cell(row=row[0].row, column=8).value = record.get("msg_id")
        wb.save(str(staged))
    finally:
        wb.close()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def campaign_running():
    result = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True, check=True)
    for line in result.stdout.splitlines():
        try:
            args = shlex.split(line)
        except ValueError:
            continue
        if args and Path(args[0]).name.startswith("python") and any(Path(v).name == "allahabad_emailer.py" for v in args[1:]):
            return True
    return False


def repair(root, apply=False):
    code_path = root / "allahabad_emailer.py"
    book_path = root / "Allahabad_HC_Advocates.xlsx"
    state_path = root / "allahabad_sent_state.json"
    source = code_path.read_text()
    updated = patch_code(source)
    contacts = source_contacts(source)
    history = json.loads(state_path.read_text())
    blacklist = {v.strip().lower() for v in (root / "blacklist.txt").read_text().splitlines() if v.strip() and not v.startswith("#")}
    ns = {}
    exec(compile(VALIDATOR, "validator", "exec"), ns)
    invalid_unsent = sum(c["email"] not in history and c["email"].lower() not in blacklist
                         and not ns["_valid_recipient"](c["email"]) for c in contacts)
    rebuild = not zipfile.is_zipfile(book_path)
    result = {"code_change_needed": updated != source, "crm_rebuild_needed": rebuild,
              "source_contacts": len(contacts), "sent_history_records": len(history),
              "malformed_unsent_contacts": invalid_unsent, "applied": False}
    if not apply or not (rebuild or updated != source):
        return result
    if campaign_running():
        raise ValueError("A scheduled batch is active; retry the repair after it finishes")
    protected = [p for p in root.glob("*.json") if p.is_file()] + [root / "blacklist.txt"]
    before = {p.name: digest(p) for p in protected}
    book_before = digest(book_path)
    staged = None
    try:
        if rebuild or updated != source:
            fd, staged = tempfile.mkstemp(prefix=".recovered-crm-", suffix=".xlsx", dir=str(root))
            os.close(fd)
            if rebuild:
                build_workbook(Path(staged), contacts, history, blacklist)
            else:
                reconcile_workbook(book_path, Path(staged), history)
            result["workbook_verification"] = verify_workbook(Path(staged), contacts, history)
        if campaign_running() or code_path.read_text() != source or digest(book_path) != book_before or before != {p.name: digest(p) for p in protected}:
            raise ValueError("Campaign data changed during preparation; retry later")
        backup = root / ".crm-repair-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup.mkdir(parents=True, mode=0o700)
        for p in (code_path, book_path):
            shutil.copy2(p, backup / p.name)
            os.chmod(backup / p.name, 0o600)
        if staged:
            os.replace(staged, book_path)
            staged = None
        if updated != source:
            fd, code_stage = tempfile.mkstemp(prefix=".allahabad-code-", dir=str(root))
            try:
                with os.fdopen(fd, "w") as stream:
                    stream.write(updated)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(code_stage, code_path.stat().st_mode & 0o777)
                os.replace(code_stage, code_path)
            finally:
                if os.path.exists(code_stage):
                    os.unlink(code_stage)
        result.update(applied=True, backup_directory=str(backup),
                      history_credentials_blacklist_unchanged=before == {p.name: digest(p) for p in protected})
        return result
    finally:
        if staged and os.path.exists(staged):
            os.unlink(staged)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.remote:
            command = " /home/ubuntu/lhc/venv/bin/python -" + (" --apply" if args.apply else "")
            result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "cedrf", command],
                                    input=Path(__file__).read_text(), capture_output=True, text=True, timeout=300)
            print(json.dumps(json.loads(result.stdout)))
            return result.returncode
        print(json.dumps(repair(Path.home() / "lhc", args.apply)))
        return 0
    except Exception as exc:
        print(json.dumps({"error": "CRM repair did not complete; credential/contact details suppressed", "type": type(exc).__name__}))
        return 3


if __name__ == "__main__":
    sys.exit(main())
