"""Import boundary: a software model of a one-way data diode.

A hardware diode permits data to travel low-side -> high-side over a single link
and makes the reverse direction physically impossible. This class models that
property in code: it exposes :meth:`send_inward` and *deliberately provides no
method to move data outward*. Egress attempts therefore have no ordinary API to
call. This is the structural half of "no ordinary path for sensitive-data
egress"; the enforcement half (denying egress-capable tools) lives in the policy
enforcement point.

For a link that really is separated -- loopback in a demo, a certified
cross-domain solution in a deployment -- use :mod:`fssaira.diode_transport`,
whose sender and receiver are separate processes on separate sockets. The
application code is identical either way, which is the whole point.

:func:`assert_no_return_path` turns "there is no method to read back" from a
comment into a check. The conformance suite runs it against whatever inward
channel a deployment has configured, including third-party ones.
"""
from __future__ import annotations

import inspect
from collections.abc import Callable

#: Method names that would constitute a return path if an inward channel had them.
RETURN_PATH_NAMES = (
    "recv", "recvfrom", "receive", "read", "read_back", "readback", "poll",
    "fetch", "pull", "reply", "respond", "ack", "acknowledge", "send_outward",
    "egress", "request", "roundtrip", "query",
)


class DiodeBreachError(RuntimeError):
    """Raised if inward delivery is attempted with no high-side handler wired."""


class ReturnPathError(AssertionError):
    """Raised when a channel that claims to be one-way exposes a way back."""


class OneWayChannel:
    def __init__(self) -> None:
        self._high_side: Callable[[dict], None] | None = None
        self.items_sent = 0

    def connect(self, high_side_handler: Callable[[dict], None]) -> None:
        """Wire the protected-domain receiver. Called once at assembly time."""
        self._high_side = high_side_handler

    def send_inward(self, item: dict) -> None:
        """Move one validated item low-side -> high-side. The only direction."""
        if self._high_side is None:
            raise DiodeBreachError("diode has no high-side handler connected")
        self.items_sent += 1
        self._high_side(item)

    # There is intentionally no send_outward / read_back method.


def assert_no_return_path(channel: object, *, extra_names: tuple[str, ...] = ()) -> None:
    """Fail if ``channel`` exposes any callable that could carry data outward.

    This is an inspection, not a proof. It catches the realistic mistake -- a
    well-meaning adapter adding ``read_back()`` for debugging, or wrapping a
    request/response client and calling it a diode -- which is precisely the
    kind of regression that would quietly void the directional claim while every
    other test still passed.
    """
    found = []
    for name in RETURN_PATH_NAMES + tuple(extra_names):
        attribute = getattr(channel, name, None)
        if attribute is not None and callable(attribute):
            found.append(name)
    if found:
        raise ReturnPathError(
            f"{type(channel).__name__} exposes return-path method(s): {', '.join(sorted(found))}. "
            "An inward channel must offer no way to move data outward."
        )


def describe_channel(channel: object) -> dict:
    """Summarise an inward channel for the assurance report and the console."""
    public = [
        name for name, _ in inspect.getmembers(channel, callable)
        if not name.startswith("_")
    ]
    try:
        assert_no_return_path(channel)
        one_way = True
        detail = ""
    except ReturnPathError as exc:
        one_way = False
        detail = str(exc)
    return {
        "type": type(channel).__name__,
        "public_methods": sorted(public),
        "one_way": one_way,
        "detail": detail,
    }


__all__ = [
    "DiodeBreachError", "OneWayChannel", "RETURN_PATH_NAMES", "ReturnPathError",
    "assert_no_return_path", "describe_channel",
]
