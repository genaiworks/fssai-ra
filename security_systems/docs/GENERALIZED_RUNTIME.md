# General-purpose tool boundary

`trustkernel.runtime.GuardedDispatcher` is a synchronous, domain-independent interface over the guard. Tool functions, resource IDs, caller mappings, approval roles, disclosure policies, and observation callbacks are supplied by the application. It has no dependency on conference worlds, model APIs, deployment terminology, or a specific agent framework.

## Request and trust boundary

The model emits only:

```json
{"tool": "update_item", "arguments": {"resource": "item-7", "value": "reviewed"}}
```

The transport authenticates the caller and passes its identity separately. The dispatcher resolves that identity through a copied server-owned mapping. Fields such as `caller`, `role`, `context`, and `approval` in the request envelope are rejected. This separation prevents a model request from selecting its own identity; it does not itself authenticate a network connection.

## Minimal integration

```python
from trustkernel.guard import ActionClass, Guard
from trustkernel.runtime import GuardedDispatcher

guard = Guard()
state = {}

@guard.tool(resource="resource", action_class=ActionClass.HIGH_IMPACT, approver_role="reviewer")
def update_item(resource, value="reviewed"):
    state[resource] = value
    return {"resource": resource, "value": value}

context = guard.root("worker", tools={"update_item"}, resources={"item-7"})
dispatcher = GuardedDispatcher(guard, {"authenticated-session": context})
request = {"tool": "update_item", "arguments": {"resource": "item-7"}}
proposal = dispatcher.propose("authenticated-session", request)
approval = guard.approve(proposal, approver="human", role="reviewer")  # reference approval service
result = dispatcher.dispatch("authenticated-session", request, approval=approval)
```

`approve` remains a trusted reference issuer. An application must authenticate its human reviewer and role before calling it; do not expose issuance to the agent. Execute `python examples/generalized_dispatch.py` for three synthetic adapters—deploy, refund, and publish—using the same dispatcher interface. These are portability examples, not independent deployment studies.

## Contracts strengthened by this review

- Function signatures are validated before a call can consume approval. Omitted defaults are included in both the reviewed argument digest and the executed call.
- Resource strings name actual function parameters. A missing/misspelled parameter fails registration. Constant and composite resource IDs require an explicit pure resolver such as `resource=lambda arguments: "catalog"`.
- Duplicate tool names fail registration, preventing an existing name from silently changing implementation inside one guard.
- Cached approved results are deep-copied; a caller cannot mutate the stored receipt through a returned list or dictionary.
- The dispatcher accepts the explicit argument map, including tool parameters named `resource` or `tool`, without colliding with proposal metadata.
- `handoff(producer, consumer, content)` snapshots JSON content and propagates the sender's label before returning it. `release` checks output policy before the application sends the result to its sink.

The low-level `Guard.propose` remains available for compatibility. Prefer `dispatcher.propose` or `Guard.propose_call` for registered tools, especially when argument names collide with metadata names.

## Evaluation independent of the application

```python
from trustkernel.evaluation import observe_attempt

observation = observe_attempt(
    attempt=send_test_request,
    snapshot=read_actual_target_state,
    is_harm=lambda before, after: after["value"] == "unreviewed",
    expected_denials=(YourAuthorizationError,),
)
assert not observation.harmful_effect
```

The observer reads the system of record or recipient sink, not a guard counter. Snapshot copies preserve the before-state. Unexpected exceptions propagate; they do not count as containment. Also supply a legitimate-work case and a deliberately weakened positive control. `trustkernel.evaluation` uses only the standard library.

## Supported scope and migration

This API supports synchronous functions with explicit keyword-compatible parameters and JSON-valued arguments. Async functions, generators, positional-only parameters, variadic signatures, and tool arguments named `approval` are rejected at registration. Wrap a dynamic tool with a small explicit synchronous adapter. Do not wrap a coroutine and claim it has been executed synchronously.

The new binding rules intentionally change digests for calls that previously omitted defaults. Reissue approvals when upgrading; in-memory approval state is not a durable migration format. A string resource previously treated as a literal must now be an explicit resolver. The registry and caller mapping are configured by trusted application code.

Returned values must support defensive copying for approved execution. A callback that changes external state and then fails still requires reconciliation. This layer provides no process sandbox, transport authentication, persistent identity store, multi-process receipt store, streaming enforcement, or crash-safe external transaction. Those remain explicit deployment responsibilities.

## Verification

`tests/test_guard_generalization.py` reproduced six failing contracts before the fixes. `tests/test_runtime.py` checks caller-field injection, unknown tools/callers, authority narrowing, payload swapping, handoff propagation, metadata-name collisions, and legitimate replay across three resource vocabularies. These complement the original world-harness tests.
