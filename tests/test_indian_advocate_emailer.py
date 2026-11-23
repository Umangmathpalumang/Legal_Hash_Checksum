"""Synthetic contacts only. No real credential reads, Gmail calls or messages."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import openpyxl

SPEC = importlib.util.spec_from_file_location("indian_emailer", Path(__file__).resolve().parents[1]/"scripts/indian-advocate-emailer.py")
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)
NOW = datetime(2026,11,23,10,40,tzinfo=timezone.utc)  # Monday 16:10 IST


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/"campaign"
        self.root.mkdir()
        self.db = app.connect(self.root)
        self.addCleanup(self.db.close)
        self.cfg = dict(app.DEFAULT_CONFIG)
        self.legacy = Path(self.temp.name)/"legacy"
        self.legacy.mkdir()
        self.workbook = Path(self.temp.name)/"source.xlsx"
        app._LEGACY_CACHE.clear()

    def book(self, rows=None):
        rows = rows or [self.contact("alpha@example.com"), self.contact("bravo@example.com")]
        wb = openpyxl.Workbook()
        sources = wb.active
        sources.title = "Sources"
        sources.cell(9,1,"FIXTURE")
        ws = wb.create_sheet("Emails for review")
        for i,key in enumerate(app.HEADERS,1):ws.cell(8,i,key)
        for i,row in enumerate(rows,9):
            for j,value in enumerate(row,1):ws.cell(i,j,value)
        wb.save(self.workbook)
        return self.workbook

    def contact(self, email, note=None, name=""):
        return [email,name,"","Advocate/panel directory","Fixture Court","FIXTURE","FIXTURE p.1",note or app.REVIEW_CLEAR]

    def load(self, rows=None):
        return app.import_workbook(self.db,self.book(rows))

    def snapshot(self, reserved=(), blocked=()):
        p=patch.object(app,"legacy_snapshot",return_value=(set(reserved),set(blocked)))
        p.start()
        self.addCleanup(p.stop)

    def run_batch(self, send=True, sender=None, now=NOW):
        self.cfg["enabled"]=True
        self.factory=MagicMock(return_value=object())
        self.sender=sender or MagicMock(return_value="gmail-fixture-id")
        return app.run_batch(self.root,self.db,self.cfg,self.legacy,send=send,now=now,
                             sleeper=lambda _:None,service_factory=self.factory,sender=self.sender)

    def test_strict_recipient_validation(self):
        for v in ["a@example.com","name+tool@example.co.in"]:self.assertTrue(app.valid_email(v))
        for v in ["bad\r\nBcc:evil@example.com","one@example.com,two@example.com","masked***@gmail.com",
                  "-lead@example.com","/lead@example.com","a@local","person@example..com","bad@example.com\n",None]:
            if v=="masked***@gmail.com":continue  # Held by review evidence rather than addr-spec grammar.
            self.assertFalse(app.valid_email(v),repr(v))

    def test_import_holds_flags_and_preserves_source(self):
        source=self.book([self.contact("good@example.com"),self.contact("old@example.com","Historical source"),
                          self.contact("wrong-address"),self.contact("good@example.com","Possible source domain typo")])
        before=source.read_bytes();result=app.import_workbook(self.db,source)
        self.assertEqual(result["imported"],3)
        self.assertEqual(result["source_flags_held"],3)
        self.assertEqual(source.read_bytes(),before)

    def test_formula_contact_is_rejected_before_any_database_change(self):
        self.load()
        before=self.db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        with self.assertRaises(app.Blocked):app.import_workbook(self.db,self.book([self.contact('="bad@example.com"')]))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],before)

    def test_unknown_source_is_held(self):
        row=self.contact("alpha@example.com");row[5]="UNKNOWN"
        self.load([row]);self.snapshot()
        self.assertEqual(app.queue(self.db,self.legacy)[1]["held_for_source_review"],1)

    def test_legacy_reservations_and_blacklist_override_new_queue(self):
        self.load([self.contact("old@example.com"),self.contact("blocked@example.com"),self.contact("new@example.com")])
        self.snapshot(reserved=["old@example.com"],blocked=["blocked@example.com"])
        queue,counts=app.queue(self.db,self.legacy)
        self.assertEqual([r["email"] for r in queue],["new@example.com"])
        self.assertEqual(counts["reserved_for_existing_campaigns"],1)
        self.assertEqual(counts["blacklisted"],1)

    def test_dry_run_never_opens_gmail_or_changes_attempts(self):
        self.load();self.snapshot()
        result=self.run_batch(send=False)
        self.assertEqual(result["planned"],2)
        self.factory.assert_not_called();self.sender.assert_not_called()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],0)

    def test_disabled_campaign_never_opens_gmail(self):
        factory=MagicMock()
        result=app.run_batch(self.root,self.db,self.cfg,self.legacy,send=True,now=NOW,service_factory=factory)
        self.assertEqual(result["status"],"paused");factory.assert_not_called()

    def test_weekend_and_outside_hours_never_open_gmail(self):
        self.load();self.snapshot()
        for now in [NOW+timedelta(days=5),NOW+timedelta(hours=4)]:
            result=self.run_batch(now=now)
            self.assertEqual(result["status"],"not_due");self.factory.assert_not_called()

    def test_success_is_durable_and_reimport_does_not_replay(self):
        self.load();self.snapshot();before=self.workbook.read_bytes()
        result=self.run_batch()
        self.assertEqual((result["status"],result["sent"]),("completed",2))
        attempts=self.db.execute("SELECT state,message_id,rfc_message_id FROM attempts").fetchall()
        self.assertTrue(all(r["state"]=="accepted" and r["message_id"]=="gmail-fixture-id" and r["rfc_message_id"] for r in attempts))
        app.import_workbook(self.db,self.workbook)
        self.assertEqual(app.queue(self.db,self.legacy)[0],[])
        self.assertEqual(self.workbook.read_bytes(),before)

    def test_uncertain_post_is_held_and_not_retried(self):
        self.load();self.snapshot()
        result=self.run_batch(sender=MagicMock(side_effect=TimeoutError("SECRET RESPONSE")))
        self.assertEqual(result["status"],"failed")
        self.assertEqual(self.db.execute("SELECT state FROM attempts").fetchone()[0],"uncertain")
        self.assertEqual([r["email"] for r in app.queue(self.db,self.legacy)[0]],["bravo@example.com"])
        self.assertIn("delivery_outcome_requires_review",result["warnings"])
        self.assertNotIn("SECRET",json.dumps(result))

    def test_hard_crash_preserves_attempting_and_prevents_replay(self):
        self.load();self.snapshot()
        with self.assertRaises(SystemExit):self.run_batch(sender=MagicMock(side_effect=SystemExit()))
        self.assertEqual(self.db.execute("SELECT state FROM attempts").fetchone()[0],"attempting")
        self.assertEqual([r["email"] for r in app.queue(self.db,self.legacy)[0]],["bravo@example.com"])

    def test_rate_error_sets_cooldown_and_stops_batch(self):
        self.load();self.snapshot()
        class LimitError(Exception):resp=type("Response",(),{"status":429})()
        result=self.run_batch(sender=MagicMock(side_effect=LimitError("SECRET")))
        self.assertEqual(result["status"],"failed");self.assertEqual(self.sender.call_count,1)
        self.assertEqual(app.remaining_budget(self.db,self.cfg,NOW+timedelta(minutes=10)),0)
        self.assertEqual(app.remaining_budget(self.db,self.cfg,NOW+timedelta(hours=1)),12)

    def test_rejected_request_is_not_retried(self):
        self.load();self.snapshot()
        class InvalidError(Exception):resp=type("Response",(),{"status":400})()
        self.run_batch(sender=MagicMock(side_effect=InvalidError()))
        self.assertEqual(self.db.execute("SELECT state FROM attempts").fetchone()[0],"rejected")
        self.assertEqual(len(app.queue(self.db,self.legacy)[0]),1)

    def test_success_then_failure_retains_accepted_id(self):
        self.load();self.snapshot()
        result=self.run_batch(sender=MagicMock(side_effect=["accepted-first",OSError("unknown")]))
        self.assertEqual((result["status"],result["sent"]),("partial_failure",1))
        self.assertEqual(self.db.execute("SELECT message_id FROM attempts WHERE email='alpha@example.com'").fetchone()[0],"accepted-first")

    def test_exclusions_are_checked_again_immediately_before_send(self):
        self.load()
        with patch.object(app,"legacy_snapshot",side_effect=[(set(),set()),({"alpha@example.com"},set()),(set(),set())]):
            result=self.run_batch()
        self.assertEqual(result["sent"],1)
        self.assertEqual(str(self.sender.call_args.args[1]["To"]),"bravo@example.com")

    def test_hourly_budget_resets_at_calendar_hour_without_rollover_skip(self):
        self.load();self.snapshot();self.cfg["hourly_limit"]=1
        result=self.run_batch()
        self.assertEqual(result["sent"],1)
        self.assertEqual(app.remaining_budget(self.db,self.cfg,NOW+timedelta(minutes=49)),0)
        self.assertEqual(app.remaining_budget(self.db,self.cfg,NOW+timedelta(minutes=50)),1)

    def test_daily_limit_is_checked_again_during_batch(self):
        self.load();self.snapshot();self.cfg["daily_limit"]=1
        self.assertEqual(self.run_batch()["sent"],1)
        self.assertEqual(app.remaining_budget(self.db,self.cfg,NOW+timedelta(hours=1)),0)

    def test_exclusive_campaign_lock(self):
        with app.campaign_lock(self.root):
            with self.assertRaises(app.Blocked):
                with app.campaign_lock(self.root):pass

    def test_invalid_config_cannot_expand_batch_or_switch_sender(self):
        for change in [{"sender":"other@example.com"},{"batch_size":100},{"enabled":"yes"}]:
            app.atomic_json(self.root/"config.json",dict(app.DEFAULT_CONFIG,**change))
            with self.assertRaises(app.Blocked):app.config(self.root)

    def test_no_api_retry_and_message_has_optout_header(self):
        service=MagicMock();service.users().messages().send().execute.return_value={"id":"fixture"}
        msg=app.message({"email":"alpha@example.com","name":"Fixture Advocate"},self.cfg,"<fixture@example.com>",NOW)
        self.assertEqual(app.api_send(service,msg),"fixture")
        service.users().messages().send().execute.assert_called_once_with(num_retries=0)
        self.assertIn("mailto:",str(msg["List-Unsubscribe"]))
        self.assertEqual(str(msg["Reply-To"]),app.OWNER)

    def test_missing_api_id_is_uncertain(self):
        service=MagicMock();service.users().messages().send().execute.return_value={}
        with self.assertRaises(app.Blocked):app.api_send(service,app.message({"email":"alpha@example.com"},self.cfg,"<fixture@example.com>",NOW))

    def test_missing_legacy_data_blocks_dry_run_instead_of_sending_new_duplicates(self):
        self.load()
        with self.assertRaises(app.Blocked):app.queue(self.db,self.legacy)

    def test_missing_legacy_data_is_saved_as_a_failed_live_run_without_gmail(self):
        self.load()
        result=self.run_batch()
        self.assertEqual(result["status"],"failed")
        self.assertIn("legacy_exclusion_file_unavailable",result["errors"])
        self.factory.assert_not_called()

    def test_legacy_file_change_invalidates_cached_exclusions(self):
        for filename,sheet,column in app.LEGACY_BOOKS:
            wb=openpyxl.Workbook();ws=wb.active;ws.title=sheet;ws.cell(2,column,"Email Address");ws.cell(3,column,"old@example.com");wb.save(self.legacy/filename)
        for name in ["allahabad_sent_state.json","sent_state.json"]:(self.legacy/name).write_text('{}')
        (self.legacy/"blacklist.txt").write_text('first@example.com\n')
        self.assertIn("first@example.com",app.legacy_snapshot(self.legacy)[1])
        (self.legacy/"blacklist.txt").write_text('second@example.com\n')
        reserved,blocked=app.legacy_snapshot(self.legacy)
        self.assertIn("old@example.com",reserved);self.assertIn("second@example.com",blocked)

    def test_export_keeps_acceptance_ids_and_source_metadata(self):
        self.load();self.snapshot();self.run_batch();app.export_csv(self.root,self.db,self.legacy)
        import csv
        with (self.root/"send-status.csv").open(encoding="utf-8-sig") as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["gmail_message_id"],"gmail-fixture-id")
        self.assertEqual(rows[0]["source_ids"],"FIXTURE")


if __name__=="__main__":unittest.main()
