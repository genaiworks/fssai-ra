# FSSAI RA Extensible Platform Guide

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
  HMAC quarantine                                  +--> PySpark validation
  no read-back route                               |        |
                                                    |        v
CONTROL PLANE                                      |   Apache Iceberg
                                                    |   snapshots and history
client -> FastAPI :8080 -> Redis                    |
          |                cases proposals          +--> controlled consumers
          |                approvals idempotency
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
python -m venv .venv
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
python scripts/bootstrap_dev_env.py
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d \
  redis kafka control-api import-gateway
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8081/health
```

The generated `deploy/.env` is ignored by Git and contains random local credentials.
Do not promote it. An institutional deployment should obtain secrets from its key
management service, authenticate callers through an OIDC or workload-identity
gateway, enable authenticated and encrypted Kafka listeners, and operate Redis with
an approved persistence and high-availability design.

### Exercise the exact-action API

```bash
curl -X POST http://127.0.0.1:8080/v1/resources \
  -H 'Content-Type: application/json' \
  -H 'X-FSSAI-Identity: operator-1' \
  -H 'X-FSSAI-Role: platform_operator' \
  -d '{"resource_id":"S-500","status":"draft","version":1}'

curl -X POST http://127.0.0.1:8080/v1/proposals \
  -H 'Content-Type: application/json' \
  -H 'X-FSSAI-Identity: agent-1' \
  -H 'X-FSSAI-Role: bounded_agent' \
  -d '{"request_id":"req-500","operation":"prepare_case_for_review","resource_id":"S-500","from_status":"draft","to_status":"ready_for_officer_review","evidence_version":"snapshot-500"}'

curl -X POST http://127.0.0.1:8080/v1/proposals/req-500/approval \
  -H 'Content-Type: application/json' \
  -H 'X-FSSAI-Identity: officer-1' \
  -H 'X-FSSAI-Role: student_support_officer' \
  -d '{"ttl_seconds":300}'

curl -X POST http://127.0.0.1:8080/v1/proposals/req-500/execute \
  -H 'X-FSSAI-Identity: executor-1' \
  -H 'X-FSSAI-Role: executor'
```

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
offset, and appends them to an Iceberg v2 table through a checkpointed Structured
Streaming query. Production deployments must pin container digests and compatible
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
