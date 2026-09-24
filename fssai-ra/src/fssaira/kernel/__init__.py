<<<<<<< HEAD
"""Stable sector-neutral kernel interfaces; existing implementation imports remain valid."""
from .contracts import CapabilityContract, execute_contracts, load_contracts
from .state import EffectState, transition

__all__ = ['CapabilityContract', 'EffectState', 'execute_contracts', 'load_contracts', 'transition']
=======
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
>>>>>>> d323d4c (M1: kernel contract engine, claims register, effect state machine)
