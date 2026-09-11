# Five minute demonstration

This walkthrough uses synthetic records, in-memory services, and no network calls.
It demonstrates authority containment, not production security.

## Run

```bash
git clone https://github.com/genaiworks/fssai-ra.git
cd fssai-ra/fssai-ra
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
python examples/demo_student_support.py
```

Release `v0.4.0` should report `32 passed` before the demonstration starts.

## Narrate the boundary

1. A synthetic document contains a recognizable malicious instruction. The import
   specimen removes that line, but the remaining text is still untrusted evidence.
2. The student-support agent may read its assigned case and prepare a recommendation.
3. The agent cannot approve an award because it lacks both the tool grant and the
   institutional authority.
4. A separate officer creates an authenticated approval for the canonical digest of
   one proposal for case S-104. The executor accepts only its trusted teaching key.
5. Changing the proposed status after review produces
   `APPROVAL_PAYLOAD_MISMATCH`, with zero register mutations.
6. Executing the unchanged proposal creates intent and outcome evidence. Retrying
   returns the same receipt, leaves the mutation count at one, and does not append
   duplicate intent or outcome records.
7. Both evidence ledgers verify their hash linkage, and the machine-readable control
   contract loads across all five domains.

## Ask the audience

For the next consequential agent capability in your institution:

- Which component independently checks the actual operation?
- What precise action must it refuse in a failure test?
- Which evidence would let an affected person challenge the outcome?
- Who keeps the service available and reconciles decisions when automation stops?

## Do not claim

Do not call the recognizable-line filter a general prompt-injection defense. Do not
describe the simulated diode as hardware. Do not imply that a hash chain prevents a
privileged insider from replacing an entire unchecked history. Do not equate thirty-two
passing deterministic tests with a benchmark, audit, or certification.
