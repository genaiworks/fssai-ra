"""The educational attack lab: pick an attack, switch a control off, watch the harm return.

    python scripts/conference_lab.py                  # http://127.0.0.1:8765
    python scripts/conference_lab.py --export PATH    # a recorded, offline copy of every run

Standard library only, bound to 127.0.0.1. Every run the page shows is executed by this
process against a fresh education world; the page never fabricates an outcome. The
``--export`` copy embeds results recorded from real runs and says so on screen.

Removing a control is a *laboratory* capability. It exists so students can see that a
control is load-bearing; no deployment path in the kernel exposes it.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira.education_models import HonestAssistant, MaliciousAssistant  # noqa: E402
from fssaira.education_world import ALL_CONTROLS, MEDIATOR_OF, EducationWorld  # noqa: E402
from fssaira.falsification import FALSIFIERS, falsifier  # noqa: E402
from fssaira.governed_request import explain, run_governed_request  # noqa: E402

PAGE = ROOT / "conference" / "education" / "lab.html"
EVIDENCE = ROOT / "conference" / "evidence"


def catalogue() -> list[dict]:
    return [{"id": f.id, "name": f.name, "property": f.property, "rule": f.rule,
             "controls": [{"name": c, "mediator": MEDIATOR_OF.get(c, c)} for c in f.controls],
             "joint": list(f.joint)} for f in FALSIFIERS]


def run_attack(identifier: str, disabled: list[str]) -> dict:
    item = falsifier(identifier)
    unknown = sorted(set(disabled) - set(ALL_CONTROLS))
    if unknown:
        raise ValueError(f"unknown controls: {unknown}")
    world = EducationWorld([c for c in ALL_CONTROLS if c not in disabled])
    started = time.perf_counter()
    attempts = item.run(world)
    violated = any(a.violated for a in attempts)
    return {"falsifier": item.id, "name": item.name, "property": item.property, "disabled": disabled,
            "violated": violated, "attempts": [a.to_dict() for a in attempts],
            "decisions": world.observed.mediator_decisions[-12:],
            "ledger_records": len(world.ledger), "evidence_intact": world.evidence_intact()[0],
            "milliseconds": round((time.perf_counter() - started) * 1000, 1)}


def run_trace(model: str) -> dict:
    trace = run_governed_request(EducationWorld(), model=MaliciousAssistant() if model == "malicious"
                                 else HonestAssistant())
    body = trace.to_dict()
    for step in body["steps"]:
        step["evidence"] = {k: v for k, v in step["evidence"].items() if k not in ("checkpoint", "receipt")}
    return {**body, "system_literacy": explain(trace)}


def scorecard() -> dict:
    path = EVIDENCE / "summary.json"
    return json.loads(path.read_text()) if path.exists() else {"figures": {}, "note": "run make conference"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, kind: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # quieter console for a live demo
        sys.stderr.write(f"  lab {self.command} {self.path}\n")

    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = parse_qs(url.query)
        try:
            if url.path in ("/", "/index.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif url.path == "/api/catalogue":
                self._send(200, json.dumps({"falsifiers": catalogue(), "live": True}).encode())
            elif url.path == "/api/run":
                disabled = [c for c in query.get("disable", []) if c]
                self._send(200, json.dumps(run_attack(query["falsifier"][0], disabled), default=str).encode())
            elif url.path == "/api/trace":
                self._send(200, json.dumps(run_trace(query.get("model", ["honest"])[0]), default=str).encode())
            elif url.path == "/api/scorecard":
                self._send(200, json.dumps(scorecard()).encode())
            else:
                self._send(404, b'{"error": "not found"}')
        except (KeyError, ValueError) as exc:
            self._send(400, json.dumps({"error": str(exc)}).encode())


def export(path: Path) -> None:
    recorded = {"catalogue": catalogue(), "runs": {}, "traces": {}, "scorecard": scorecard(),
                "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    for item in FALSIFIERS:
        recorded["runs"][f"{item.id}|"] = run_attack(item.id, [])
        for control in item.controls:
            recorded["runs"][f"{item.id}|{control}"] = run_attack(item.id, [control])
    for model in ("honest", "malicious"):
        recorded["traces"][model] = run_trace(model)
    html = PAGE.read_text(encoding="utf-8").replace(
        "/*RECORDED*/null", json.dumps(recorded, default=str).replace("</", "<\\/"))
    path.write_text(html, encoding="utf-8")
    print(f"wrote recorded lab to {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    if args.export:
        export(args.export)
        return 0
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Trust by Construction attack lab: http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
