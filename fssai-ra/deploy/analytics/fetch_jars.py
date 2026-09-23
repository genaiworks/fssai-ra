"""Build-time-only download of the exact, checksum-locked analytics dependencies."""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

manifest, destination = map(Path, sys.argv[1:])
destination.mkdir(parents=True, exist_ok=True)
for artifact in json.loads(manifest.read_text()):
    with urllib.request.urlopen(artifact['url'], timeout=120) as response:
        data = response.read()
    if hashlib.sha512(data).hexdigest() != artifact['sha512']:
        raise RuntimeError('dependency checksum mismatch: ' + artifact['name'])
    (destination / artifact['name']).write_bytes(data)
    print('verified ' + artifact['name'])
