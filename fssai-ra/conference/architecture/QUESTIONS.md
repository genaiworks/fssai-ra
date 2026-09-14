# The uncomfortable questions

Answers are about this reference implementation. Where a claim rests on a figure, the figure
is in [`../evidence/SCORECARD.md`](../evidence/SCORECARD.md) and was produced by running code.

## Could the same property be achieved with a smaller trusted base?

Partly, and some of it has been done. The executor used to verify approvals with the same
HMAC secret the approval service signed with, so a compromised executor could mint its own
approvals; approvals are now Ed25519 and the executor holds only a public key. The evidence
notary signs checkpoints with a key the evidence writer does not hold. What remains in the
base is listed in the scorecard's trusted-computing-base table: both mediators, key custody,
the approval and grant authorities, the notary key, the model publisher key, and the pack
floor. Publishing checkpoints to an external transparency log would remove the notary; an HSM
or KMS would narrow custody. The model, the router, agents, tools, and pack authors are
outside the base and are attacked as adversaries in every falsifier.

## Are the two mediators actually independent?

Logically yes, physically not in this reference. They hold different credentials (write versus
decrypt), check different questions, and neither accepts the other's output as authority. But
here they run in one Python process and share an evidence ledger, so a process-level compromise
is a common-mode failure of both. A deployment separates them into processes with separate
service identities, and that separation is not demonstrated here.

## Can the model influence mediator policy indirectly?

It can try through four channels. **Domain packs**: the kernel floor rejects the malicious pack
with every attempt named. **Router suggestions**: advisory; the gate and registry decide, and
either alone stopped the router attacks (defence in depth measured in F11). **Human reviewers**:
the model's text reaches a person, and persuasion is not something code can fully contain. The
trace's reviewer approves only what matches the case file, and review is capacity-bounded, but
real reviewer susceptibility is unmeasured. **Outputs read by other agents**: outputs carry
labels and tokens, not authority.

## Can an administrator bypass the architecture?

Yes. Someone holding custody keys, the approval signing key, and write access to the register
can do anything. The architecture makes this visible, not impossible: separate credentials,
signed evidence, and separation of duties raise the number of people who must collude. It does
not replace institutional controls over administrators.

## Does evidence itself become a vulnerability?

It could. The evidence plane stores digests, surrogate identifiers, codes, and field names, never
values, and every trace checks that no identity value appears in evidence. Metadata still leaks:
who accessed which surrogate, when, for what purpose. The erasure journal keeps surrogate
identifiers by design. Evidence must be access-controlled and retention-limited.

## Can derived data escape the privacy boundary?

Within governed paths: outputs inherit their session's label, models cannot lower it (F24),
identifiers the model writes in clear are re-tokenized, embeddings are encrypted under the
student's key, and derived outputs are purged on erasure. Outside governed paths: anything
released to an entitled person leaves custody, and non-identity facts paraphrased into an
output are protected by the label, not by detection.

## Is "local model" being treated as trustworthy?

No. Local endpoints must present the attested digest and model identity and be approved for
the purpose and data classes. Substituted weights under the approved name are refused (F10).
Local models still receive tokens, not identity. Local changes where weights run, not what they
may do.

## Is cryptographic erasure complete?

For the copies the architecture governs, it was verified by trying to read the student back:
primary store, snapshot backup, key backup restored with the journal, token map, vector index,
and derived outputs were unreadable or absent. Negative plaintext scans of stored bytes and
evidence are reported as *unverified*, because not finding a string is not proof. Not covered:
released content, model runtime memory, Python heap residue, and key material retained outside
custody.

## Can delegation become privilege escalation?

Not along the seven declared axes: subjects, fields, classes, purpose, expiry, zones, audience.
Every escalation case was refused, revoking a parent revoked its children, and stateful sequences
found no child exceeding its parent. Removing attenuation produced violations immediately.
Purpose is an exact identifier: "academic support" and "tutoring support" are different purposes,
which is safe and sometimes inconvenient.

## Can human review become rubber-stamping?

It can, and the architecture bounds rather than prevents it. Review has declared capacity,
queue limits, timeouts, escalation, and a manual fallback; overload defers or escalates and never
approves (F17). Whether a real reviewer reads carefully at the declared capacity is an empirical
question this repository cannot answer.

## What happens when the policy engine or a mediator is compromised?

The guarantee that mediator provides is lost for everything its credential reaches. A compromised
context gate discloses what custody lets it decrypt; a compromised executor can write without
approval but still cannot mint approvals that other verifiers accept. Signed evidence makes both
detectable after the fact if checkpoints are published outside the compromised process. The
trusted-computing-base table states each failure mode.
