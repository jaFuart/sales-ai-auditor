from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from auditor.ai import OpenAIAnalyzer
from auditor.amo import AmoClient, NoRedirect
from auditor.common import AuditorError
from auditor.demo import demo_snapshot
from auditor.telephony import import_calls, validate_segments
from auditor.report import build_report


class Response(io.BytesIO):
    def __init__(self, payload=None, status=200):
        super().__init__(json.dumps(payload).encode() if payload is not None else b"")
        self.status = status


class AmoTests(unittest.TestCase):
    def client(self, responses, retries=4):
        opener = Mock()
        opener.open.side_effect = responses
        return AmoClient("demo-account", "unit-test-token", opener=opener, sleep=Mock(), retries=retries)

    def test_204_means_empty_collection(self):
        client = self.client([Response(status=204)])
        self.assertEqual(client.list_all("/api/v4/leads", "leads"), [])
        request = client.opener.open.call_args[0][0]
        self.assertEqual(request.get_method(), "GET")
        self.assertTrue(request.full_url.startswith("https://demo-account.amocrm.ru/api/v4/leads?"))

    def test_pagination_uses_local_pages_and_deduplicates(self):
        client = self.client([Response({"_embedded": {"leads": [{"id": 1}, {"id": 2}]}, "_links": {"next": {"href": "https://evil.example/steal"}}}),
                              Response({"_embedded": {"leads": [{"id": 2}, {"id": 3}]}})])
        self.assertEqual(client.list_all("/api/v4/leads", "leads"), [{"id": 1}, {"id": 2}, {"id": 3}])
        requests = [call[0][0].full_url for call in client.opener.open.call_args_list]
        self.assertTrue(all(url.startswith(client.base) for url in requests))
        self.assertIn("page=2", requests[1])

    def test_full_last_page_is_followed_by_204(self):
        client = self.client([Response({"_embedded": {"tasks": [{"id": index} for index in range(250)]}}), Response(status=204)])
        self.assertEqual(len(client.list_all("/api/v4/tasks", "tasks")), 250)
        self.assertEqual(client.opener.open.call_count, 2)

    def test_retries_429_and_5xx_then_succeeds(self):
        errors = [HTTPError("https://example", 429, "contains-secret", {"Retry-After": "3"}, None),
                  HTTPError("https://example", 503, "contains-secret", {}, None), Response({"_embedded": {"tasks": []}})]
        client = self.client(errors)
        self.assertEqual(client.list_all("/api/v4/tasks", "tasks"), [])
        self.assertEqual(client.sleep.call_args_list[0][0][0], 3)
        self.assertEqual(client.sleep.call_args_list[1][0][0], 2)

    def test_errors_are_bounded_and_do_not_expose_credentials(self):
        for error in (HTTPError("https://example?secret=token", 401, "unit-test-token", {}, None), URLError("unit-test-token")):
            client = self.client([error] * 3, retries=2)
            with self.assertRaises(AuditorError) as result:
                client.list_all("/api/v4/leads", "leads")
            self.assertNotIn("unit-test-token", str(result.exception))
            self.assertLessEqual(client.opener.open.call_count, 3)

    def test_repeated_page_and_malformed_collection_fail_closed(self):
        payload = {"_embedded": {"leads": [{"id": 1}]}, "_links": {"next": {"href": "unused"}}}
        client = self.client([Response(payload), Response(payload)])
        with self.assertRaises(AuditorError):
            client.list_all("/api/v4/leads", "leads")
        client = self.client([Response({"_embedded": {}})])
        with self.assertRaises(AuditorError):
            client.list_all("/api/v4/leads", "leads")

    def test_subdomain_and_redirect_validation(self):
        for subdomain in ("https://a.amocrm.ru", "localhost:8080", "a/../../x", "a.amocrm.ru", "a@evil", "-a"):
            with self.assertRaises(AuditorError):
                AmoClient(subdomain, "unit-test-token")
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example"))

    def test_live_normalization_and_contact_tasks_excluded(self):
        client = self.client([])
        data = {
            "leads": [{"id": 123, "name": "CRM", "status_id": 17, "pipeline_id": 8, "price": 250000,
                       "responsible_user_id": 10, "created_at": 1700000000, "updated_at": 1750000000, "closed_at": None,
                       "_embedded": {"companies": [{"id": 77}]}}],
            "tasks": [{"id": 91, "entity_id": 123, "entity_type": "leads", "is_completed": False, "text": "Позвонить", "complete_till": 1760000000},
                      {"id": 92, "entity_id": 123, "entity_type": "contacts", "is_completed": False, "text": "Contact", "complete_till": 1760000000}],
            "users": [{"id": 10, "name": "Иван Тестов"}],
            "pipelines": [{"id": 8, "_embedded": {"statuses": [{"id": 17, "name": "Согласование"}]}}],
            "companies": [{"id": 77, "name": "Реальная компания"}],
        }
        client.list_all = lambda path, key: data[key]
        result = client.snapshot()
        self.assertEqual(result["mode"], "live")
        self.assertTrue(result["complete"])
        self.assertEqual(result["deals"][0]["company"], "Реальная компания")
        self.assertEqual(result["deals"][0]["status_label"], "Согласование")
        self.assertEqual(len(result["deals"][0]["tasks"]), 1)
        self.assertNotIn("unit-test-token", json.dumps(result))


class TelephonyTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = demo_snapshot()
        self.raw = deepcopy(self.snapshot["calls"][0])
        self.raw["id"] = 900001

    def import_payload(self, calls):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calls.json"
            path.write_text(json.dumps({"calls": calls}), encoding="utf-8")
            return import_calls(path, self.snapshot)

    def test_import_explicit_link_and_timestamp_validation(self):
        output = self.import_payload([self.raw])
        self.assertEqual(output[0]["analysis_mode"], "local_rules")
        self.assertFalse(output[0]["synthetic"])
        deal = next(deal for deal in self.snapshot["deals"] if deal["id"] == self.raw["deal_id"])
        self.assertIn(900001, deal["call_ids"])

    def test_calling_employee_may_differ_from_deal_owner_and_is_counted(self):
        self.raw["manager_id"] = 999
        output = self.import_payload([self.raw])
        self.snapshot["calls"].extend(output)
        report = build_report(self.snapshot)
        self.assertIn(999, {manager["id"] for manager in report["managers"]})
        employee = next(item for item in report["manager_stats"] if item["id"] == 999)
        self.assertEqual(employee["calls_count"], 1)
        self.assertEqual(employee["open_count"], 0)
        self.assertEqual(sum(item["calls_count"] for item in report["manager_stats"]), report["metrics"]["calls_count"])

    def test_unknown_deal_duplicate_and_bad_audio_url_rejected(self):
        self.raw["deal_id"] = 999999
        with self.assertRaises(AuditorError):
            self.import_payload([self.raw])
        self.raw["deal_id"] = self.snapshot["calls"][0]["deal_id"]
        with self.assertRaises(AuditorError):
            self.import_payload([self.raw, self.raw])
        self.raw["audio_url"] = "http://localhost/secrets"
        with self.assertRaises(AuditorError):
            self.import_payload([self.raw])

    def test_invalid_file_does_not_partially_mutate_snapshot(self):
        original = deepcopy(self.snapshot)
        invalid = deepcopy(self.raw)
        invalid["transcript"][0]["end"] = 10000
        with self.assertRaises(AuditorError):
            self.import_payload([self.raw, invalid])
        self.assertEqual(self.snapshot, original)


class AITests(unittest.TestCase):
    def setUp(self):
        self.call = demo_snapshot()["calls"][0]
        self.value = {"summary": "Клиент ждёт предложение", "objections": ["Цена"], "next_step": "Отправить предложение",
                      "evidence": [{"segment_index": 2, "quote": self.call["transcript"][2]["text"]}]}

    def client(self, value, status="completed"):
        opener = Mock()
        opener.open.return_value = Response({"status": status, "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]}]})
        return OpenAIAnalyzer("unit-test-key", opener=opener)

    def test_structured_response_is_validated_and_request_has_no_retention(self):
        client = self.client(self.value)
        value = client.analyze(self.call)
        self.assertEqual(value["analysis_mode"], "openai")
        self.assertEqual(value["evidence"][0]["text"], self.call["transcript"][2]["text"])
        request = client.opener.open.call_args[0][0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertNotIn("unit-test-key", request.data.decode())

    def test_hallucinated_evidence_and_unsupported_claims_rejected(self):
        self.value["evidence"][0]["quote"] = "Вымышленная цитата"
        with self.assertRaises(AuditorError):
            self.client(self.value).analyze(self.call)
        self.value["evidence"] = []
        with self.assertRaises(AuditorError):
            self.client(self.value).analyze(self.call)

    def test_incomplete_and_malformed_output_rejected(self):
        with self.assertRaises(AuditorError):
            self.client(self.value, status="incomplete").analyze(self.call)
        with self.assertRaises(AuditorError):
            self.client({"summary": "wrong schema"}).analyze(self.call)

    def test_missing_key_and_http_error_do_not_print_secrets(self):
        with self.assertRaises(AuditorError):
            OpenAIAnalyzer("")
        client = self.client(self.value)
        client.opener.open.side_effect = HTTPError("https://secret", 401, "unit-test-key", {}, None)
        with self.assertRaises(AuditorError) as result:
            client.analyze(self.call)
        self.assertNotIn("unit-test-key", str(result.exception))

    def test_real_asr_adapter_preserves_timestamps_without_inventing_speakers(self):
        opener = Mock()
        opener.open.return_value = Response({"duration": 14.5, "segments": [{"start": 0, "end": 14.5, "text": "Пример речи"}]})
        client = OpenAIAnalyzer("unit-test-key", opener=opener)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mp3"
            path.write_bytes(b"mock audio content")
            result = client.transcribe(path)
        self.assertEqual(result["transcript"][0]["end"], 14.5)
        self.assertEqual(result["transcript"][0]["speaker"], "Не определён")
        self.assertFalse(result["speaker_identification"])
        self.assertIn(b"whisper-1", opener.open.call_args[0][0].data)


if __name__ == "__main__":
    unittest.main()
