# Bindings

The contract is the institution's document. These files are *this
implementation's* claim about which executable check enforces each requirement,
and they are kept separate for that reason: an adopter who replaces the
implementation keeps the contract and rewrites the bindings.

A binding names a mechanism and a locator. `fssaira coverage` checks that every
requirement is either bound here or declared `verified_by: organizational` in the
contract itself, and prints the count of those that are neither.

Mechanisms, loosely ordered by strength of evidence:

| Mechanism | What it means |
|---|---|
| `model_check` | an invariant enumerated over a declared state space |
| `conformance` | a portable check run against the deployment's own backends |
| `ablation` | the control was removed and the harm returned |
| `scenario` | an adversarial scenario contained by the enforcement point |
| `unit_test` | a deterministic test asserting the control's behaviour |
| `attestation` | a named role attests on a declared cadence |

A binding is a claim that the control is *exercised*, never that it is
*adequate*. Strength of evidence is the mechanism name, not a score.
