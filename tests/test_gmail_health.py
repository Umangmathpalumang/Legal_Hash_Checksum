"""No real Gmail requests or messages: exercise outage alerts and recovery."""
import importlib.util
import json
from pathlib import Path
import smtplib
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from io import BytesIO


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gmail_health", ROOT / "scripts/check-gmail-health.py")
health = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)


class GmailHealthTests(unittest.TestCase):
    def test_first_failure_and_daily_reminder(self):
        checks = {"feedback": "ok", "outreach": "auth_failed"}
        kind, signature = health.notification_kind({}, checks, 100)
        self.assertEqual(kind, "failure")
        previous = {"notified_signature": signature, "last_notified_at": 100}
        self.assertIsNone(health.notification_kind(previous, checks, 200)[0])
        self.assertEqual(health.notification_kind(previous, checks, 86501)[0], "failure")

    def test_new_failure_and_recovery_are_not_suppressed(self):
        previous = {"notified_signature": "outreach:auth_failed", "last_notified_at": 100}
        checks = {"feedback": "auth_failed", "outreach": "auth_failed"}
        self.assertEqual(health.notification_kind(previous, checks, 110)[0], "failure")
        self.assertEqual(health.notification_kind(previous, {"feedback": "ok", "outreach": "ok"}, 110),
                         ("recovery", ""))

    def test_outreach_failure_alert_uses_smtp_and_fixed_recipient(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.send_message.return_value = {}
        with patch.object(health, "smtp_connection", return_value=connection), patch.object(health.request, "urlopen") as urlopen:
            result = health.send_owner_email("Failure", "body", {"feedback": "ok", "outreach": "auth_failed"},
                                             ("fixture@gmail.com", "SECRET"), None)
        self.assertEqual(result, "accepted_smtp")
        self.assertEqual(connection.send_message.call_args.kwargs["to_addrs"], [health.OWNER])
        self.assertEqual(str(connection.send_message.call_args.args[0]["To"]), health.OWNER)
        urlopen.assert_not_called()

    def test_feedback_failure_uses_oauth(self):
        response = MagicMock()
        response.__enter__.return_value = BytesIO(b'{"id":"accepted-fixture"}')
        with patch.object(health.request, "urlopen", return_value=response) as urlopen, patch.object(health, "smtp_connection") as smtp:
            result = health.send_owner_email("Failure", "body", {"feedback": "auth_failed", "outreach": "ok"}, None, "ACCESS")
        self.assertEqual(result, "accepted_oauth")
        self.assertEqual(urlopen.call_args.args[0].full_url,
                         "https://gmail.googleapis.com/gmail/v1/users/me/messages/send")
        smtp.assert_not_called()

    def test_both_credentials_failed_never_attempts_email(self):
        with patch.object(health.request, "urlopen") as urlopen, patch.object(health, "smtp_connection") as smtp:
            result = health.send_owner_email("Failure", "body", {"feedback": "auth_failed", "outreach": "auth_failed"}, None, None)
        self.assertEqual(result, "unavailable")
        urlopen.assert_not_called()
        smtp.assert_not_called()

    def test_ambiguous_smtp_failure_does_not_fall_back_and_duplicate_message(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.send_message.side_effect = OSError("contains SECRET")
        with patch.object(health, "smtp_connection", return_value=connection), patch.object(health.request, "urlopen") as urlopen:
            result = health.send_owner_email("Failure", "body", {"feedback": "ok", "outreach": "ok"},
                                             ("fixture@gmail.com", "SECRET"), "ACCESS")
        self.assertEqual(result, "failed")
        urlopen.assert_not_called()

    def test_auth_failure_and_network_error_are_distinct(self):
        with patch.object(health, "feedback_settings", return_value=("ok", ("fixture", "SECRET"))):
            with patch.object(health, "smtp_connection", side_effect=smtplib.SMTPAuthenticationError(535, b"SECRET")):
                self.assertEqual(health.check_feedback(), ("auth_failed", None))
            with patch.object(health, "smtp_connection", side_effect=OSError("SECRET")):
                self.assertEqual(health.check_feedback(), ("network_error", None))

    def test_recovery_commands_are_specific_and_no_passwords_are_in_email(self):
        body = health.recovery_body({"feedback": "ok", "outreach": "auth_failed"})
        self.assertIn("reauthorize-outreach-gmail.py --reauthorize", body)
        self.assertNotIn("update-feedback-gmail.py", body)
        body = health.recovery_body({"feedback": "auth_failed", "outreach": "ok"})
        self.assertIn("update-feedback-gmail.py", body)
        self.assertNotIn("reauthorize-outreach-gmail.py --reauthorize", body)

    def test_failed_delivery_remains_pending_then_recovers_once(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(health, "STATE_DIR", Path(folder)), patch.object(health, "check_feedback", return_value=("auth_failed", None)), patch.object(health, "check_outreach", return_value=("auth_failed", None)), patch.object(health, "send_owner_email", return_value="unavailable"), patch("builtins.print"):
                self.assertEqual(health.run_check(notify=True), 2)
                state = health.read_state()
                self.assertTrue(state["pending_notification"])
                self.assertEqual((Path(folder) / "state.json").stat().st_mode & 0o777, 0o600)
            with patch.object(health, "STATE_DIR", Path(folder)), patch.object(health, "check_feedback", return_value=("ok", ("fixture", "SECRET"))), patch.object(health, "check_outreach", return_value=("auth_failed", None)), patch.object(health, "send_owner_email", return_value="accepted_smtp") as send, patch("builtins.print"):
                health.run_check(notify=True)
                health.run_check(notify=True)
                self.assertEqual(send.call_count, 1)
                self.assertFalse(health.read_state()["pending_notification"])
            with patch.object(health, "STATE_DIR", Path(folder)), patch.object(health, "check_feedback", return_value=("ok", ("fixture", "SECRET"))), patch.object(health, "check_outreach", return_value=("ok", "ACCESS")), patch.object(health, "send_owner_email", return_value="accepted_smtp") as send, patch("builtins.print"):
                self.assertEqual(health.run_check(notify=True), 0)
                health.run_check(notify=True)
                self.assertEqual(send.call_count, 1)
                self.assertEqual(health.read_state()["notified_signature"], "")
                stored = (Path(folder) / "state.json").read_text()
                self.assertNotIn("SECRET", stored)
                self.assertNotIn("ACCESS", stored)

    def test_outreach_probe_preserves_token_and_rejects_expanded_scope(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(health.Path, "home", return_value=Path(folder)):
            root = Path(folder) / "lhc"
            root.mkdir()
            token = {"token_uri": health.TOKEN_URL, "client_id": "fixture", "client_secret": "SECRET",
                     "refresh_token": "REFRESH", "scopes": [health.SEND_SCOPE]}
            token_path = root / "token.json"
            token_path.write_text(json.dumps(token))
            original = token_path.read_bytes()
            (root / "credentials.json").write_text(json.dumps({"installed": {"token_uri": health.TOKEN_URL, "client_id": "fixture"}}))
            for name in ("allahabad_emailer.py", "calcutta_emailer.py", "lhc_emailer.py"):
                (root / name).write_text("SENDER_EMAIL = " + repr(health.OWNER) + "\nraise RuntimeError('Must never execute a campaign')\n")
            response = MagicMock()
            response.__enter__.return_value = BytesIO(b'{"access_token":"ACCESS"}')
            with patch.object(health.request, "urlopen", return_value=response):
                self.assertEqual(health.check_outreach(), ("ok", "ACCESS"))
            self.assertEqual(token_path.read_bytes(), original)
            rejected = HTTPError(health.TOKEN_URL, 400, "bad", {}, BytesIO(b'{"error":"invalid_grant"}'))
            with patch.object(health.request, "urlopen", side_effect=rejected):
                self.assertEqual(health.check_outreach(), ("auth_failed", None))
            with patch.object(health.request, "urlopen", side_effect=URLError("SECRET")):
                self.assertEqual(health.check_outreach(), ("network_error", None))
            token["scopes"].append("gmail.readonly")
            token_path.write_text(json.dumps(token))
            with patch.object(health.request, "urlopen") as urlopen:
                self.assertEqual(health.check_outreach(), ("config_error", None))
                urlopen.assert_not_called()

    def test_missing_or_stale_monitor_state_is_visible(self):
        self.assertTrue(health.public_status({}, 100000)["stale"])
        self.assertFalse(health.public_status({"checked_at": 100000}, 100010)["stale"])


if __name__ == "__main__":
    unittest.main()
