# FSSAI-RA console

A React operator console for the control plane. It is a client, not a component:
every operation it performs is available from `fssaira` and the HTTP API, and it
holds no credential the API does not check.

```bash
npm install
npm run dev          # http://localhost:5173, proxies /api to 127.0.0.1:8080
```

Point it elsewhere with `FSSAI_API_URL=http://host:8080 npm run dev`, or build a
static bundle with `npm run build` and serve `dist/` behind the included nginx
configuration.

## What each tab is for

| Tab | Question it answers |
|---|---|
| Deployment | What is this deployment actually running, and what is wrong with it? |
| Governance | Which transitions are enforced, by whom, and what may a model propose? |
| Actions | Propose → approve → execute, including the denials |
| Intelligence | What would the model like to do, and what is that really worth? |
| Evidence | The hash-chained record, and whether it still verifies |
| Assurance | Model check and conformance, run against *these* backends |

## Deliberate design choices

**Denial codes are shown verbatim.** `APPROVAL_PAYLOAD_MISMATCH` tells an
operator that the proposal changed after review. Flattening that to "error"
would destroy the only information that matters.

**Bad states are not made to look calm.** Volatile storage, a broken chain, and
active teaching keys are rendered as prominently as successes. A governance
console that flatters its operator is worse than no console.

**The identity selector is a demonstration.** It switches between published
development bearer tokens so a reader can watch separation of duties work. It is
reported as a blocking finding on the Deployment tab for exactly that reason.
