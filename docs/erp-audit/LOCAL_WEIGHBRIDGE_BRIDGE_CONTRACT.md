# Oro Verde local weighbridge bridge contract

Status: architecture contract only. The current application stores and validates the scale profile; it does not yet connect to a physical indicator.

## 1. Deployment topology

The bridge is a small Windows service installed on the mill's weighing-station PC. It is not a browser extension and must not require workers' phones to open a LAN port.

- The Windows service initiates an outbound TLS connection to the Oro Verde API.
- No inbound firewall port is opened on the mill PC or router.
- The service reconnects with bounded exponential backoff and reports heartbeat/health.
- Workers continue using the normal hosted Oro Verde application on their phones. They receive readings through the authenticated application API, not by contacting the Windows PC directly.
- The bridge is read-only: it must never send commands that alter the indicator, calibration, tare memory, or configuration.

## 2. Authentication and secret handling

- An administrator provisions or rotates a dedicated bridge credential from the authenticated application.
- The API stores only a one-way hash of the credential. The raw credential is displayed once at provisioning and is never returned by settings GET.
- The installer stores the credential using Windows DPAPI / Windows Credential Manager, not in a plaintext JSON file or command-line argument.
- Bridge messages are accepted only over TLS and only for the single configured mill/device identity.
- Revoke/rotate immediately invalidates the previous credential. Worker accounts cannot provision or rotate it.
- Do not use a shared employee password, Render database URI, or general API key as the bridge credential.

## 3. Reading envelope

Each reading sent by the bridge must include:
- configured device ID and protocol/driver identifier;
- monotonically increasing per-installation sequence number;
- device receive timestamp and bridge send timestamp in UTC;
- raw value and raw unit as received (for audit/debug, bounded length);
- normalized value in kg as a decimal string;
- stability state and sample count;
- source = `scale`.

The API must reject malformed, non-finite, out-of-range, unsupported-unit, stale, future-dated, duplicate, or out-of-order readings. A successful heartbeat is not proof of a valid weight reading.

## 4. Driver and protocol policy

The configured manufacturer/model and protocol identify an adapter. There is no universal serial/TCP weighing protocol.

- A driver must be selected by an explicit supported protocol identifier.
- Unknown protocols fail closed with `unsupported_protocol`; they must never fall back to guessing numeric substrings from arbitrary device output.
- Each driver owns frame boundaries, status flags (stable/unstable/overload), sign handling, unit decoding, checksum validation where applicable, and device-specific error codes.
- A value marked unstable, overload, motion, or error is not eligible for capture.
- A driver must not report a reading stable merely because bytes arrived or a TCP connection opened.

## 5. Stable reading and capture

The bridge publishes live samples, but the server remains authoritative for acceptance:
- require the configured number of consecutive stable samples;
- reject samples outside the configured freshness window;
- retain decimal precision and normalize units before arithmetic;
- gross and tare are captured as separate operator actions from a current stable reading;
- net is always calculated server-side as gross minus tare, never trusted from the bridge or browser;
- preserve operator, timestamp, device, and source metadata in the immutable weighing audit snapshot.

A scale disconnection must not silently reuse the last value. The UI must mark the reading stale/unavailable and offer the existing manual entry path with source `manual`.

## 6. Rollout gates

Do not enable live weighing in production until all are true:
1. exact indicator manufacturer/model and manual/protocol are known;
2. a model-specific driver has fixtures from real device frames, including stable, unstable, overload, negative, malformed, and disconnect cases;
3. bridge authentication, rotation, replay protection, and stale-reading tests pass;
4. Windows service reconnect and restart tests pass;
5. a real mill-scale acceptance test compares displayed gross/tare/net with the indicator;
6. traditional intake and GS olive purchase both consume the same validated reading contract without changing their existing business rules.

## 7. Current implementation boundary

The Settings profile and its validation are implemented in the companion PR. This document defines the secure local-bridge boundary only. The bridge executable, Windows installer/service, transport drivers, cloud ingestion endpoints, and live-reading UI are not implemented yet. No physical connection or reading is claimed.
