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
from datetime import datetime
from urllib.parse import parse_qs


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gmail_health", ROOT / "scripts/check-gmail-health.py")
health = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)


class GmailHealthTests(unittest.TestCase):
    def setUp(self):
        no_real_logs = patch.object(health, "check_campaigns", return_value={})
        no_real_logs.start()
        self.addCleanup(no_real_logs.stop)

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
                (root / name).write_text("SENDER_EMAIL = " + repr(health.OWNER)
                                        + "\nSCOPES = " + repr([health.SEND_SCOPE])
                                        + "\nraise RuntimeError('Must never execute a campaign')\n")
            response = MagicMock()
            response.__enter__.return_value = BytesIO(b'{"access_token":"ACCESS"}')
            with patch.object(health.request, "urlopen", return_value=response) as urlopen:
                self.assertEqual(health.check_outreach(), ("ok", "ACCESS"))
                self.assertEqual(parse_qs(urlopen.call_args.args[0].data.decode())["scope"], [health.SEND_SCOPE])
            self.assertEqual(token_path.read_bytes(), original)
            (root / "allahabad_emailer.py").write_text(
                "SENDER_EMAIL = " + repr(health.OWNER)
                + "\ndef get_gmail_service():\n SCOPES = "
                + repr([health.SEND_SCOPE, "https://www.googleapis.com/auth/gmail.readonly"]) + "\n")
            response.__enter__.return_value = BytesIO(b'{"access_token":"ACCESS"}')
            with patch.object(health.request, "urlopen", return_value=response):
                self.assertEqual(health.check_outreach(), ("scope_mismatch", "ACCESS"))
            rejected = HTTPError(health.TOKEN_URL, 400, "bad", {}, BytesIO(b'{"error":"invalid_grant"}'))
            with patch.object(health.request, "urlopen", side_effect=rejected):
                self.assertEqual(health.check_outreach(), ("auth_failed", None))
            rejected = HTTPError(health.TOKEN_URL, 400, "bad", {}, BytesIO(b'{"error":"invalid_scope"}'))
            with patch.object(health.request, "urlopen", side_effect=rejected):
                self.assertEqual(health.check_outreach(), ("scope_mismatch", None))
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

    def test_scope_failure_guidance_does_not_request_password_or_inbox_access(self):
        body = health.recovery_body({"feedback": "ok", "outreach": "scope_mismatch"})
        self.assertIn("repair-outreach-runtime.py --remote --apply", body)
        self.assertNotIn("update-feedback-gmail.py", body)
        self.assertNotIn("reauthorize-outreach-gmail.py --reauthorize", body)

    def test_healthy_oauth_token_can_alert_for_campaign_scope_mismatch(self):
        response = MagicMock()
        response.__enter__.return_value = BytesIO(b'{"id":"fixture"}')
        with patch.object(health.request, "urlopen", return_value=response):
            self.assertEqual(health.send_owner_email("Failure", "body",
                {"feedback": "auth_failed", "outreach": "scope_mismatch"}, None, "ACCESS"), "accepted_oauth")


class CampaignStatusTests(unittest.TestCase):
    def test_allahabad_failure_email_has_data_repair_steps_not_password_rotation(self):
        campaigns = {"allahabad": {"status": "partial_failure", "last_run": "2026-11-23T13:00:00",
                                  "sent": 9, "errors": ["invalid_recipient"], "warnings": ["crm_workbook_corrupt"]}}
        body = health.recovery_body({"feedback": "ok", "outreach": "ok", "outreach_jobs": "delivery_failed"}, campaigns)
        self.assertIn("repair-allahabad-crm.py --remote --apply", body)
        self.assertNotIn("update-feedback-gmail.py", body)
        self.assertNotIn("reauthorize-outreach-gmail.py --reauthorize", body)

    def test_latest_failed_run_is_not_hidden_by_older_success(self):
        text = """2026-11-23 09:00:00 INFO === Allahabad HC Emailer starting ===
2026-11-23 09:03:00 INFO === Done. Sent 12/12. Total: 12/200 ===
2026-11-23 10:00:00 INFO === Allahabad HC Emailer starting ===
google.auth.exceptions.RefreshError: ('invalid_scope: Bad Request', {})
"""
        result = health.campaign_snapshot(text, datetime(2026, 11, 23, 10, 15))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["sent"], 0)
        self.assertIn("invalid_scope", result["errors"])

    def test_corrupt_crm_warning_does_not_hide_successful_sends(self):
        text = """2026-11-23 12:00:00 INFO === Allahabad HC Emailer starting ===
2026-11-23 12:01:00 WARNING Excel update failed: File is not a zip file
2026-11-23 12:02:00 INFO === Done. Sent 9/12. Total: 4208/20588 ===
"""
        result = health.campaign_snapshot(text, datetime(2026, 11, 23, 12, 15))
        self.assertEqual((result["status"], result["sent"]), ("completed", 9))
        self.assertIn("crm_workbook_corrupt", result["warnings"])

    def test_calcutta_invalid_headers_are_delivery_failure_despite_valid_auth(self):
        text = """2026-11-23 11:20:00 INFO IST time: Mon 23-Nov 11:20 AM | Working hours: True
2026-11-23 11:20:05 ERROR Failed: HttpError 400 Invalid To header
2026-11-23 11:20:12 INFO === Done. Sent 0/12 this run. Excel CRM updated. ===
"""
        result = health.campaign_snapshot(text, datetime(2026, 11, 23, 12, 15), 20, False)
        self.assertEqual(result["status"], "failed")
        self.assertIn("invalid_recipient", result["errors"])
        self.assertNotIn("header", json.dumps(result))

    def test_completed_queue_is_normal_and_does_not_require_repeat_emailing(self):
        text = """2026-11-23 11:40:00 INFO === LHC Emailer starting ===
2026-11-23 11:40:00 INFO All contacts have been emailed. Nothing to do.
"""
        self.assertEqual(health.campaign_snapshot(text, datetime(2026, 11, 23, 12, 15), 40)["status"], "empty_queue")

    def test_missing_cron_run_is_reported_after_grace_period(self):
        self.assertEqual(health.campaign_snapshot("", datetime(2026, 11, 23, 12, 14))["status"], "not_due")
        self.assertEqual(health.campaign_snapshot("", datetime(2026, 11, 23, 12, 16))["status"], "schedule_missed")

    def test_midnight_and_weekend_do_not_create_false_missing_run_alert(self):
        self.assertEqual(health.campaign_snapshot("", datetime(2026, 11, 23, 0, 15), 20, False)["status"], "not_due")
        self.assertEqual(health.campaign_snapshot("", datetime(2026, 11, 22, 12, 16))["status"], "not_due")

    def test_new_run_clears_previous_header_failures(self):
        text = """2026-11-23 11:20:00 INFO IST time: Mon 23-Nov 11:20 AM | Working hours: True
2026-11-23 11:20:01 ERROR HttpError 400 Invalid To header
2026-11-23 11:20:02 INFO === Done. Sent 0/12 this run. Excel CRM updated. ===
2026-11-23 12:20:00 INFO IST time: Mon 23-Nov 12:20 PM | Working hours: True
2026-11-23 12:20:01 WARNING Skipping invalid recipient in workbook row 4; contact unchanged
2026-11-23 12:20:02 INFO === Done. Sent 0/12 this run. Excel CRM updated. ===
"""
        result = health.campaign_snapshot(text, datetime(2026, 11, 23, 12, 25), 20, False)
        self.assertEqual(result["status"], "empty_queue")
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()
