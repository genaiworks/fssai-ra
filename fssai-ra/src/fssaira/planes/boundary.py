"""Boundary plane: authenticate ingress and egress; quarantine untrusted input as data.

The no-read-back seam is software here (:class:`fssaira.diode.OneWayChannel`,
UDP transport) and is swappable for certified one-way hardware.
"""
from __future__ import annotations

from fssaira.planes.base import Plane, Prohibition

PLANE = Plane(
    name="boundary",
    responsibility=(
        "Authenticate every caller and source, carry retrieved or imported content as "
        "untrusted data, and expose a no-read-back seam"
    ),
    must_not=(
        Prohibition("let retrieved or imported text act as instructions or open an egress path",
                    "tests/test_attacks.py::test_prompt_injection_is_stripped_and_egress_blocked"),
        Prohibition("publish input whose source signature does not verify",
                    "tests/test_import_api.py::test_import_gateway_quarantines_bad_signature_without_publishing"),
        Prohibition("expose a read-back route from the governed side",
                    "tests/test_import_api.py::test_import_gateway_has_no_readback_route"),
        Prohibition("accept a transport channel that can read back",
                    "tests/test_diode_transport.py::test_a_channel_that_can_read_back_is_rejected"),
    ),
    components=(
        "fssaira.import_boundary:ImportBoundary",
        "fssaira.diode:OneWayChannel",
        "fssaira.diode_transport:UdpDiodeReceiver",
    ),
)
