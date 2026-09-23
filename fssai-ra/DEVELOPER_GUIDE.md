# Build and test bounded agent integrations

Start with the [full data-pipeline walkthrough](docs/PIPELINE_WALKTHROUGH.md) for sample data, actual storage shapes, cryptography, tool handoffs and runnable verification.


Start here for reusable integration development. See the [user guide](docs/USER_GUIDE.md), [feature catalogue](docs/FEATURES.md), and [research workflow](docs/RESEARCH_GUIDE.md). The repository is a reference implementation with executable
failure cases. It is useful for developing control-plane adapters and teaching
agent security; passing its tests is not production certification.

## Run in ten minutes

From `fssai-ra/`, using Python 3.10 or later:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,privacy,api]'
make developer-demo PYTHON=.venv/bin/python
.venv/bin/python -m pytest tests/test_qualified_transport.py tests/test_remote_effects.py tests/test_developer_security_demo.py
```

Dependency installation needs package access. The developer demo and tests use
synthetic data and local services; they need no model account or API key.
The demo prints `exact_artifact_bytes: true`, rejects a digest mismatch, and
shows `UNCERTAIN → UNCERTAIN → CONFIRMED` with exactly one provider submission.
The broader `make all` target checks public code, evidence, and host qualification without private manuscripts; see [validation tiers](docs/COMMANDS.md#validation-tiers). Host qualification should report `reference` on a developer machine. Do not turn missing isolation evidence into success to pass a gate.

## Choose an integration boundary

| Real problem | Entry point | What the developer must supply |
| --- | --- | --- |
| Agent reaches records or tools outside its task | `fssaira.tbc.TrustRuntime` and `SDKClient` | Trusted task contract, identity, isolated control service and authenticated transport |
| Poisoned memory survives an agent restart | Runtime source invalidation and lineage | Reliable source bindings and explicit recovery authority |
| Tool server changes descriptions after approval | `fssaira.integration.tool_servers` | Independently approved server identity and tool definitions |
| Trusted HTTPS peer serves changed content | `QualifiedTransport.fetch_artifact` | Destination policy, key pins and a digest approved independently of model/peer |
| Lost reply could cause duplicate remote actions | `EffectLedger` | Authenticated provider adapter and authoritative idempotency lookup |
| AI monitor falsely approves unsafe behavior | Runtime monitor interface | Separate monitor identity; its finding can only restrict authority |
| Evaluation overstates production readiness | Isolation probes and promotion gate | Actual deployment measurements and independent evidence custody |

The Python objects and SQLite databases are trusted service components. Do not
hand these objects, database paths, signing material or approval tokens to model
code. Expose only the authenticated model-facing dispatch boundary. These
modules do not install an OS sandbox or prevent a process opening another socket.

## Fetch independently approved bytes

```python
from fssaira.integration.network import DestinationPolicy
from fssaira.integration.transport import QualifiedTransport, TransportQualification

# Obtain all three from trusted deployment configuration and approval records.
policy = DestinationPolicy('assets.example.org', ('/approved/',), max_bytes=65536)
terms = TransportQualification(spki_pins=frozenset({approved_peer_spki_pin}))
client = QualifiedTransport(policy, terms)
artifact = client.fetch_artifact(
    approved_url, approved_public_ip_addresses,
    expected_sha256=approved_content_sha256,
    classifications=frozenset(),
)
consume(artifact.body)
record_evidence(artifact.evidence.to_dict())
```

This is an integration fragment: `approved_*`, `consume` and `record_evidence`
come from your control service. The complete runnable example is
`scripts/developer_security_demo.py`. Never accept the expected digest from the
same untrusted response it is intended to verify. Treat returned content as
untrusted data even when its identity is correct.

The adapter rejects redirects; submit any new destination through authorization
again. It does not resolve DNS internally, attach model-supplied headers, send
cookies or upload bodies. Classifications must come from trusted lineage, not a
model assertion. An arbitrary allowed URL path can encode a secret: approve
paths independently or use a catalogue of exact resources when confidentiality
matters. `fetch()` retains its evidence-only API; `fetch_artifact()` returns bytes
only after digest verification. Concurrent calls keep separate response buffers.

## Map provider responses conservatively

`EffectLedger.submit` accepts an acknowledgement shaped as
`{'status': 'applied', ...}` only when the provider confirms execution. A mere
accepted/queued response remains uncertain. `lookup(key)` returns one of:

- `{'status': 'applied', 'result': {...}}` for a confirmed effect;
- `{'status': 'absent'}` only for authoritative, terminal non-execution;
- `None`, `{'status': 'pending'}` or another nonfinal answer when uncertain.

An eventually consistent 404 is not authoritative absence. Never map it to
`absent`. Pending and malformed replies keep dependent work blocked. Derive the
key with `idempotency_key` from the approved decision; the ledger rejects reuse
for a different operation or payload. Call `require_settled` before dependent
work and reconcile by key after a lost reply. Provider credentials and approval
checks belong outside the model. This ledger does not itself verify an approval.

## Reproduce the failure cases

```sh
.venv/bin/python -m pytest tests/test_qualified_transport.py tests/test_remote_effects.py
.venv/bin/python -m pytest tests/test_developer_security_demo.py
```

Run the public architecture bindings with `.venv/bin/python scripts/verify_architecture.py`; fresh results go to `work/architecture/`. Private manuscript drift checks are separate: `make manuscript-check PYTHON=.venv/bin/python` requires the historical archive.

Transport tests use real loopback TLS handshakes and fresh test certificates.
Monitor tests use scripted findings, not a live-model accuracy experiment. Test
counts, adversarial episodes and numeric result checks are different units.
Report them separately. The historical v14 manuscript and evidence bindings are in
`paper/tbc-v14/`; v13 is preserved. See `SECURITY_REVIEW.md` for remaining
acceptance requirements, and do not infer that all 109 architecture controls are
fully implemented from the number of passing tests.

## Historical v14 release figures

The v14 figure workflow expects PNG and SVG assets in `paper/tbc-v14/figures/`. Those local archive inputs are not all distributed in a fresh checkout; this section applies only when that archive is available.
Figure 6 reads the architecture-comparison and domain-pack result JSON directly;
its manifest records the input hashes, counts and rendered asset hashes. The
paper builder and release checker reject stale or altered figure assets.
Verification uses the standard library:

```sh
python scripts/build_release_figures.py --check
```

To deliberately regenerate them, install Matplotlib in a separate environment
and run `python scripts/build_release_figures.py`. Then rebuild the paper with
`python scripts/build_paper_v14.py`, review the rendered pages, and update the
reviewed paper hash in `paper/tbc-v14/implementation.json`. Rendering can vary
between Matplotlib versions; the Word build embeds the exact committed PNGs.
The two experiments have different fixtures and denominators and must not be
pooled or described as field security or live-model detector accuracy.
