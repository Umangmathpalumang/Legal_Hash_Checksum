"""Synthetic recovery tests. No real contacts, credentials, or email calls."""
import ast
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("allahabad_repair", ROOT / "scripts/repair-allahabad-crm.py")
crm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(crm)


SOURCE = '''from pathlib import Path
CONTACTS = []
def get_unsent(state):
    bl = load_blacklist()
    return [c for c in CONTACTS if c["email"] not in state and c["email"].lower() not in bl]
def send_email(service, to_email, subject, body):
    return service.send(to_email)
def update_excel_crm(contact, email_num, template_used, sent_at_dt):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(EXCEL_FILE)
        wb.save(EXCEL_FILE)
    except Exception as exc:
        log.warning(type(exc).__name__)
'''


class AllahabadRepairTests(unittest.TestCase):
    def test_reconciliation_fills_live_fields_without_rebuilding_contact_cells(self):
        import openpyxl
        contact = {"sl": 1, "roll": "001", "name": "Fixture", "email": "fixture@example.com", "address": "Original", "remarks": "Keep"}
        history = {contact["email"]: {"sent_at": "2026-11-23T08:30:00", "msg_id": "fixture-id"}}
        with tempfile.TemporaryDirectory() as folder:
            original, staged = Path(folder) / "original.xlsx", Path(folder) / "staged.xlsx"
            crm.build_workbook(original, [contact], {}, set())
            wb = openpyxl.load_workbook(original)
            wb["Allahabad HC Advocates"].column_dimensions["E"].width = 61
            wb["Send Log"].append([datetime(2026, 11, 23), "02:00 PM", "Fixture", contact["email"], "1", "t1", "Python Script"])
            wb.save(original)
            wb.close()
            before = original.read_bytes()
            crm.reconcile_workbook(original, staged, history)
            self.assertEqual(original.read_bytes(), before)
            self.assertEqual(crm.verify_workbook(staged, [contact], history)["send_log_rows"], 1)
            wb = openpyxl.load_workbook(staged)
            self.assertEqual(wb["Allahabad HC Advocates"]["G3"].value, "Sent")
            self.assertEqual(wb["Allahabad HC Advocates"]["I3"].value, "fixture-id")
            self.assertEqual(wb["Allahabad HC Advocates"].column_dimensions["E"].width, 61)
            self.assertEqual(wb["Send Log"]["F2"].value, "t1")
            wb.close()

    def test_concurrent_crm_change_is_not_overwritten(self):
        ns = {}
        exec(crm.ATOMIC_SAVE, ns)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "crm.xlsx"
            path.write_bytes(b"original")
            stat = path.stat()
            signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
            def competing_save(staged):
                with zipfile.ZipFile(staged, "w") as archive:
                    archive.writestr("xl/workbook.xml", "fixture")
                path.write_bytes(b"external update")
            workbook = MagicMock()
            workbook.save.side_effect = competing_save
            with self.assertRaisesRegex(RuntimeError, "CRM changed"):
                ns["_save_crm_atomic"](workbook, path, signature)
            self.assertEqual(path.read_bytes(), b"external update")

    def test_live_crm_writer_updates_status_time_and_message_id_atomically(self):
        import openpyxl
        full_writer = '''def update_excel_crm(contact, email_num, template_used, sent_at_dt):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb["Allahabad HC Advocates"]
        email_lower = contact["email"].lower().strip()
        sent_date = sent_at_dt.date()
        STATUS = {1: "Email 1 Sent"}
        for row in ws.iter_rows(min_row=3, max_row=ws.max_row):
            if row[3].value and row[3].value.lower().strip() == email_lower:
                # Add sent date in col F onwards if available
                break
        ws_log = wb["Send Log"]
        ws_log.append([sent_date, sent_at_dt.strftime("%I:%M %p"), contact.get("name", ""), contact["email"],
                       str(email_num), template_used, "Python Script"])
        wb.save(EXCEL_FILE)
    except Exception as exc:
        log.warning(type(exc).__name__)
'''
        source = SOURCE[:SOURCE.index("def update_excel_crm")] + full_writer
        fixed = crm.patch_code(source)
        contact = {"sl": 1, "roll": "001", "name": "Fixture", "email": "fixture@example.com", "address": "", "remarks": ""}
        record = {"sent_at": "2026-11-23T08:30:00", "msg_id": "new-fixture-id"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "crm.xlsx"
            crm.build_workbook(path, [contact], {}, set())
            ns = {"EXCEL_FILE": str(path), "load_state": lambda: {contact["email"]: record}, "log": MagicMock()}
            exec(compile(fixed, "reviewed synthetic writer", "exec"), ns)
            ns["update_excel_crm"](contact, 1, "t1", datetime(2026, 11, 23, 8, 30))
            ns["log"].warning.assert_not_called()
            wb = openpyxl.load_workbook(path)
            self.assertEqual(wb["Allahabad HC Advocates"]["G3"].value, "Email 1 Sent")
            self.assertEqual(wb["Allahabad HC Advocates"]["H3"].value, datetime(2026, 11, 23, 14, 0))
            self.assertEqual(wb["Allahabad HC Advocates"]["I3"].value, "new-fixture-id")
            self.assertEqual(wb["Send Log"]["H2"].value, "new-fixture-id")
            wb.close()

    def test_bad_addresses_are_filtered_without_mutating_contacts_or_history(self):
        fixed = crm.patch_code(SOURCE)
        contacts = [{"email": value} for value in ("sent@example.com", "blocked@example.com", "good@example.com", "bad@.com", "bad@example.com\r\nBcc:extra@example.com")]
        original = json.dumps(contacts)
        ns = {"CONTACTS": contacts, "load_blacklist": lambda: {"blocked@example.com"}, "log": MagicMock()}
        # Run only the reviewed pure functions, never a campaign entrypoint.
        tree = ast.parse(fixed)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in ("_valid_recipient", "get_unsent", "send_email"):
                exec(compile(ast.Module(body=[node], type_ignores=[]), "fixture", "exec"), ns)
        state = {"sent@example.com": {"msg_id": "fixture"}}
        self.assertEqual(ns["get_unsent"](state), [{"email": "good@example.com"}])
        self.assertEqual(json.dumps(contacts), original)
        self.assertEqual(len(state), 1)
        sender = MagicMock()
        with self.assertRaises(ValueError):
            ns["send_email"](sender, "bad@.com", "s", "b")
        sender.send.assert_not_called()
        self.assertEqual(crm.patch_code(fixed), fixed)

    def test_atomic_save_failure_keeps_existing_workbook(self):
        ns = {}
        exec(crm.ATOMIC_SAVE, ns)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "crm.xlsx"
            path.write_bytes(b"existing workbook")
            stat = path.stat()
            signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
            wb = MagicMock()
            wb.save.side_effect = lambda staged: Path(staged).write_bytes(b"PKtruncated")
            with self.assertRaises(zipfile.BadZipFile):
                ns["_save_crm_atomic"](wb, path, signature)
            self.assertEqual(path.read_bytes(), b"existing workbook")
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_recovery_preserves_all_rows_history_ids_and_formula_like_text(self):
        import openpyxl
        contacts = [
            {"sl": 0, "roll": "001", "name": "=A1", "email": "sent@example.com", "address": "Fixture", "remarks": ""},
            {"sl": 2, "roll": "002", "name": "Unsent", "email": "new@example.com", "address": None, "remarks": "Original note"},
            {"sl": 3, "roll": "003", "name": "Invalid", "email": "bad@.com", "address": "", "remarks": ""},
        ]
        history = {"sent@example.com": {"name": "=A1", "sent_at": "2026-11-23T07:30:00", "msg_id": "fixture-message"}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "recovered.xlsx"
            crm.build_workbook(path, contacts, history, set())
            self.assertEqual(crm.verify_workbook(path, contacts, history),
                             {"contact_rows": 3, "send_log_rows": 1, "zip_verified": True})
            wb = openpyxl.load_workbook(path)
            ws = wb["Allahabad HC Advocates"]
            self.assertEqual(ws["C3"].data_type, "s")
            self.assertEqual(ws["H3"].value, datetime(2026, 11, 23, 13, 0))
            self.assertEqual(ws["G5"].value, "Invalid address")
            self.assertEqual(ws["D2"].value, "Email")
            self.assertEqual(wb["Send Log"]["H2"].value, "fixture-message")
            wb.close()

    def test_full_repair_backs_up_truncation_and_does_not_reset_history(self):
        contacts = [{"sl": 1, "roll": "001", "name": "Fixture", "email": "fixture@example.com", "address": "", "remarks": ""}]
        history = {"fixture@example.com": {"name": "Fixture", "sent_at": "2026-11-23T07:30:00", "msg_id": "fixture-message"}}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = SOURCE.replace("CONTACTS = []", "CONTACTS = " + repr(contacts))
            (root / "allahabad_emailer.py").write_text(source)
            book = root / "Allahabad_HC_Advocates.xlsx"
            book.write_bytes(b"PKtruncated")
            state = root / "allahabad_sent_state.json"
            state.write_text(json.dumps(history))
            (root / "token.json").write_text('{"fixture":"secret"}')
            (root / "blacklist.txt").write_text("blocked@example.com\n")
            before = state.read_bytes()
            preview = crm.repair(root)
            self.assertFalse(preview["applied"])
            self.assertEqual(book.read_bytes(), b"PKtruncated")
            with patch.object(crm, "campaign_running", return_value=False):
                result = crm.repair(root, apply=True)
            self.assertTrue(result["history_credentials_blacklist_unchanged"])
            self.assertEqual(state.read_bytes(), before)
            self.assertEqual((Path(result["backup_directory"]) / book.name).read_bytes(), b"PKtruncated")
            self.assertEqual(crm.repair(root, apply=True)["applied"], False)


if __name__ == "__main__":
    unittest.main()
