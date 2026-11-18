"""Exercise token recovery with synthetic credentials and a temporary home."""
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = runpy.run_path(str(ROOT / "scripts/reauthorize-outreach-gmail.py"))
SEND = "https://www.googleapis.com/auth/gmail.send"


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / "lhc"
        self.root.mkdir()
        self.old = {"client_id": "fixture", "token_uri": "https://oauth2.googleapis.com/token",
                    "scopes": [SEND], "refresh_token": "expired", "token": "old"}
        self.new = dict(self.old, refresh_token="replacement", token="new")
        self.target = self.root / "token.json"
        self.original = json.dumps(self.old).encode()
        self.target.write_bytes(self.original)
        (self.root / "sent_state.json").write_text('{"already_sent": 4199}')
        (self.root / "blacklist.txt").write_text("blocked@example.test\n")

    def install(self, replacement=None, digest=None):
        body = {"token": replacement if replacement is not None else self.new,
                "sha256": digest or hashlib.sha256(self.original).hexdigest()}
        with patch.object(Path, "home", return_value=self.home), patch("sys.stdin", io.StringIO(json.dumps(body))), redirect_stdout(io.StringIO()):
            exec(HELPER["REMOTE_INSTALL"], {})

    def test_reads_shared_token_with_existing_sender_aliases(self):
        (self.root / "credentials.json").write_text(json.dumps(
            {"installed": {"client_id": "fixture", "token_uri": self.old["token_uri"]}}
        ))
        for name, address in (("allahabad", "support@example.test"),
                              ("calcutta", "fixture@gmail.com"),
                              ("lhc", "support@example.test")):
            (self.root / f"{name}_emailer.py").write_text(f"SENDER_EMAIL={address!r}\n")
        output = io.StringIO()
        with patch.object(Path, "home", return_value=self.home), redirect_stdout(output):
            exec(HELPER["REMOTE_READ"], {})
        bundle = json.loads(output.getvalue())
        self.assertEqual(bundle["sender"], "fixture@gmail.com")
        self.assertEqual(bundle["scopes"], [SEND])
        self.assertEqual(bundle["sha256"], hashlib.sha256(self.original).hexdigest())

    def test_installs_atomically_with_private_backup(self):
        self.install()
        self.assertEqual(json.loads(self.target.read_text()), self.new)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        folder = self.root / ".oauth-backups"
        self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
        backups = list(folder.glob("token-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.original)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / "sent_state.json").read_text(), '{"already_sent": 4199}')
        self.assertEqual((self.root / "blacklist.txt").read_text(), "blocked@example.test\n")

    def test_rejects_scope_expansion_and_changed_client(self):
        for token in (dict(self.new, scopes=[SEND, "gmail.readonly"]),
                      dict(self.new, client_id="different"),
                      dict(self.new, token_uri="https://example.test/"),
                      dict(self.new, refresh_token="")):
            with self.assertRaises(SystemExit):
                self.install(token)
            self.assertEqual(self.target.read_bytes(), self.original)

    def test_rejects_concurrent_change(self):
        with self.assertRaises(SystemExit):
            self.install(digest="not-the-original-hash")
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_rejects_token_symlink(self):
        other = self.root / "other.json"
        self.target.rename(other)
        self.target.symlink_to(other)
        with self.assertRaises(SystemExit):
            self.install()
        self.assertEqual(other.read_bytes(), self.original)

    def test_helper_has_no_campaign_send_calls(self):
        for name in ("REMOTE_READ", "REMOTE_INSTALL"):
            self.assertNotIn("sendmail", HELPER[name])
            self.assertNotIn("messages().send", HELPER[name])
            self.assertNotIn("run_batch", HELPER[name])


if __name__ == "__main__":
    unittest.main()
