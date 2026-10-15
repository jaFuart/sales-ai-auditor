from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from auditor.common import AuditorError, parse_time
from auditor.demo import AS_OF, demo_snapshot
from auditor.report import build_report, task_issues
from auditor.store import Store
from auditor.__main__ import snapshot_for


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = demo_snapshot()
        self.now = parse_time(AS_OF)

    def test_only_unfinished_direct_lead_tasks_cover_the_deal(self):
        task = {"complete_till": (self.now - timedelta(days=1)).isoformat(), "is_completed": True, "entity_type": "leads"}
        self.assertEqual(task_issues({"tasks": [task]}, self.now), ["no_task"])
        task.update(is_completed=False, entity_type="contacts")
        self.assertEqual(task_issues({"tasks": [task]}, self.now), ["no_task"])
        task.update(entity_type="leads")
        self.assertEqual(task_issues({"tasks": [task]}, self.now), ["overdue"])
        task["complete_till"] = AS_OF
        self.assertEqual(task_issues({"tasks": [task]}, self.now), [])

    def test_future_task_and_completed_overdue_task_do_not_flag_overdue(self):
        tasks = [{"is_completed": True, "complete_till": (self.now - timedelta(days=3)).isoformat()},
                 {"is_completed": False, "complete_till": (self.now + timedelta(days=1)).isoformat()}]
        self.assertEqual(task_issues({"tasks": tasks}, self.now), [])

    def test_old_untouched_open_deal_remains_in_all_snapshots(self):
        for days in (7, 14, 30):
            report = build_report(self.snapshot, days)
            old = next(deal for deal in report["deals"] if deal["id"] == 1001)
            self.assertIn("no_task", old["issues"])
            self.assertIn("stale", old["issues"])
            self.assertEqual(report["metrics"]["open_count"], 40)

    def test_half_open_ranges_and_old_created_won_deal(self):
        start = self.now - timedelta(days=30)
        base = deepcopy(self.snapshot["deals"][0])
        base.update(status="won", tasks=[], created_at=(start - timedelta(days=20)).isoformat(), closed_at=start.isoformat(), amount=250000)
        end = deepcopy(base)
        end.update(id=9002, closed_at=AS_OF, amount=999000)
        created = deepcopy(base)
        created.update(id=9003, status="new", closed_at=None, created_at=start.isoformat())
        self.snapshot.update(deals=[base, end, created], calls=[])
        result = build_report(self.snapshot, 30)
        self.assertEqual(result["metrics"]["won_count"], 1)
        self.assertEqual(result["metrics"]["won_amount"], 250000)
        self.assertEqual(result["metrics"]["new_leads"], 1)
        self.assertEqual(result["metrics"]["win_rate"], 100.0)

    def test_periods_are_genuinely_calculated_and_daily_totals_match(self):
        reports = [build_report(self.snapshot, days) for days in (7, 14, 30)]
        self.assertLess(reports[0]["metrics"]["calls_count"], reports[1]["metrics"]["calls_count"])
        self.assertLess(reports[1]["metrics"]["won_amount"], reports[2]["metrics"]["won_amount"])
        for report in reports:
            for key in ("won_amount", "calls_count", "new_leads"):
                self.assertEqual(sum(row[key] for row in report["series"]), report["metrics"][key])
            for key in ("won_count", "won_amount", "open_count", "overdue_count", "no_task_count", "calls_count"):
                self.assertEqual(sum(row[key] for row in report["manager_stats"]), report["metrics"][key])
            self.assertEqual(sum(stage["count"] for stage in report["pipeline"]), report["metrics"]["open_count"])

    def test_contract_required_fields_and_evidence(self):
        report = build_report(self.snapshot)
        required = {"meta", "managers", "metrics", "pipeline", "series", "manager_stats", "deals", "calls", "recommendations", "summary"}
        self.assertEqual(set(report), required)
        self.assertTrue({"as_of", "period_days", "from", "to", "mode", "analysis_mode", "warnings"} <= set(report["meta"]))
        self.assertTrue({"issues", "recommendation", "call_ids", "tasks", "crm_url"} <= set(report["deals"][0]))
        for call in report["calls"]:
            self.assertIsNone(call["audio_url"])
            for evidence in call["evidence"]:
                self.assertTrue(any(evidence["text"] in item["text"] and evidence["start"] == item["start"] for item in call["transcript"]))
        self.assertTrue(all(item["requires_approval"] for item in report["recommendations"]))

    def test_incomplete_snapshot_cannot_claim_no_tasks(self):
        self.snapshot["complete"] = False
        report = build_report(self.snapshot)
        self.assertEqual(report["metrics"]["no_task_count"], 0)
        self.assertFalse(any("no_task" in deal["issues"] for deal in report["deals"]))
        self.assertTrue(any("Неполная" in warning for warning in report["meta"]["warnings"]))

    def test_report_rebuilds_call_links_after_crm_refresh(self):
        raw = self.snapshot["calls"][0]
        target = next(deal for deal in self.snapshot["deals"] if deal["id"] == raw["deal_id"])
        target["call_ids"] = []
        target["last_activity_at"] = (self.now - timedelta(days=40)).isoformat()
        result = build_report(self.snapshot)
        deal = next(deal for deal in result["deals"] if deal["id"] == target["id"])
        self.assertIn(raw["id"], deal["call_ids"])
        self.assertEqual(parse_time(deal["last_activity_at"]), parse_time(raw["occurred_at"]))

    def test_model_next_step_is_compared_to_crm_tasks(self):
        raw = self.snapshot["calls"][0]
        raw.update(analysis_mode="openai", next_step="Отправить договор", evidence=[raw["transcript"][2]], summary="Real model result", objections=[])
        target = next(deal for deal in self.snapshot["deals"] if deal["id"] == raw["deal_id"])
        target["tasks"] = []
        call = next(call for call in build_report(self.snapshot)["calls"] if call["id"] == raw["id"])
        self.assertTrue(call["followup_gap"])
        self.assertEqual(call["quality"], "attention")
        self.assertEqual(call["summary"], "Real model result")
        target["tasks"] = [{"text": "Отправить договор", "is_completed": False, "complete_till": AS_OF}]
        call = next(call for call in build_report(self.snapshot)["calls"] if call["id"] == raw["id"])
        self.assertFalse(call["followup_gap"])

    def test_demo_deterministic_and_build_does_not_mutate_source(self):
        before = json.dumps(self.snapshot, sort_keys=True)
        first = build_report(self.snapshot)
        self.assertEqual(first, build_report(demo_snapshot()))
        self.assertEqual(before, json.dumps(self.snapshot, sort_keys=True))

    def test_no_live_snapshot_never_falls_back_to_demo(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "auditor.db")
            with self.assertRaises(AuditorError):
                snapshot_for("live", store)
            snapshot = snapshot_for("demo", store)
            snapshot["calls"][0].update(analysis_mode="openai", summary="Preserved paid extraction")
            store.save_snapshot("demo", snapshot)
            self.assertEqual(snapshot_for("demo", store)["calls"][0]["summary"], "Preserved paid extraction")
            report = build_report(snapshot)
            store.save_report("demo", 30, report)
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM transcripts").fetchone()[0], 28)
                self.assertEqual(db.execute("SELECT count(*) FROM reports").fetchone()[0], 1)

    def test_invalid_period_and_timezone_rejected(self):
        for days in (0, -1, 366, "30"):
            with self.assertRaises(AuditorError):
                build_report(self.snapshot, days)
        with self.assertRaises(AuditorError):
            parse_time("2026-10-14T18:00:00")


if __name__ == "__main__":
    unittest.main()
