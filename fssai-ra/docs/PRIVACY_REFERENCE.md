# Opt-in HTTP privacy reference profile

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Run `pytest tests/test_privacy_integration.py`, then see the same controls against a malicious model in the [conference package](../conference/README.md).

The default HTTP path remains `disclosure-only`. A server may construct
`PrivacyConfiguration` and pass it through
`create_app(..., disclosure_options={"privacy": configuration})`.
`GET /v1/disclosure` reports `tokenized-memory-reference` when it is active.

This is an executable reference seam, deliberately limited to the memory state
store until persistent vault/key custody and restoration are qualified. It does
not enable a production mode, change every existing deployment, or attest a
remote runtime's honesty.

The [pipeline lab](PIPELINE_WALKTHROUGH.md#5-run-the-protected-data-lab-and-inspect-every-stage) now demonstrates encrypted fields in SQLite/PostgreSQL. It is a separate one-process teaching adapter with ephemeral custody, not a persistent HTTP privacy profile.

## Configuration and enforcement

The server constructs one `KeyCustody`, grants minimal credentials to its record
source and token vault, creates an `EncryptedRecordSource`, and supplies a
nonempty mapping of declared identity fields to token types. The record source
and vault must share custody. A strict `ModelRegistry` holds approved signed
manifests. A server-owned `runtime_identity(endpoint)` provider returns the
artifact digest and model identity; no request body supplies this evidence.
Production replacement of that provider requires authenticated serving identity
and its own trust analysis.

The complete runnable configuration and adversarial cases are in
`tests/test_privacy_integration.py`; they use real AES-GCM, tokens, signed
manifests, FastAPI routes and a deterministic model, with synthetic records.

```bash
.venv/bin/python -m pytest tests/test_privacy_integration.py -vv
```

The path checks manifest purpose/classes/expiry/revocation before record access,
then uses the disclosure gate for holder, subject, field, purpose, consent and
zone decisions. Context values, known identifiers in task/evidence, and outputs
are tokenized. Model-task requests without governed context deny in this profile.
Unknown detected contact details in prompts/outputs require classification and
are refused. This is not comprehensive detection of unknown names or identifiers.

Output derivation requires an existing held session. Release checks the stored
output and recipient, and supports `restore_identity: true` only when entitled.
Unknown or out-of-scope restoration tokens deny. The final gate rechecks current
release authority after preparing restored content and before returning it.
Evidence records the digest of the bytes returned, not the plaintext identities.

## Known limits and next qualification gates

- Memory only: process loss discards the vault and custody. No persistent-state
  profile is silently accepted with ephemeral keys.
- Consent/revocation ordering is local to the reference store. Distributed
  freshness, network streaming and hardware key protection remain unqualified.
- Tokenization covers declared identifiers and supported contact patterns. It
  does not prevent re-identification through rare attributes, prior model
  knowledge, images or unrestricted user-supplied unknown identity text.
- The API authenticates an output holder and checks the requested recipient's
  policy category; actual delivery and recipient identity proof remain adapter
  obligations. It does not send a message or prove the caller delivered it.
- This joins the privacy components. It does not bind a consequential action's
  approval to trusted context receipts, qualify the notary/pack floor, or add a
  completed education privacy/correction workflow.
- Negative literal scans and rejected probe credentials are unverified evidence,
  not proof that a copy is erased. Restore journal checks cover recorded local
  history; a fresh process needs an independent current journal watermark.
