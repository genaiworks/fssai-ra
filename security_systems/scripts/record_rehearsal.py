"""Capture real command output and timings, then build an offline replay page.

This is an automated terminal rehearsal, not a recording of a human presenter.
"""
import html
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/rehearsal"
DEMOS = (
    ("Approval replay boundary", ["examples/replay_boundary.py"], 0),
    ("Denied after write", ["examples/effect_oracle.py"], 0),
    ("Workshop starter: expected failures", ["-m", "workshop.check", "--implementation", "starter"], 1),
    ("Workshop solution", ["-m", "workshop.check", "--implementation", "solution"], 0),
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    recordings = []
    for title, argv, expected in DEMOS:
        start = time.perf_counter()
        events = []
        with subprocess.Popen([sys.executable, "-u", *argv], cwd=ROOT, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as process:
            for line in process.stdout:
                events.append([round(time.perf_counter() - start, 6), "o", line])
            code = process.wait()
        recordings.append({"title": title, "command": "python " + " ".join(argv), "events": events,
                           "returncode": code, "expected_returncode": expected,
                           "seconds": round(time.perf_counter() - start, 6)})
    (OUT / "terminal.json").write_text(json.dumps(recordings, indent=2) + "\n")
    transcript = "\n\n".join(r["title"] + "\n$ " + r["command"] + "\n" +
                             "".join(e[2] for e in r["events"]) for r in recordings)
    (OUT / "transcript.txt").write_text(transcript)
    data = json.dumps(recordings).replace("<", "\\u003c")
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Trustkernel — reviewer demo</title>
<style>body{max-width:1000px;margin:40px auto;padding:0 20px;background:#111827;color:#e5e7eb;font:18px system-ui}
button,select{font:inherit;padding:10px;margin:5px;background:#e5e7eb;color:#111827;border:0;border-radius:5px}
pre{padding:20px;background:#030712;white-space:pre-wrap;overflow-wrap:anywhere;font:16px/1.5 monospace}
a{color:#93c5fd}p{line-height:1.6}h1{font-size:32px}</style>
<h1>Observe the effect. Challenge the control.</h1>
<p>Four recorded local command runs. Synthetic data, scripted requests, no model API.
This is an automated terminal capture, not a human talk recording. Read the full transcript below or replay a run.</p>
<label for="demo">Demonstration</label><select id="demo"></select>
<button id="play">Replay</button><button id="show">Show complete output</button>
<p id="meta"></p><pre id="terminal" aria-label="Recorded terminal output"></pre>
<details><summary>Full accessible transcript</summary><pre>TRANSCRIPT</pre></details>
<script>const demos=DATA; const select=document.getElementById('demo');
const terminal=document.getElementById('terminal');let timers=[];
demos.forEach((d,i)=>{const option=document.createElement('option');option.value=i;option.textContent=d.title;select.appendChild(option)});
function clear(){timers.forEach(clearTimeout);timers=[];terminal.textContent='';}
function display(full){clear();const d=demos[Number(select.value)];
document.getElementById('meta').textContent=d.command+' | recorded '+d.seconds+' seconds | exit '+d.returncode;
terminal.textContent='$ '+d.command+'\\n';
d.events.forEach(e=>{if(full){terminal.textContent+=e[2]}else{timers.push(setTimeout(()=>{terminal.textContent+=e[2]},e[0]*1000))}});}
document.getElementById('play').onclick=()=>display(false);document.getElementById('show').onclick=()=>display(true);
select.onchange=()=>display(true);display(true);</script></html>'''
    page = page.replace("TRANSCRIPT", html.escape(transcript)).replace("DATA", data)
    (OUT / "reviewer-demo.html").write_text(page)
    if any(r["returncode"] != r["expected_returncode"] for r in recordings):
        return 1
    print(f"Captured {len(recordings)} runs; all returned their expected status. {OUT / 'reviewer-demo.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
