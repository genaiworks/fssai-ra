"""Effect observations for arbitrary systems; standard library only.

Supply an independent snapshot reader and a harm predicate. Unexpected attack
errors propagate instead of being mistaken for successful containment.
"""
import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class Refused(Exception):
    pass


@dataclass
class Observation:
    before: Any
    after: Any
    refused: bool
    harmful_effect: bool


def observe_attempt(attempt: Callable, snapshot: Callable, is_harm: Callable,
                    expected_denials: tuple[type[Exception], ...] = (Refused,)) -> Observation:
    """Unexpected errors propagate: an unexecuted attack must not become a pass.

    Keep snapshot separate from the component being evaluated. It should read
    the system of record or recipient sink, not a guard's allow/deny counter.
    """
    before = copy.deepcopy(snapshot())
    refused = False
    try:
        attempt()
    except expected_denials:
        refused = True
    after = copy.deepcopy(snapshot())
    return Observation(before, after, refused, bool(is_harm(before, after)))


