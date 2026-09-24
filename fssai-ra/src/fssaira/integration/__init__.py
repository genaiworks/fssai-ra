<<<<<<< HEAD
"""Strict integration contracts. Adapters must enforce these before transport."""
=======
"""The GenAI integration contract (paper Section 6.1) as enforced interfaces.

A future model, orchestrator, or tool protocol plugs into this package, never
around it:

* ``typed``: versioned ``Proposal`` and ``ContextRequest`` parsing. Server-derived
  security fields come only from an authenticated ``CallerContext``.
* ``retrieval``: retrieval as a protected read, authorized before any candidate
  is generated or scored.
* ``memory``: labelled, provenance-carrying, retention-bounded memory artifacts
  whose restrictions survive import into a new session.
* ``bundle``: a model change is a signed bundle of eight component digests,
  attested only by an independent measurement.
* ``streaming``: a streamed response is a sequence of governed releases.
* ``sandbox``: process-level containment for generated code, with its honest
  limit stated and executed.

Submodules are imported explicitly; importing this package loads nothing else.
"""
>>>>>>> 1423e13 (M4: GenAI integration contract, backend assurance, and two fail-open fixes)
