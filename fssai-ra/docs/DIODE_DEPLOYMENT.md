# One Way Data Diode Integration Guide

## Claim boundary

`OneWayChannel` and the import-gateway container implement an inward-only software
interface. They are useful for development because protected-domain code receives
the same normalized envelope expected behind a physical gateway. They do not make
reverse communication physically impossible. A process, host, hypervisor, network
administrator, or alternate interface can defeat a software-only topology.

Use the phrase **physical one-way transfer** only when the deployed link and all
relevant alternate paths have been independently assessed.

## Hardware replacement seam

The low-side transmitter receives a released normalized envelope with this minimum
schema:

```json
{
  "source": "registered-source-id",
  "text": "normalized untrusted content",
  "stripped": ["detected-marker"],
  "trace_id": "stable-transfer-identifier",
  "content_hash": "sha256-of-normalized-content"
}
```

The high-side receiver validates framing, length, schema, sequence, duplicate status,
and content hash before publishing to the protected Kafka topic. It never interprets
content as an instruction or accepts access labels from the envelope.

## Deployment checklist

- Inventory every network interface, management port, wireless device, removable
  medium, console, telemetry path, power-management channel, and authorized output.
- Document which boundary the diode crosses and what information is allowed inward.
- Place signing, malware scanning, decompression, and risky parsing on the correct
  side according to the threat model; use constrained formats and resource limits.
- Authenticate source releases before transfer and independently validate the
  high-side envelope.
- Define sequence-gap, duplicate, corruption, overflow, and receiver-outage behavior.
- Ensure the high side has no route to acknowledgements on the diode link. Operational
  acknowledgements, if required, must use a separately governed channel and disclose
  what it can reveal.
- Exercise maintenance and break-glass procedures. A temporary bidirectional cable
  invalidates the ordinary directionality claim while connected.
- Retain equipment model, firmware, configuration, physical diagram, test method,
  tester, date, result, and residual paths as evidence.
- Repeat the assessment after topology, firmware, maintenance, or ownership changes.

## Availability and manual continuity

An inward-only path can fail silently from the sender's perspective because it has no
return acknowledgement. Monitor receiver sequence and freshness on the high side.
When freshness exceeds the declared threshold, stop automated use of affected data,
alert the owner, and continue through the documented manual service path. Never
restore availability by silently enabling an ungoverned reverse link.
