"""The seven-stage lifecycle as executable gates (paper §6).

``frame → contract → pack → bind → falsify → promote → operate``

Each stage emits an artifact and passes or fails a gate. A failed gate keeps
the capability in the preceding stage. ``fssaira <stage>`` runs one stage from
the command line.
"""
