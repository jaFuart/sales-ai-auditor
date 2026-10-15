"""Exercise the HTTP boundary with a real local socket and a temporary database."""
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from auditor.__main__ import Handler


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        root = Path(cls.directory.name)
        (root / "index.html").write_text("<title>Dashboard test</title>", encoding="utf-8")
        handler = type("TestHandler", (Handler,), {"report_source": "demo", "db_path": str(root / "auditor.sqlite3"),
                                                    "log_message": lambda *args: None})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(handler, directory=str(root)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.directory.cleanup()

    def get(self, path):
        with urlopen(self.base + path, timeout=5) as response:
            return response.status, response.headers, response.read()

    def test_dashboard_health_and_report(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Dashboard test", body)
        status, headers, body = self.get("/api/health")
        self.assertEqual(json.loads(body), {"status": "ok", "mode": "demo", "read_only": True})
        status, headers, body = self.get("/api/report?days=7")
        report = json.loads(body)
        self.assertEqual(report["meta"]["period_days"], 7)
        self.assertEqual(report["meta"]["mode"], "demo")
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_bad_period_and_unknown_endpoint_have_json_errors(self):
        for path, status in (("/api/report?days=99", 400), ("/api/report?days=bad", 400), ("/api/unknown", 404)):
            with self.assertRaises(HTTPError) as result:
                self.get(path)
            self.assertEqual(result.exception.code, status)
            self.assertIn("error", json.loads(result.exception.read()))


if __name__ == "__main__":
    unittest.main()
