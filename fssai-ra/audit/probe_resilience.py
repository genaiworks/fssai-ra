import json
from pathlib import Path

from fssaira.profiles import ApplicationProfile
from fssaira.resilience import run_resilience

if __name__ == '__main__':
    old = json.loads(Path('evaluation/results/resilience-student-support.json').read_text())
    new = json.loads(json.dumps(run_resilience(ApplicationProfile.load('profiles/student_support.yaml')).to_dict()))
    Path('audit/resilience-fresh.json').write_text(json.dumps(new, indent=2))
    print(json.dumps({'passed': new['passed'], 'changed_top_level_fields': [k for k in new if old.get(k) != new[k]]}, indent=2))
