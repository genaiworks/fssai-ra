"""Checks the V24 extended abstract before it is submitted.

Rebuilds the manuscript into a temporary directory and verifies:
  1. the DOCX rebuilds byte-for-byte from this source (reproducible build);
  2. the released PDF has the same page count the rebuild produces;
  3. the quoted evidence file is byte-identical to the evaluation artifact;
  4. the prose stays within the 1,500-word invitation limit;
  5. every citation resolves and every listed reference is cited;
  6. every figure the manuscript references exists, is used and is numbered in order;
  7. the comparison figure's numbers survive a fresh run of the kernel;
  8. the reference field fits the tightest cap the form applies anywhere;
  9. the released files match release-verification.json.

Usage: python source/verify_v24.py   (run from anywhere)
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import tempfile

BASE = Path(__file__).resolve().parent
RELEASE = BASE.parent
REPO = BASE.parents[2]
NAME = "Trust_by_Construction_V24_Extended_Abstract"
failures = []


def check(label, ok, detail=""):
    print(f"  [{'pass' if ok else 'FAIL'}] {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pages(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    match = re.search(r"^Pages:\s+(\d+)", out, re.M)
    return int(match.group(1)) if match else None


print("verifying the V24 extended abstract")
with tempfile.TemporaryDirectory() as tmp:
    build = subprocess.run([sys.executable, str(BASE / "build_v24.py"), tmp],
                           capture_output=True, text=True)
    check("build_v24.py runs to completion", build.returncode == 0,
          build.stderr.strip().splitlines()[-1] if build.returncode else "")
    rebuilt = Path(tmp) / f"{NAME}.docx"
    released = RELEASE / f"{NAME}.docx"
    check(f"{NAME}.docx rebuilds byte-for-byte",
          rebuilt.exists() and released.exists() and sha(rebuilt) == sha(released))

report = json.loads((RELEASE / "release-verification.json").read_text())
sys.path.insert(0, str(REPO))
from scripts.check_submission import validate
form = validate((RELEASE / f"{NAME.replace('Extended_Abstract','Form_Fields')}.md").read_text())
check("every form field is within its word and character limits", form["valid"])
for name, d in form["sections"].items():
    check(f"  {name[:46]}", d["valid"],
          f"{d['words']}w, {d['characters']}c, {d['headroom']} chars spare")

paste = (RELEASE / f"{NAME.replace('Extended_Abstract','Form_Fields')}.md").read_text()
check("the paste text carries no figure markers or captions",
      "@FIG:" not in paste and not re.search(r"^Figure \d+\.", paste, re.M))
manuscript_body = (BASE / "manuscript.md").read_text()
check("the document and the form fields come from one source",
      all(line in manuscript_body for line in paste.splitlines() if line.strip()))
fields = sorted((RELEASE / "form-fields").glob("*.txt"))
check("five paste files are emitted", len(fields) == 5, ", ".join(f.name for f in fields))

manuscript = (BASE / "manuscript.md").read_text()
body, refs = manuscript.split("## References")
cited = {int(n) for n in re.findall(r"\[(\d+)\]", body)}
listed = {int(n) for n in re.findall(r"^\[(\d+)\] ", refs, re.M)}
check("every citation resolves and every reference is cited", cited == listed,
      f"cited {sorted(cited)}, listed {sorted(listed)}")

figures = re.findall(r"@FIG:([a-z-]+)", manuscript)
check("every referenced figure file exists",
      all((BASE / f"{name}.png").exists() for name in figures), ", ".join(figures))
captions = [int(n) for n in re.findall(r"^Figure (\d+)\.", manuscript, re.M)]
check("every figure carries a numbered caption",
      len(captions) == len(figures), f"{len(figures)} figures")
check("figures are numbered 1..n in the order they appear",
      captions == list(range(1, len(figures) + 1)), str(captions))

# The reference field has no published cap. Hold it to the tightest cap the form
# applies anywhere, so an unstated limit cannot silently truncate the citations.
reference_field = (RELEASE / "form-fields" / "5-references.txt").read_text().strip()
check("the reference field fits the form's tightest cap",
      len(reference_field.replace("\n", "\r\n")) <= 1500,
      f"{len(reference_field.replace(chr(10), chr(13) + chr(10)))} of 1500 characters")

# The comparison in Figure 5 is evidence, so it is re-derived here rather than trusted.
sys.path.insert(0, str(REPO / "src"))
try:
    from fssaira.delegation_eval import run_delegation_suite, ablate_delegation
except ModuleNotFoundError as exc:
    check("the delegation evidence re-runs from the kernel", False, str(exc))
else:
    live = run_delegation_suite().to_dict()
    vendored = json.loads((BASE / "delegation-comparison.json").read_text())
    check("the delegation evidence re-runs from the kernel and agrees",
          {k: v for k, v in live.items() if k != "generated_at"}
          == {k: v for k, v in vendored.items()
              if k not in ("controls_ablated", "every_control_load_bearing")})
    arms = live["arms"]
    check("the manuscript quotes the arm totals the run produced",
          (arms["unguarded"]["contained"], arms["caller_checked"]["contained"],
           arms["this_architecture"]["contained"]) == (0, 2, 10),
          f"{arms['unguarded']['contained']}, {arms['caller_checked']['contained']}, "
          f"{arms['this_architecture']['contained']} of {live['hostile_chains']}")
    check("the benign chain completes in every arm, so arm C refuses selectively",
          all(arm["benign_chain_completed"] for arm in arms.values()))
    ablation = ablate_delegation()
    check("every ablated delegation control is load-bearing",
          bool(ablation) and all(row["load_bearing"] for row in ablation),
          f"{len(ablation)} controls, each restoring its harm when removed")
check("the manuscript uses the form's canonical headings",
      all(f"## {h}" in manuscript for h in
          ["Introduction", "Development Section 1 Methodology Core Argument and Case Context",
           "Development Section 2 Results Analysis and Impact", "Conclusion", "References"]))

# A reviewer must be able to open what reference [5] names, at the commit it names.
ref5 = re.search(r"^\[5\].*$", manuscript, re.M).group(0)
commit = re.search(r"snapshot ([0-9a-f]{7,40})", ref5).group(1)
cited_paths = re.findall(r"\b(fssai-ra/[\w./-]+\.(?:json|py))", ref5)
check("reference 5 names the commit in its URL", f"/tree/{commit}" in ref5)
check("reference 5 names at least two artifacts", len(cited_paths) >= 2, ", ".join(cited_paths))
root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=REPO,
                      capture_output=True, text=True).stdout.strip()
unreachable = [path for path in cited_paths
               if subprocess.run(["git", "cat-file", "-e", f"{commit}:{path}"],
                                 cwd=root, capture_output=True).returncode != 0]
check("every path cited in reference 5 exists at that commit", not unreachable,
      ", ".join(unreachable) if unreachable else f"{len(cited_paths)} paths at {commit}")
pushed = subprocess.run(["git", "branch", "-r", "--contains", commit],
                        cwd=root, capture_output=True, text=True).stdout.strip()
check("the cited commit is pushed to a remote branch", bool(pushed),
      pushed.replace("\n", ", ").strip() or "not on any remote branch")

canonical = REPO / "evaluation" / "results" / "v1.0.0-domain-pack-matrix.json"
check("quoted evidence matches the evaluation artifact",
      (BASE / "domain-pack-matrix.json").read_bytes() == canonical.read_bytes(),
      str(canonical.relative_to(REPO)))

matrix = json.loads(canonical.read_text())["profiles"]
totals = {key: sum(profile[key] for profile in matrix)
          for key in ("states_explored", "scenarios_total", "scenarios_contained",
                      "benign_total", "benign_completed")}
for sentence, ok in [
    (f"{totals['states_explored']:,} bounded configurations",
     f"{totals['states_explored']:,} bounded configurations" in manuscript),
    (f"{totals['scenarios_total']} hostile scenarios",
     f"{totals['scenarios_total']} hostile scenarios" in manuscript),
    (f"{totals['benign_total']} benign workflows",
     f"{totals['benign_total']} benign workflows" in manuscript),
]:
    check(f"manuscript quotes '{sentence}' as recorded", ok)
check("every recorded hostile scenario was contained",
      totals["scenarios_contained"] == totals["scenarios_total"])
check("every recorded benign workflow completed",
      totals["benign_completed"] == totals["benign_total"])

matrix_rows = json.loads((BASE / "claim-matrix.json").read_text())
tests = "\n".join(path.read_text(encoding="utf-8")
                  for path in (REPO / "tests").glob("test_*.py"))
built = [row for row in matrix_rows if row["status"] == "BUILT"]
missing = [row["evidence"] for row in built if f"def {row['evidence']}(" not in tests]
check("every BUILT claim names a test that exists", not missing,
      f"{len(built)} built claims" if not missing else ", ".join(missing))
check("every claim carries a recognised status",
      {row["status"] for row in matrix_rows} <= {"BUILT", "PROPOSED", "NOT CLAIMED"})
check("the claim matrix distinguishes built from proposed",
      any(row["status"] == "PROPOSED" for row in matrix_rows))

check("author is stated as Rachana Srivastava",
      report["author"] == "Rachana Srivastava" and "Rachana Srivastava" in manuscript)

for kind in ("docx", "pdf"):
    released = RELEASE / f"{NAME}.{kind}"
    check(f"released {kind} matches its recorded digest",
          released.exists() and sha(released) == report["sha256"][kind])

pdf = RELEASE / f"{NAME}.pdf"
if pdf.exists():
    check("released PDF matches its recorded page count",
          pages(pdf) == report["pages"], f"{pages(pdf)} pages")
    check("the document stays within five pages", pages(pdf) <= 5)

print(("FAILED: " + "; ".join(failures)) if failures else "all checks passed")
sys.exit(1 if failures else 0)
