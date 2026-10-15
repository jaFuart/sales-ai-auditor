"""Dependency-free CLI. Demo is the default; integrations always need a command."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit
from .common import AuditorError, dump_json
from .demo import demo_snapshot
from .report import build_report
from .store import Store

ROOT = Path(__file__).resolve().parents[1]


def snapshot_for(source, store):
    if source == "demo":
        try:
            return store.snapshot("demo")
        except AuditorError:
            pass
        value = demo_snapshot()
        store.save_snapshot("demo", value)
        return value
    return store.snapshot("live")


def parser():
    root = argparse.ArgumentParser(description="Sales AI Auditor — read-only CRM analytics")
    root.add_argument("--db", default=str(ROOT / "runtime/auditor.sqlite3"), help="Local SQLite path")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("build-demo", help="Export deterministic JSON fixtures for static hosting")
    report = commands.add_parser("report", help="Compute and export a report")
    report.add_argument("--days", type=int, default=30)
    report.add_argument("--source", choices=["demo", "live"], default="demo")
    report.add_argument("--output", default="runtime/report.json")
    serve = commands.add_parser("serve", help="Serve the dashboard and read-only report API")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--source", choices=["demo", "live"], default="demo")
    commands.add_parser("sync-amo", help="Read all amoCRM leads/tasks/users/pipelines into SQLite")
    calls = commands.add_parser("import-calls", help="Import normalized telephony JSON, no audio download")
    calls.add_argument("--input", required=True)
    analysis = commands.add_parser("analyze-calls", help="Run OpenAI structured analysis (uses API credits)")
    analysis.add_argument("--source", choices=["demo", "live"], default="live")
    analysis.add_argument("--limit", type=int, default=10)
    transcribe = commands.add_parser("transcribe", help="Send a LOCAL audio file to OpenAI (uses API credits)")
    transcribe.add_argument("--audio", required=True)
    transcribe.add_argument("--output", default="runtime/transcript.json")
    return root


class Handler(SimpleHTTPRequestHandler):
    report_source = "demo"
    db_path = None

    def _json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path)
        if path.path == "/api/health":
            return self._json(200, {"status": "ok", "mode": self.report_source, "read_only": True})
        if path.path == "/api/report":
            try:
                query = parse_qs(path.query)
                days = int(query.get("days", ["30"])[0])
                if days not in (7, 14, 30):
                    return self._json(400, {"error": "Choose days=7, 14 or 30."})
                store = Store(self.db_path)
                report = build_report(snapshot_for(self.report_source, store), days)
                store.save_report(self.report_source, days, report)
                return self._json(200, report)
            except (ValueError, AuditorError):
                return self._json(400, {"error": "Cannot build report; check the selected source and period."})
            except Exception:
                return self._json(500, {"error": "Report unavailable; inspect local source data."})
        if path.path.startswith("/api/"):
            return self._json(404, {"error": "Unknown read-only API endpoint."})
        return super().do_GET()

    def log_message(self, format, *args):
        # Never log URLs/query strings, which can contain accidentally pasted tokens.
        sys.stderr.write("HTTP request completed\n")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        store = Store(args.db)
        if args.command == "build-demo":
            snapshot = demo_snapshot()
            store.save_snapshot("demo", snapshot)
            for days in (7, 14, 30):
                report = build_report(snapshot, days)
                store.save_report("demo", days, report)
                dump_json(ROOT / f"dist/data/report-{days}.json", report)
            print("Built dist/data/report-{7,14,30}.json from a fixed synthetic snapshot.")
        elif args.command == "report":
            report = build_report(snapshot_for(args.source, store), args.days)
            store.save_report(args.source, args.days, report)
            dump_json(args.output, report)
            print(f"Saved {args.source} report: {args.output}")
        elif args.command == "serve":
            # Fail before binding a socket when the live source is absent.
            snapshot_for(args.source, store)
            handler = type("ReportHandler", (Handler,), {"report_source": args.source, "db_path": args.db})
            server = ThreadingHTTPServer((args.host, args.port), partial(handler, directory=str(ROOT / "dist")))
            print(f"Dashboard: http://{args.host}:{args.port} · source={args.source}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        elif args.command == "sync-amo":
            from .amo import AmoClient
            snapshot = AmoClient.from_env().snapshot()
            # Preserve imported calls when refreshing CRM; this command never requests telephony.
            try:
                snapshot["calls"] = store.snapshot("live")["calls"]
            except AuditorError:
                pass
            store.save_snapshot("live", snapshot)
            print(f"Stored {len(snapshot['deals'])} CRM deals. No CRM records changed.")
        elif args.command == "import-calls":
            from .telephony import import_calls
            snapshot = store.snapshot("live")
            imported = import_calls(args.input, snapshot)
            merged = {str(call["id"]): call for call in snapshot["calls"]}
            merged.update({str(call["id"]): call for call in imported})
            snapshot["calls"] = list(merged.values())
            store.save_snapshot("live", snapshot)
            print(f"Imported {len(imported)} calls. Audio URLs were not fetched.")
        elif args.command == "analyze-calls":
            from .ai import OpenAIAnalyzer
            if not 1 <= args.limit <= 100:
                raise AuditorError("Choose --limit between 1 and 100 calls.")
            snapshot = snapshot_for(args.source, store)
            client = OpenAIAnalyzer.from_env()
            selected = snapshot["calls"][:args.limit]
            for call in selected:
                call.update(client.analyze(call))
            store.save_snapshot(args.source, snapshot)
            print(f"Stored structured model analysis for {len(selected)} calls.")
        elif args.command == "transcribe":
            from .ai import OpenAIAnalyzer
            output = OpenAIAnalyzer.from_env().transcribe(args.audio)
            dump_json(args.output, output)
            print(f"Saved real ASR output: {args.output}")
    except AuditorError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print("Error: invalid or unavailable local input; check file format and permissions.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
