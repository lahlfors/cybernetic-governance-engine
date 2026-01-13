# Contribution Strategy: NeMo Guardrails ISO 42001 Exporter

## Overview
We have implemented a custom `NeMoOTelCallback` that leverages the `StreamingHandler` interface to hook into the NeMo Guardrails event loop. This allows us to emit structured OpenTelemetry spans for every guardrail intervention, satisfying **ISO 42001 Annex A.6.2.8 (Event Logging)** requirements.

## Implementation Details
*   **Class:** `NeMoOTelCallback` (extends `nemoguardrails.streaming.StreamingHandler`)
*   **Events Captured:** `on_action_start`, `on_action_end`.
*   **Attributes:**
    *   `guardrail.id`: The name of the action (e.g., `self_check_input`).
    *   `guardrail.outcome`: `ALLOWED` or `BLOCKED`.
    *   `iso.control_id`: `A.6.2.8`.
    *   `guardrail.block_reason`: The detailed refusal message or status.

## Integration Pattern
The integration uses the `streaming_handler` mechanism supported by NeMo's `generate_async` method.
1.  Initialize `NeMoOTelCallback`.
2.  Set `nemoguardrails.context.streaming_handler_var` to the callback instance (Critical for capturing internal actions).
3.  Pass the callback as `streaming_handler` to `rails.generate_async`.

## Proposal for `nvidia/nemo-guardrails`
We propose contributing this pattern as a standard "Compliance Exporter" or "Observability Hook".

### Pull Request Description
**Title:** feat(telemetry): Add OpenTelemetry Exporter for ISO 42001 Compliance

**Description:**
This PR introduces a standardized `OTelCallback` that provides observability into guardrail execution. Currently, users often struggle to see *why* a guardrail triggered in production without parsing text logs. This exporter creates structured spans for every `check_*` or `guard_*` action.

**Key Changes:**
1.  New module `nemoguardrails.telemetry.otel`.
2.  `OTelCallback` class implementing `StreamingHandler`.
3.  Documentation on how to use `streaming_handler_var` to enable deep tracing.

**Benefit:**
*   Enterprises targeting ISO 42001 or EU AI Act compliance get "out-of-the-box" audit logging.
*   Debugging of "over-active" rails becomes easier with visual traces.

## Next Steps
1.  Fork `nvidia/nemo-guardrails`.
2.  Port `src/infrastructure/telemetry/nemo_exporter.py` to `nemoguardrails/telemetry/otel.py`.
3.  Add unit tests verifying span creation.
4.  Submit PR.
