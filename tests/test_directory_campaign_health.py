"""Only saved synthetic JSON is inspected; no Gmail or SSH calls."""
import importlib.util
import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location("directory_health",Path(__file__).resolve().parents[1]/"scripts/check-gmail-health.py")
app=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(app)


class DirectoryHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/"config.json").write_text(json.dumps({"enabled":True,"enabled_at":"2026-11-23T03:00:00+00:00"}))
        self.saved={"status":"completed","last_run":"2026-11-23T09:40:05+00:00","sent":12,"errors":[],"warnings":[]}

    def read(self,now=datetime(2026,11,23,15,30)):
        (self.root/"latest_run.json").write_text(json.dumps(self.saved))
        return app.directory_campaign_snapshot(self.root,now)

    def test_disabled_campaign_does_not_require_a_run(self):
        (self.root/"config.json").write_text('{"enabled":false}')
        self.assertEqual(app.directory_campaign_snapshot(self.root,datetime(2026,11,23,15,30))["status"],"paused")

    def test_completed_status_converts_utc_to_ist(self):
        result=self.read();self.assertEqual(result["status"],"completed")
        self.assertEqual(result["last_run"],"2026-11-23T15:10:05");self.assertEqual(result["sent"],12)

    def test_stuck_attempt_is_reported(self):
        self.saved["status"]="in_progress"
        self.assertIn("run_did_not_finish",self.read()["errors"])

    def test_uncertain_delivery_hold_remains_actionable_after_a_later_success(self):
        self.saved["warnings"]=["delivery_outcome_requires_review"]
        self.assertEqual(self.read()["status"],"partial_failure")

    def test_missed_schedule_is_reported(self):
        self.saved["last_run"]="2026-11-23T08:40:05+00:00"
        self.assertEqual(self.read()["status"],"schedule_missed")

    def test_activation_does_not_backdate_a_missed_run(self):
        (self.root/"config.json").write_text('{"enabled":true,"enabled_at":"2026-11-23T10:00:00+00:00"}')
        self.saved.update(status="not_due",last_run=None,sent=0)
        self.assertEqual(self.read()["status"],"not_due")

    def test_arbitrary_error_text_is_redacted(self):
        self.saved.update(status="failed",errors=["SECRET API RESPONSE"])
        result=self.read();self.assertNotIn("SECRET",json.dumps(result));self.assertEqual(result["errors"],["unexpected_campaign_error"])

    def test_empty_queue_and_budget_pause_are_normal(self):
        for status in ["empty_queue","rate_limited"]:
            self.saved["status"]=status;self.assertEqual(self.read()["status"],status)


if __name__=="__main__":unittest.main()
