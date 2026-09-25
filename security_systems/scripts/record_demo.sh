#!/usr/bin/env bash
# Drives the terminal for the 4-minute proposal recording (docs/RECORDING_SCRIPT.md).
# Start your screen recorder, run this, and press Enter at each beat while you speak.
# Everything is offline and deterministic, so a retake shows the same output.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
TK=("$PY" -m trustkernel)

beat() {
  printf '\n\033[2m── press Enter: %s ──\033[0m' "$1"
  read -r _
  clear 2>/dev/null || true
  printf '\033[1;36m%s\033[0m\n\n' "$1"
}

beat "1  An agent pipeline with deploy rights"
"$PY" examples/guarded_agent_loop.py

beat "2  Borrowed authority: three dispatchers, ten hostile chains"
"${TK[@]}" delegation | head -3

beat "3  Replay with a forged approval"
"$PY" examples/replay_boundary.py

beat "4  'Denied' is not a test result"
"$PY" examples/effect_oracle.py | "$PY" -c '
import json, sys
names = {"reject_before_write": "rejects before writing", "write_then_reject": "writes, then says denied",
         "control_removed": "control removed", "legitimate_write": "legitimate deploy"}
for row in json.load(sys.stdin):
    print("%-26s refused=%-5s  harmful effect=%s" % (names[row["case"]], row["refused"], row["harmful_effect"]))'

beat "5  Prove the attacker can win"
"${TK[@]}" redteam --attempts 300 | tail -1
"${TK[@]}" redteam --attempts 300 --remove execution_mediator | tail -1

beat "6  Which controls can we delete?"
"${TK[@]}" ablate --only F11 --only F13

printf '\n\033[2m── end of recording ──\033[0m\n'
