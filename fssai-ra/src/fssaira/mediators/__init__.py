"""The two mediators, reference monitors in the Saltzer–Schroeder sense.

* :mod:`fssaira.mediators.executor` enforces Rule 1 (action authority). It is
  the sole holder of the write credential.
* :mod:`fssaira.mediators.context_gate` enforces Rule 2 (governed disclosure).
  It is the sole holder of record access and data keys.

Both modules are kernel-facing names over the single existing implementation of
each mediator; neither forks it.
"""
