"""Record reviewer sensitivity without pooling it with the historical V31 grid.

Run from fssai-ra with --out <new-directory> and optionally --model <Ollama-tag>.
A saved manifest prevents resuming with changed model weights or harness code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import urllib.request
from pathlib import Path

from fssaira.injection_bench import ollama_agent, run, summarise, validate_grid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='qwen3:0.6b')
    parser.add_argument('--strict-only', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=10) as response:
        tags = json.load(response)
    with urllib.request.urlopen('http://127.0.0.1:11434/api/version', timeout=10) as response:
        version = json.load(response)
    model = next(m for m in tags['models'] if m['name'] == args.model)
    source = Path(__file__).resolve().parents[1] / 'src/fssaira/injection_bench.py'
    manifest = {
        'model': model, 'ollama': version,
        'platform': platform.platform(), 'python': platform.python_version(),
        'settings': {'temperature': 0, 'seed': 7, 'num_ctx': 8192, 'num_predict': 1024,
                     'think': False, 'max_turns': 10},
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'scope': 'Supplemental sensitivity run; not pooled with historical five-model grid',
    }
    manifest_path = args.out / 'manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise ValueError('Manifest changed; use a new output directory')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    modes = ('strict',) if args.strict_only else ('task-fields', 'strict')
    for mode in modes:
        configs = ('full',) if mode == 'strict' else ('none', 'full')
        results = run({f'ollama:{args.model}': ollama_agent(args.model, timeout=120)},
                      configs=configs, out=args.out / mode, review_mode=mode,
                      on_result=lambda row: print(row['config'], row['task'], row['goal'],
                                                  row['utility'], row['attack_success'],
                                                  row['error'], flush=True))
        validate_grid(results, configs=configs)
        (args.out / f'{mode}-summary.json').write_text(json.dumps(summarise(results), indent=2) + '\n')
    print('COMPLETE', flush=True)


if __name__ == '__main__':
    main()
