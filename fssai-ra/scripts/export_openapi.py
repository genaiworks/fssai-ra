"""Export the deterministic FastAPI schema for review and client generation."""
from pathlib import Path
import json

from fssaira import ApplicationProfile, ControlPlane
from fssaira.api import create_app

app = create_app(ControlPlane(ApplicationProfile.load("profiles/student_support.yaml")))
destination = Path("docs/openapi.json")
destination.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
print(destination)
