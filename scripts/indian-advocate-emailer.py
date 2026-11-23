#!/usr/bin/env python3
"""One-time advocate introductions from the reviewed directory workbook.

Import, preview, status and dry-run never open a Gmail connection. Runtime data
stays outside Git. Delivery acceptance is recorded before another recipient is
attempted; uncertain outcomes are held for manual review, never auto-replayed.
"""
import argparse
import base64
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import datetime, timedelta, timezone
from email.headerregistry import Address
from email.errors import HeaderParseError
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid

IST = timezone(timedelta(hours=5, minutes=30))
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
OWNER = "umangmathpal@gmail.com"
REVIEW_CLEAR = "Source and delivery review required"
HEADERS = ("Email", "Advocate name (if explicit)", "AOR code (if explicit)",
           "Directory group", "Court / jurisdiction", "Source IDs",
           "PDF page references", "Review notes")
FIELDS = ("email", "name", "aor_code", "directory_group", "courts",
          "source_ids", "page_refs", "review_notes")
LEGACY_BOOKS = (("Allahabad_HC_Advocates.xlsx", "Allahabad HC Advocates", 4),
                ("Calcutta_HC_Advocates.xlsx", "Calcutta HC Advocates", 5),
                ("LHC_Advocate_CRM.xlsx", "Advocates Master List", 4))
DEFAULT_CONFIG = {"enabled": False, "batch_size": 12, "delay_seconds": 15,
                  "daily_limit": 108, "hourly_limit": 12,
                  "sender": OWNER, "schedule": "10 9-17 * * 1-5",
                  "subject": "Free legal tools for Indian advocates - feedback welcome"}
_LEGACY_CACHE = {}
SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
 email TEXT PRIMARY KEY, name TEXT NOT NULL, aor_code TEXT NOT NULL,
 directory_group TEXT NOT NULL, courts TEXT NOT NULL, source_ids TEXT NOT NULL,
 page_refs TEXT NOT NULL, review_notes TEXT NOT NULL, source_row INTEGER NOT NULL,
 eligibility TEXT NOT NULL, hold_reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attempts (
 id INTEGER PRIMARY KEY, email TEXT NOT NULL REFERENCES contacts(email),
 state TEXT NOT NULL, attempted_at TEXT NOT NULL, accepted_at TEXT,
 message_id TEXT, rfc_message_id TEXT NOT NULL, error_code TEXT);
CREATE INDEX IF NOT EXISTS attempts_email ON attempts(email,id);
CREATE TABLE IF NOT EXISTS blacklist (email TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
 selected INTEGER NOT NULL, sent INTEGER NOT NULL, errors TEXT NOT NULL);
"""


class Blocked(Exception):
    """Contains a short, redacted error code only."""


def stamp(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def valid_email(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][^\s\r\n@]*@[^\s\r\n@]+", value):
        return False
    try:
        address = Address(addr_spec=value)
        local, domain = value.rsplit("@", 1)
        return (address.addr_spec.lower() == value.lower() and len(value) <= 254
                and len(local) <= 64 and re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", domain) is not None
                and re.fullmatch(r"[A-Za-z]{2,24}", domain.rsplit(".", 1)[1]) is not None
                and all(not part.startswith("-") and not part.endswith("-") for part in domain.split(".")))
    except (ValueError, TypeError, IndexError, HeaderParseError):
        return False


def atomic_json(path, data):
    fd, staged = tempfile.mkstemp(prefix=".state-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staged, 0o600)
        os.replace(staged, str(path))
    finally:
        if os.path.exists(staged):
            os.unlink(staged)


@contextmanager
def campaign_lock(root):
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(str(root), 0o700)
    with (root / "campaign.lock").open("a") as lock:
        os.chmod(str(root / "campaign.lock"), 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Blocked("campaign_already_running")
        yield


def connect(root):
    path = root / "campaign.sqlite3"
    if path.is_symlink():
        raise Blocked("unsafe_database_path")
    db = sqlite3.connect(str(path), timeout=10)
    os.chmod(str(path), 0o600)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript(SCHEMA)
    return db


def config(root):
    path = root / "config.json"
    if path.is_symlink():
        raise Blocked("unsafe_config_path")
    if not path.exists():
        atomic_json(path, DEFAULT_CONFIG)
    value = json.loads(path.read_text())
    if (not isinstance(value.get("enabled"), bool) or value.get("sender") != OWNER
            or value.get("schedule") != DEFAULT_CONFIG["schedule"]
            or any(not isinstance(value.get(k), int) or isinstance(value.get(k), bool)
                   or not low <= value[k] <= high for k, low, high in
                   (("batch_size", 1, 12), ("delay_seconds", 15, 300),
                    ("daily_limit", 1, 108), ("hourly_limit", 1, 12)))
            or value.get("subject") != DEFAULT_CONFIG["subject"]):
        raise Blocked("invalid_campaign_config")
    return value


def import_workbook(db, workbook):
    import openpyxl
    before = hashlib.sha256(workbook.read_bytes()).hexdigest()
    wb = openpyxl.load_workbook(str(workbook), read_only=True, data_only=False)
    try:
        if "Sources" not in wb.sheetnames or "Emails for review" not in wb.sheetnames:
            raise Blocked("wrong_workbook_sheets")
        source_ids = {row[0] for row in wb["Sources"].iter_rows(min_row=9, max_col=1, values_only=True) if row[0]}
        ws = wb["Emails for review"]
        if tuple(c.value for c in next(ws.iter_rows(min_row=8, max_row=8, max_col=8))) != HEADERS:
            raise Blocked("wrong_workbook_headers")
        records = {}
        for row in ws.iter_rows(min_row=9, max_col=8):
            if not any(c.value is not None for c in row):
                continue
            if any(c.data_type == "f" for c in row):
                raise Blocked("formula_in_contact_row")
            values = ["" if c.value is None else str(c.value) for c in row]
            record = dict(zip(FIELDS, values))
            email = record["email"].strip().lower()
            record["email"] = email
            reason = ("invalid_recipient" if not valid_email(email) else
                      "source_review_required" if record["review_notes"] != REVIEW_CLEAR else
                      "unrecognized_source" if not record["source_ids"] or not set(record["source_ids"].split("; ")) <= source_ids else "")
            if email in records:
                # Conflicting duplicate evidence can only tighten eligibility.
                previous = records[email]
                if reason:
                    previous["hold_reason"] = reason
                    previous["eligibility"] = "held"
                continue
            record.update(source_row=row[0].row, eligibility="held" if reason else "ready", hold_reason=reason)
            records[email] = record
    finally:
        wb.close()
    if before != hashlib.sha256(workbook.read_bytes()).hexdigest():
        raise Blocked("workbook_changed_during_import")
    if not records:
        raise Blocked("empty_workbook")
    columns = FIELDS + ("source_row", "eligibility", "hold_reason")
    with db:
        db.execute("UPDATE contacts SET eligibility='held',hold_reason='missing_from_latest_import'")
        sql = ("INSERT INTO contacts ({}) VALUES ({}) ON CONFLICT(email) DO UPDATE SET {}".format(
            ",".join(columns), ",".join("?" for _ in columns),
            ",".join("{0}=excluded.{0}".format(k) for k in columns if k != "email")))
        db.executemany(sql, [tuple(r[k] for k in columns) for r in records.values()])
        db.execute("INSERT OR REPLACE INTO metadata VALUES ('workbook_sha256',?)", (before,))
        db.execute("INSERT OR REPLACE INTO metadata VALUES ('imported_at',?)", (stamp(),))
    return {"imported": len(records), "source_flags_held": sum(r["eligibility"] == "held" for r in records.values()),
            "ready_before_legacy_exclusions": sum(r["eligibility"] == "ready" for r in records.values())}


def legacy_snapshot(root):
    """Reserve ALL legacy contacts, including unsent ones, to avoid cross-job races."""
    import openpyxl
    paths = [root / item[0] for item in LEGACY_BOOKS] + [root / name for name in
             ("allahabad_sent_state.json", "sent_state.json", "blacklist.txt")]
    try:
        fingerprint = tuple((str(p),p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in paths)
    except OSError:
        raise Blocked("legacy_exclusion_file_unavailable")
    if _LEGACY_CACHE.get("fingerprint") == fingerprint:
        return _LEGACY_CACHE["reserved"], _LEGACY_CACHE["blocked"]
    reserved, blocked = set(), set()
    for filename, sheet, column in LEGACY_BOOKS:
        path = root / filename
        if not path.is_file():
            raise Blocked("legacy_workbook_unavailable")
        try:
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=False)
            try:
                ws = wb[sheet]
                header = ws.cell(2, column).value
                if re.sub(r"[^a-z]", "", str(header).lower()) not in {"email", "emailaddress"}:
                    raise Blocked("legacy_workbook_schema_changed")
                for (cell,) in ws.iter_rows(min_row=3, min_col=column, max_col=column):
                    if cell.data_type == "f":
                        raise Blocked("legacy_email_formula")
                    if isinstance(cell.value, str):
                        reserved.add(cell.value.strip().lower())
            finally:
                wb.close()
        except Blocked:
            raise
        except Exception:
            raise Blocked("legacy_workbook_unreadable")
    for filename in ("allahabad_sent_state.json", "sent_state.json"):
        try:
            history = json.loads((root / filename).read_text())
            if not isinstance(history, dict):
                raise ValueError()
            reserved.update(key.strip().lower() for key in history)
        except Exception:
            raise Blocked("legacy_history_unreadable")
    path = root / "blacklist.txt"
    if not path.is_file():
        raise Blocked("shared_blacklist_unavailable")
    for line in path.read_text().splitlines():
        value = line.split("#", 1)[0].strip().lower()
        if value:
            blocked.add(value)
    try:
        after = tuple((str(p),p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in paths)
    except OSError:
        raise Blocked("legacy_exclusions_changed_during_read")
    if after != fingerprint:
        raise Blocked("legacy_exclusions_changed_during_read")
    reserved, blocked = frozenset(reserved), frozenset(blocked)
    _LEGACY_CACHE.update(fingerprint=fingerprint, reserved=reserved, blocked=blocked)
    return reserved, blocked


def queue(db, legacy_root):
    reserved, blocked = legacy_snapshot(legacy_root)
    blocked = set(blocked)
    blocked.update(r[0] for r in db.execute("SELECT email FROM blacklist"))
    result, counts = [], Counter()
    for row in db.execute("""SELECT c.*,a.state AS delivery_state FROM contacts c LEFT JOIN attempts a
      ON a.id=(SELECT MAX(id) FROM attempts WHERE email=c.email) ORDER BY c.source_row,c.email"""):
        if row["email"] in blocked:
            counts["blacklisted"] += 1
        elif row["email"] in reserved:
            counts["reserved_for_existing_campaigns"] += 1
        elif row["eligibility"] != "ready":
            counts["held_for_source_review"] += 1
        elif row["delivery_state"] in {"accepted", "attempting", "uncertain", "rejected"}:
            counts["already_accepted_or_held_attempt"] += 1
        else:
            result.append(dict(row))
    counts["eligible_unsent"] = len(result)
    counts["total_contacts"] = db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    return result, dict(counts)


def body_text(contact):
    name = " ".join(contact.get("name", "").split())[:160]
    salutation = "Dear {},".format(name) if name else "Dear Advocate,"
    return (salutation + "\n\nI'm Umang Mathpal, creator of Legal Hash Checksum, a product of Hoursdev. "
            "I built a collection of legal utilities for Indian advocates, including evidence file hashing, "
            "certificate forms, document generators and calculators.\n\n"
            "You can explore the tools here:\nhttps://legalhashchecksum.com/tools\n\n"
            "I'd welcome your feedback on which tools are useful in your practice and what could work better. "
            "There is no obligation to sign up or purchase anything.\n\n"
            "Regards,\nUmang Mathpal\nHoursdev / Legal Hash Checksum\n"
            "https://www.hoursdev.com/\n\n"
            "This is a one-time introduction using a professional address published in a court or legal-services directory. "
            "To opt out, reply with Unsubscribe. I will add your address to the campaign's exclusion list.\n")


def message(contact, cfg, message_id, now):
    if not valid_email(contact["email"]):
        raise Blocked("invalid_recipient")
    msg = EmailMessage()
    msg["From"] = formataddr(("Umang Mathpal - Legal Hash Checksum", cfg["sender"]))
    msg["To"] = contact["email"]
    msg["Reply-To"] = OWNER
    msg["Subject"] = cfg["subject"]
    msg["Message-ID"] = message_id
    msg["Date"] = format_datetime(now.astimezone(IST))
    msg["List-Unsubscribe"] = "<mailto:{}?subject=Unsubscribe%20Indian%20Advocates>".format(OWNER)
    msg.set_content(body_text(contact))
    return msg


def gmail_service(legacy_root):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from google_auth_httplib2 import AuthorizedHttp
    import httplib2
    path = legacy_root / "token.json"
    if path.is_symlink():
        raise Blocked("unsafe_token_path")
    token = json.loads(path.read_text())
    if set(token.get("scopes", [])) != {SEND_SCOPE} or token.get("token_uri") != "https://oauth2.googleapis.com/token":
        raise Blocked("scope_mismatch")
    try:
        creds = Credentials.from_authorized_user_file(str(path), [SEND_SCOPE])
        if not creds.valid:
            if not creds.refresh_token:
                raise Blocked("auth_failed")
            creds.refresh(Request())
        # Do not overwrite the shared token or request inbox access.
        return build("gmail", "v1", http=AuthorizedHttp(creds, http=httplib2.Http(timeout=20)), cache_discovery=False)
    except Blocked:
        raise
    except Exception:
        raise Blocked("auth_failed_or_network_error")


def api_send(service, msg):
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute(num_retries=0)
    if not isinstance(result, dict) or not result.get("id"):
        raise Blocked("delivery_outcome_unknown")
    return result["id"]


def classify_error(exc):
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status == 400:
        return "rejected", "invalid_request_or_recipient"
    if status in (401, 403, 429):
        return "deferred", "gmail_auth_or_limit_{}".format(status)
    return "uncertain", "delivery_outcome_unknown"


def working_hours(now):
    local = now.astimezone(IST)
    return local.weekday() < 5 and 9 <= local.hour < 18


def remaining_budget(db, cfg, now):
    local = now.astimezone(IST)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    daily = db.execute("SELECT COUNT(*) FROM attempts WHERE attempted_at>=?", (stamp(midnight),)).fetchone()[0]
    hour_start = local.replace(minute=0,second=0,microsecond=0)
    hourly = db.execute("SELECT COUNT(*) FROM attempts WHERE attempted_at>=?", (stamp(hour_start),)).fetchone()[0]
    cooldown = db.execute("SELECT value FROM metadata WHERE key='cooldown_until'").fetchone()
    if cooldown and cooldown[0] > stamp(now):
        return 0
    return max(0, min(cfg["batch_size"], cfg["daily_limit"]-daily, cfg["hourly_limit"]-hourly))


def save_public_status(root, db, cfg, result=None):
    latest = db.execute("SELECT * FROM runs ORDER BY started_at DESC,id DESC LIMIT 1").fetchone()
    state = {"enabled": cfg["enabled"], "status": "paused" if not cfg["enabled"] else "not_due",
             "last_run": None, "sent": 0, "errors": [], "warnings": [], "schedule_minute": 10}
    if latest and cfg["enabled"]:
        state.update(status=latest["status"], last_run=latest["started_at"], sent=latest["sent"], errors=json.loads(latest["errors"]))
    if result:
        state.update(result)
    uncertain = db.execute("SELECT COUNT(*) FROM attempts WHERE state IN ('attempting','uncertain')").fetchone()[0]
    if uncertain:
        state["warnings"] = ["delivery_outcome_requires_review"]
        state["held_uncertain_attempts"] = uncertain
    atomic_json(root / "latest_run.json", state)
    return state


def run_batch(root, db, cfg, legacy_root, send=False, now=None, sleeper=time.sleep, service_factory=gmail_service, sender=api_send):
    real_clock = now is None
    now = now or datetime.now(timezone.utc)
    if send and not cfg["enabled"]:
        return {"status": "paused", "sent": 0, "errors": []}
    if send and not working_hours(now):
        return {"status": "not_due", "sent": 0, "errors": []}
    try:
        candidates, counts = queue(db, legacy_root)
    except Blocked as exc:
        if not send:
            raise
        with db:
            db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
                       (uuid.uuid4().hex,stamp(now),stamp(),"failed",0,0,json.dumps([str(exc)])))
        return save_public_status(root,db,cfg)
    selected = candidates[:remaining_budget(db, cfg, now)]
    if not send:
        return {"status": "dry_run", "planned": len(selected), "sent": 0, "queue": counts,
                "subject": cfg["subject"], "body": body_text({})}
    run_id = uuid.uuid4().hex
    status = "in_progress"
    sent, errors = 0, []
    with db:
        db.execute("INSERT INTO runs VALUES (?,?,NULL,?,?,?,?)", (run_id, stamp(now), status, len(selected), 0, "[]"))
    save_public_status(root, db, cfg)
    try:
        if not selected:
            status = "empty_queue" if not candidates else "rate_limited"
        else:
            service = service_factory(legacy_root)
            for contact in selected:
                current = datetime.now(timezone.utc) if real_clock else now
                if not working_hours(current):
                    break
                # Re-read shared exclusions immediately before every delivery.
                reserved, blocked = legacy_snapshot(legacy_root)
                own_block = db.execute("SELECT 1 FROM blacklist WHERE email=?", (contact["email"],)).fetchone()
                if contact["email"] in reserved or contact["email"] in blocked or own_block:
                    continue
                if remaining_budget(db, cfg, current) == 0:
                    break
                mid = make_msgid(domain="legalhashchecksum.com")
                msg = message(contact, cfg, mid, current)
                with db:
                    cursor = db.execute("INSERT INTO attempts(email,state,attempted_at,rfc_message_id) VALUES (?,'attempting',?,?)",
                                        (contact["email"], stamp(current), mid))
                    attempt = cursor.lastrowid
                # A hard crash from this point leaves 'attempting' and prevents a replay.
                try:
                    gmail_id = sender(service, msg)
                except Exception as exc:
                    state, code = classify_error(exc)
                    with db:
                        db.execute("UPDATE attempts SET state=?,error_code=? WHERE id=?", (state, code, attempt))
                        if state == "deferred":
                            db.execute("INSERT OR REPLACE INTO metadata VALUES ('cooldown_until',?)",
                                       (stamp(current+timedelta(hours=1)),))
                    errors.append(code)
                    status = "partial_failure" if sent else "failed"
                    break
                with db:
                    db.execute("UPDATE attempts SET state='accepted',accepted_at=?,message_id=? WHERE id=?", (stamp(current), gmail_id, attempt))
                    sent += 1
                    db.execute("UPDATE runs SET sent=? WHERE id=?", (sent, run_id))
                save_public_status(root, db, cfg)
                if contact is not selected[-1]:
                    sleeper(cfg["delay_seconds"])
            if status == "in_progress":
                status = "completed" if sent else "rate_limited"
    except Blocked as exc:
        errors.append(str(exc))
        status = "partial_failure" if sent else "failed"
    except Exception:
        errors.append("campaign_runtime_error")
        status = "partial_failure" if sent else "failed"
    with db:
        db.execute("UPDATE runs SET finished_at=?,status=?,sent=?,errors=? WHERE id=?",
                   (stamp(), status, sent, json.dumps(errors), run_id))
    return save_public_status(root, db, cfg)


def export_csv(root, db, legacy_root):
    ready, _ = queue(db, legacy_root)
    eligible = {r["email"] for r in ready}
    fd, staged = tempfile.mkstemp(prefix=".export-", dir=str(root))
    fields = list(FIELDS) + ["eligibility", "hold_reason", "delivery_state", "accepted_at", "gmail_message_id"]
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for c in db.execute("""SELECT c.*,a.state,a.accepted_at,a.message_id FROM contacts c LEFT JOIN attempts a
               ON a.id=(SELECT MAX(id) FROM attempts WHERE email=c.email) ORDER BY c.source_row,c.email"""):
                row = {k: c[k] for k in FIELDS}
                row.update(eligibility="eligible" if c["email"] in eligible else "excluded_or_already_attempted",
                           hold_reason=c["hold_reason"], delivery_state=c["state"] or "unsent",
                           accepted_at=c["accepted_at"] or "", gmail_message_id=c["message_id"] or "")
                writer.writerow({k: "'"+v if isinstance(v,str) and v.startswith(("=","+","-","@")) else v for k,v in row.items()})
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, str(root / "send-status.csv"))
    finally:
        if os.path.exists(staged):
            os.unlink(staged)
    return {"export": str(root / "send-status.csv")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home()/"lhc"/"indian_advocates")
    parser.add_argument("--legacy-root", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    imp = commands.add_parser("import")
    imp.add_argument("--workbook", type=Path, required=True)
    commands.add_parser("preview")
    commands.add_parser("status")
    commands.add_parser("export")
    run = commands.add_parser("run")
    run.add_argument("--send", action="store_true", help="Requires an enabled config; default is a dry-run")
    run.add_argument("--cron", action="store_true", help="Label a scheduled invocation")
    conf = commands.add_parser("configure")
    mode = conf.add_mutually_exclusive_group()
    mode.add_argument("--enable", action="store_true")
    mode.add_argument("--disable", action="store_true")
    unsub = commands.add_parser("unsubscribe")
    unsub.add_argument("--email", required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    root = args.root.expanduser().resolve()
    legacy_root = (args.legacy_root or root.parent).expanduser().resolve()
    try:
        with campaign_lock(root):
            cfg = config(root)
            db = connect(root)
            try:
                if args.command == "import":
                    result = import_workbook(db, args.workbook)
                    save_public_status(root, db, cfg)
                elif args.command in {"preview", "run"}:
                    result = run_batch(root, db, cfg, legacy_root, send=args.command=="run" and args.send)
                elif args.command == "configure":
                    if args.enable or args.disable:
                        cfg["enabled"] = bool(args.enable)
                        if args.enable:
                            cfg["enabled_at"] = stamp()
                        atomic_json(root / "config.json", cfg)
                    result = save_public_status(root, db, cfg)
                elif args.command == "unsubscribe":
                    email = args.email.strip().lower()
                    if not valid_email(email):
                        raise Blocked("invalid_recipient")
                    with db:
                        db.execute("INSERT OR IGNORE INTO blacklist VALUES (?,?)", (email, stamp()))
                    result = {"status": "unsubscribed"}
                elif args.command == "export":
                    result = export_csv(root, db, legacy_root)
                else:
                    _, counts = queue(db, legacy_root)
                    result = dict(save_public_status(root, db, cfg), queue=counts,
                                  attempts=dict(db.execute("SELECT state,COUNT(*) FROM attempts GROUP BY state").fetchall()))
            finally:
                db.close()
            print(json.dumps(result))
            return 2 if result.get("status") in {"failed", "partial_failure"} else 0
    except Blocked as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}))
        return 3
    except Exception:
        print(json.dumps({"status": "blocked", "error": "campaign_setup_or_data_error"}))
        return 3


if __name__ == "__main__":
    sys.exit(main())
