"""The sector-neutral kernel of Trust by Construction.

The kernel holds what no domain pack may replace:

* ``contract``: the seven-field control contract, its strict loader, and the
  resolver that proves every named failure test exists.
* ``claims``: the claims register (``machine_verified | attested | unverified``).
* ``state_machine``: the legal lifecycle of a consequential effect.
* ``evidence``: the append-only hash chain and its externally keyed checkpoint.
* ``invariants``: the action invariants checked by bounded enumeration.

A new sector supplies a domain pack; a new model supplies a re-attested bundle.
Neither edits this package. Submodules are imported explicitly so that loading
the kernel's contract tooling never drags in optional backends.
"""
