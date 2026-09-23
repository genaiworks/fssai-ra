"""Execute capability contracts and persist their source-bound evidence."""
import argparse
import json
from pathlib import Path

from check_architecture import check

from fssaira.kernel.contracts import execute_contracts, load_contracts

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "work/architecture")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    traceability = check(ROOT)
    contracts = load_contracts(ROOT / 'contract/capabilities/architecture.yaml', ROOT)
    evidence = execute_contracts(contracts, ROOT, args.output)
    result = {'traceability': traceability, 'executed_contracts': evidence,
              'qualification': 'local-reference; independent operational attestation not established'}
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': evidence['passed'], 'claims': evidence['counts'],
                      'traceability': traceability}, indent=2))
    return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
