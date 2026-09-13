# FSSAI RA Extensible Platform Guide

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Continue the engineering route → [`SECURITY.md`](SECURITY.md)

## What this platform provides

FSSAI-RA is a reference platform for institutions that want AI assistance without
giving a model unchecked institutional authority. The base framework supplies a
working control plane, a low-side import gateway, durable state adapters, event
transport, reproducible data jobs, evidence recording, recovery behavior, tests,
and domain profiles. An adopter changes the application profile and backend
configuration while preserving the observable control contract.

The repository offers two modes:

- **Teaching mode** uses Python memory stores and runs on a laptop with no service
  dependencies. It demonstrates rules and failure behavior.
- **Distributed reference mode** adds FastAPI, Redis, Apache Kafka, PySpark, Apache
  Iceberg, and S3-compatible object storage. It is a starting point for engineering
  and evaluation, not a production certification.

## Reference topology

```text
LOW SIDE / EXTERNAL                 PROTECTED DATA PLANE

documents and updates
          |
          v
  import-gateway :8081  ---- inward event ---->  Apache Kafka
  type size provenance       boundary seam          |
  HMAC quarantine + durable low-side audit          +--> PySpark validation
  no read-back route                               |        |
                                                    |        v
CONTROL PLANE                                      |   Apache Iceberg
                                                    |   snapshots and history
client -> FastAPI :8080 -> PostgreSQL               |
          |                case + evidence in one   +--> controlled consumers
          |                transaction
          |              -> Redis (alternative
          |                best-effort adapter)
          v                pending outcomes
 exact-action executor
          |
          +--> hash-chained evidence
          +--> Kafka lifecycle events
```

The Compose networks reduce accidental connectivity. They are not a physical data
diode or cross-domain solution. See `DIODE_DEPLOYMENT.md` before making a physical
directionality claim.

## Five minute teaching mode

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
uvicorn fssaira.api:create_default_app --factory --port 8080
```

Open `http://127.0.0.1:8080/docs` for the generated API interface. Health output
lists configuration warnings so a memory deployment cannot silently appear to be
production-ready.

## Distributed reference mode

Requirements are Docker with Compose v2 and at least 8 GB of memory for the
analytics profile.

```bash
python3 scripts/bootstrap_dev_env.py
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d \
  redis kafka control-api import-gateway
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8081/health
```

The generated `deploy/.env` is ignored by Git and contains random local credentials,
including distinct bearer tokens for the operator, proposer, and two reviewing officers.
Do not promote it. An institutional deployment should obtain secrets from its key
management service, authenticate callers through an OIDC or workload-identity
gateway, enable authenticated and encrypted Kafka listeners, and operate Redis with
an approved persistence and high-availability design.

The console's header accepts a pasted bearer token and keeps it only for the
browser session. The four named choices are published teaching tokens and will
correctly fail against a generated distributed-stack configuration.

### Exercise the exact-action API

The checked-in `.env.example` uses the readable placeholders below. If you ran
`make dev-env`, use the corresponding random token key from
`FSSAI_AUTH_TOKENS_JSON` instead.

```bash
export OPERATOR_TOKEN='change-me-operator-token'
export AGENT_TOKEN='change-me-agent-token'
export OFFICER_TOKEN='change-me-officer-token'
export SECOND_OFFICER_TOKEN='change-me-second-officer-token'

curl -X POST http://127.0.0.1:8080/v1/resources \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -d '{"resource_id":"S-500","status":"draft","version":1}'

curl -X POST http://127.0.0.1:8080/v1/proposals \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -d '{"request_id":"req-500","operation":"prepare_case_for_review","resource_id":"S-500","from_status":"draft","to_status":"ready_for_officer_review","evidence_version":"snapshot-500"}'

curl -X POST http://127.0.0.1:8080/v1/proposals/req-500/review \
  -H "Authorization: Bearer $OFFICER_TOKEN"

# Only when the configured load threshold requires escalation: the second
# officer starts an independently timed review, waits for the declared floor,
# then endorses the exact proposal digest.
curl -X POST http://127.0.0.1:8080/v1/proposals/req-500/review \
  -H "Authorization: Bearer $SECOND_OFFICER_TOKEN"
curl -X POST http://127.0.0.1:8080/v1/proposals/req-500/endorsement \
  -H "Authorization: Bearer $SECOND_OFFICER_TOKEN"

curl -X POST http://127.0.0.1:8080/v1/proposals/req-500/approval \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $OFFICER_TOKEN" \
  -d '{"ttl_seconds":300}'

curl -X POST http://127.0.0.1:8080/v1/proposals/req-500/execute \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
```

`/review` stores the first presentation time idempotently on the server. If a
deliberation floor is configured, an immediate approval is refused; refreshing
or repeating `/review` cannot reset that clock. After the escalation threshold,
a distinct officer starts their own review and posts `/endorsement` before the
primary reviewer approves. Both identities and roles are covered by the signed
approval artifact and recorded with the action intent.

Changing the target, state, evidence version, reviewer role, or approved payload
causes a stable fail-secure error code. Retrying the successful request returns the
same receipt without another authoritative mutation.

## PySpark and Apache Iceberg

The optional `analytics` profile supplies the official Iceberg REST fixture,
S3-compatible storage, and the Spark-Iceberg quickstart image. Start it with:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml \
  --profile analytics up -d

docker compose --env-file deploy/.env -f deploy/compose.yaml exec spark-iceberg \
  spark-submit /opt/fssaira/jobs/bootstrap_iceberg.py

docker compose --env-file deploy/.env -f deploy/compose.yaml exec spark-iceberg \
  spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.3 \
  /opt/fssaira/jobs/kafka_to_iceberg.py
```

The streaming job reads normalized inward events, preserves Kafka partition and
offset, and merges them into an Iceberg v2 table on that stable identity. Replayed
micro-batches therefore do not create duplicate rows. Production deployments must pin container digests and compatible
Spark, Scala, Kafka connector, and Iceberg runtime artifacts after integration
testing. The unpinned quickstart images in Compose are for evaluation only.

## Extension contract

To add a domain:

1. Copy `profiles/template.yaml` and describe one resource and its permitted state
   transitions, reviewer roles, owner, and manual fallback.
2. Run `fssaira validate-profile profiles/your_profile.yaml`.
3. Add domain-specific contract requirements and tests for prohibited and benign
   actions, redress, accessibility, and data quality.
4. Connect the authoritative system through a register adapter that provides
   version checks and idempotent receipts.
5. Connect institutional identity, keys, policy administration, and evidence
   custody. Do not trust the demonstration identity headers.
6. Run `fssaira evaluate` and publish the JSON result with the commit, environment,
   denominators, failures, and exclusions.

The base is successful when an adopter can replace a component without changing the
rule being tested. Technology names are implementations; the control contract is the
portable framework.

## Current upstream references

- FastAPI dependency injection, lifespan, OpenAPI, and testing:
  https://fastapi.tiangolo.com/
- Redis transactions and optimistic locking:
  https://redis.io/docs/latest/develop/clients/redis-py/transpipe/
- Apache Kafka releases and official container images:
  https://kafka.apache.org/community/downloads/
- Apache Spark Structured Streaming:
  https://spark.apache.org/docs/latest/streaming/index.html
- Apache Iceberg Spark integration and REST catalog:
  https://iceberg.apache.org/docs/latest/spark-getting-started/ and
  https://iceberg.apache.org/rest-catalog-spec/

These links inform the reference configuration; they do not imply endorsement or
certification by those projects.

## Governed disclosure configuration

| Variable | Purpose | Default |
|---|---|---|
| `FSSAI_DISCLOSURE_STORE` | `memory`, `sqlite:///PATH`, or a `postgresql://` DSN for grants, revocations, consent, sessions, outputs, and emergency-access obligations | `memory` |
| `FSSAI_MODEL_ENDPOINT` | the model endpoint name declared in the domain pack; undeclared endpoints receive nothing | unset |
| `FSSAI_DISCLOSURE_TOKEN_ISSUER`, `FSSAI_DISCLOSURE_TOKEN_AUDIENCE`, `FSSAI_DISCLOSURE_TOKEN_JWKS_URL` | verify grants issued by the institutional authorization server | unset |
| `FSSAI_DISCLOSURE_CONSENT_URL` | live consent service, checked at every read and release | store-held consent |
| `FSSAI_DISCLOSURE_FHIR_URL`, `FSSAI_DISCLOSURE_FHIR_FIELDS` | FHIR R4 record source and its JSON field map | synthetic records loaded by an operator |
| `FSSAI_DISCLOSURE_GRANT_KEY`, `FSSAI_DISCLOSURE_DECLASSIFICATION_KEY` | teaching HMAC keys, replaced by institutional tokens in production | teaching keys |

See [`GOVERNED_DISCLOSURE.md`](GOVERNED_DISCLOSURE.md#running-it-for-real) for what each is tested against.

