# Oro Verde Weighbridge Agent — core scaffold

This directory contains the protocol-safe core for a future Windows local weighbridge agent.

## Implemented

- Explicit protocol-to-driver registry. Unknown protocol IDs fail closed.
- A typed device-sample contract; the device driver must decode the real stable/motion status.
- Consecutive stable-sample gate, freshness checks, finite-decimal validation, and kg normalization from kg/g/lb.
- Unit tests for unsupported protocols, stability resets, stale/future samples, malformed values, and unit conversion.

## Deliberately not implemented yet

- No serial, USB, or TCP device transport.
- No manufacturer/model driver.
- No Windows service or installer.
- No credential provisioning, cloud connection, heartbeat, or API ingestion.
- No simulated readings and no generic parser that guesses a weight from arbitrary bytes.

The scaffold cannot connect to a scale and must not be described as connected. A real driver requires the exact indicator manufacturer, model, protocol manual, and captured frames. Cloud transport requires the authenticated bridge endpoint and credential lifecycle to be implemented in the Oro Verde API first.

## Development

Install the package and test extra in a Python 3.11+ environment:

```bash
python -m pip install -e ".[test]"
pytest
```

A vendor driver should implement `ScaleDriver` in `src/oroverde_weighbridge/drivers/` and be explicitly registered by its exact protocol ID. It must validate framing, status flags, units, sign, and checksums as specified by the manufacturer's protocol.
