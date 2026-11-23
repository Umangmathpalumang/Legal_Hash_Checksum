"""Exercise campaign repairs against synthetic code and contacts; never send mail."""
import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runtime_repair", ROOT / "scripts/repair-outreach-runtime.py")
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


def campaign(scopes):
    return '# Unicode preamble: ✓\ndef get_gmail_service():\n    SCOPES = ' + repr(scopes) + '\n    return SCOPES\n'


CALCUTTA = '''SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
def get_gmail_service():
  return SCOPES
def create_message(sender_email, to_email, subject, body_text):
  return {"to": to_email}
def run_batch():
  for row in range(3, 8):
    email = "fixture@example.com"
    if not email or "@" not in email:
      continue
    create_message("sender@example.com", email, "subject", "body")
'''


class RuntimeRepairTests(unittest.TestCase):
    def test_scope_fix_removes_only_ungranted_read_permission(self):
        original = campaign([repair.SEND, repair.READ])
        fixed = repair.patch_scopes(original)
        namespace = {}
        exec(compile(fixed, "fixture", "exec"), namespace)
        self.assertEqual(namespace["get_gmail_service"](), [repair.SEND])
        self.assertIn("Unicode preamble: ✓", fixed)
        self.assertEqual(repair.patch_scopes(fixed), fixed)

    def test_unrecognized_scope_cannot_be_rewritten_silently(self):
        with self.assertRaises(ValueError):
            repair.patch_scopes(campaign([repair.SEND, "gmail.modify"]))

    def test_already_correct_calcutta_scope_is_preserved(self):
        self.assertEqual(repair.patch_scopes(CALCUTTA), CALCUTTA)

    def test_recipient_guard_rejects_malformed_and_injected_headers(self):
        fixed = repair.patch_recipients(CALCUTTA)
        ns = {}
        exec(compile(fixed, "fixture", "exec"), ns)
        valid = ns["_valid_recipient"]
        for value in ("advocate@example.com", "first.last+case@example.co.in"):
            self.assertTrue(valid(value), value)
            self.assertEqual(ns["create_message"]("sender@example.com", value, "s", "b")["to"], value)
        for value in ("", None, "name@example..com", "name@.com", "one@example.com;two@example.com", "one@example.com,two@example.com", "name@example.com\r\nBcc: other@example.com", "@example.com", "name@localhost"):
            self.assertFalse(valid(value), repr(value))
            with self.assertRaises(ValueError):
                ns["create_message"]("sender@example.com", value, "s", "b")
        self.assertEqual(repair.patch_recipients(fixed), fixed)

    def test_unknown_recipient_code_requires_review(self):
        with self.assertRaises(ValueError):
            repair.patch_recipients(CALCUTTA.replace('if not email or "@" not in email:', 'if email is None:'))

    def test_code_apply_backs_up_and_preserves_all_operational_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in repair.FILES:
                (root / name).write_text(CALCUTTA if name == "calcutta_emailer.py" else campaign([repair.SEND, repair.READ]))
            for name in ("token.json", "credentials.json", "allahabad_sent_state.json", "sent_state.json"):
                (root / name).write_text(json.dumps({"fixture": "preserve-me"}))
            (root / "blacklist.txt").write_text("blocked@example.com\n")
            (root / "contacts.xlsx").write_bytes(b"preserve workbook bytes")
            before = repair.protected_hashes(root)
            preview = repair.repair(root)
            self.assertFalse(preview["applied"])
            result = repair.repair(root, apply=True)
            self.assertTrue(result["contacts_history_credentials_unchanged"])
            self.assertEqual(before, repair.protected_hashes(root))
            backup = Path(result["backup_directory"])
            self.assertEqual(len(list(backup.glob("*.py"))), 3)
            self.assertEqual((backup / "allahabad_emailer.py").stat().st_mode & 0o777, 0o600)
            self.assertEqual(repair.repair(root, apply=True)["changed_code_files"], [])


if __name__ == "__main__":
    unittest.main()
