# BHIV vNEXT MASTERDB-GEO-QUEST-01: Rule-Coverage Matrix

**Dataset Target:** Mumbai FIR Aircraft Surveillance (`BHIV-GEO-QUEST-01-AIRCRAFT`)
**Pipeline Engine:** Deterministic Validator & Quarantine Engine (`scripts/validator_engine.py`)
**Test Suite:** `tests/test_validation.py` (executed via `pytest`, 12/12 passing)
**Last Audit UTC:** `2026-10-13T12:40:00Z`

---

## 1. Rule-to-Fixture & Test Traceability Matrix

| Rule ID | Rule Scope & Objective | Severity | Exception Code | Associated Fixture Path | Test Function in `tests/test_validation.py` | Expected Disposition | Actual Outcome Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`RULE_PROV_01`** | **Ingestion Lineage**: Verifies source URL and acquisition timestamp are present. | `CRITICAL` | `ERR_PROV_MISSING` | [`fixtures/synthetic/missing_provenance.json`](file:///c:/Users/Microsoft/week/MASTERDB-GEO-QUEST-01/fixtures/synthetic/missing_provenance.json) | `test_missing_provenance` | `QUARANTINE` | Quarantined; code `ERR_PROV_MISSING`, severity `CRITICAL` (**PASS**) |
| **`RULE_TYPE_01`** | **Required Non-Null Fields**: Ensures `hex`, `lat`, and `lon` are not null or empty. | `CRITICAL` | `ERR_REQUIRED_NULL` | [`fixtures/synthetic/malformed_types.json`](file:///c:/Users/Microsoft/week/MASTERDB-GEO-QUEST-01/fixtures/synthetic/malformed_types.json) | `test_malformed_types`, `test_warning_vs_hard_failure_disposition` | `QUARANTINE` | Quarantined; code `ERR_REQUIRED_NULL`, severity `CRITICAL` (**PASS**) |
| **`RULE_TYPE_02`** | **Data Type Parsing**: Ensures numeric and coordinate floats parse properly without NaN/inf. | `ERROR` | `ERR_TYPE_MALFORMED` | [`fixtures/synthetic/malformed_types.json`](file:///c:/Users/Microsoft/week/MASTERDB-GEO-QUEST-01/fixtures/synthetic/malformed_types.json) | `test_malformed_types` | `QUARANTINE` | Quarantined; code `ERR_TYPE_MALFORMED`, severity `ERROR` (**PASS**) |
| **`RULE_ID_01`** | **Identifier Uniqueness**: Detects duplicate ICAO hex addresses within a batch snapshot. | `ERROR` | `ERR_ID_DUPLICATE` | [`fixtures/synthetic/duplicate_identifiers.json`](file:///c:/Users/Microsoft/week/MASTERDB-GEO-QUEST-01/fixtures/synthetic/duplicate_identifiers.json) | `test_duplicate_identifiers` | `QUARANTINE` (2nd instance) | 1st accepted, 2nd quarantined; code `ERR_ID_DUPLICATE` (**PASS**) |
| **`RULE_SCHEMA_01`** | **Schema Conformance**: Rejects non-dictionary records or payloads missing core state vectors. | `CRITICAL` | `ERR_SCHEMA_MISMATCH` | [`fixtures/synthetic/schema_mismatch.json`](file:///c:/Users/Microsoft/week/MASTERDB-GEO-QUEST-01/fixtures/synthetic/schema_mismatch.json) | `test_schema_mismatch` | `QUARANTINE` | Quarantined; code `ERR_SCHEMA_MISMATCH`, severity `CRITICAL` (**PASS**) |
| **`RULE_TIME_01`** | **Negative Sensor Latency**: Flags negative observation or position ages (future clock drift). | `ERROR` | `ERR_TIME_FUTURE` | [`fixtures/synthetic/stale_future_timestamps.json`](file:///c:/Users/Microsoft/week/MASTERDB-GEO-QUEST-01/fixtures/synthetic/stale_future_timestamps.json) | `test_stale_future_timestamps` | `QUARANTINE` | Quarantined; code `ERR_TIME_FUTURE`, severity `ERROR` (**PASS**) |
| **`RULE_TIME_02`** | **Stale Observation Threshold**: Flags observation latency exceeding operational shelf-life (> 3600s). | `WARNING` | `ERR_TIME_STALE` | [`fixtures/synthetic/stale_future_timestamps.json`](file:///c:/Users/Microsoft/week/MASTERDB-GEO-QUEST-01/fixtures/synthetic/stale_future_timestamps.json) | `test_stale_future_timestamps`, `test_warning_vs_hard_failure_disposition` | `QUARANTINE` (Policy) | Quarantined; code `ERR_TIME_STALE`, severity `WARNING` (**PASS**) |
| **`RULE_PHYS_01`** | **Kinematic Physical Envelopes**: Clamps coordinates to WGS84, speeds $\le 1500$ kts, tracks $[0, 360^\circ]$, alt $[-2000, 85000]$ ft. | `ERROR` | `ERR_PHYS_OUT_OF_BOUNDS` | [`fixtures/synthetic/inconsistent_measurements.json`](file:///c:/Users/Microsoft/week/MASTERDB-GEO-QUEST-01/fixtures/synthetic/inconsistent_measurements.json) | `test_inconsistent_measurements` | `QUARANTINE` | Quarantined; code `ERR_PHYS_OUT_OF_BOUNDS`, severity `ERROR` (**PASS**) |
| **`RULE_PHYS_02`** | **Cross-Field Physics Consistency**: Enforces surface logic (e.g. `on_ground=True` cannot cruise at $> 120$ kts). | `ERROR` | `ERR_PHYS_INCONSISTENT` | [`fixtures/synthetic/inconsistent_measurements.json`](file:///c:/Users/Microsoft/week/MASTERDB-GEO-QUEST-01/fixtures/synthetic/inconsistent_measurements.json) | `test_inconsistent_measurements` | `QUARANTINE` | Quarantined; code `ERR_PHYS_INCONSISTENT`, severity `ERROR` (**PASS**) |
| **`RULE_CONS_01`** | **Record Conservation Law**: $\text{Input Count} = \text{Accepted Count} + \text{Quarantined Count}$. | `CRITICAL` | `ERR_CONSERVATION_VIOLATION` | Verified across live capture, combined synthetic batch, and imbalanced counts | `test_conservation_rule_synthetic`, `test_real_dataset_compatibility`, `test_conservation_enforcement_negative` | `ACCEPT` (balanced) / `REJECT` (imbalanced) | Balanced: `conservation_verified==True`; Imbalanced: triggers `ERR_CONSERVATION_VIOLATION` with exact discrepancy (**PASS**) |

---

## 2. Fixture Suite Summary

| Fixture ID | Fixture Filename | Record Count | Expected Accepted | Expected Quarantined | Key Exceptions Triggered | Verified Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `SYNTH_01_VALID` | `valid_record.json` | 1 | 1 | 0 | None (`PASS`) | **VERIFIED** |
| `SYNTH_02_MISSING_PROVENANCE` | `missing_provenance.json` | 1 | 0 | 1 | `ERR_PROV_MISSING` | **VERIFIED** |
| `SYNTH_03_MALFORMED_TYPES` | `malformed_types.json` | 1 | 0 | 1 | `ERR_REQUIRED_NULL`, `ERR_TYPE_MALFORMED` | **VERIFIED** |
| `SYNTH_04_DUPLICATE_IDENTIFIERS` | `duplicate_identifiers.json` | 2 | 1 | 1 | `ERR_ID_DUPLICATE` | **VERIFIED** |
| `SYNTH_05_SCHEMA_MISMATCH` | `schema_mismatch.json` | 1 | 0 | 1 | `ERR_SCHEMA_MISMATCH`, `ERR_REQUIRED_NULL` | **VERIFIED** |
| `SYNTH_06_STALE_FUTURE_TIMESTAMPS` | `stale_future_timestamps.json` | 2 | 0 | 2 | `ERR_TIME_STALE`, `ERR_TIME_FUTURE` | **VERIFIED** |
| `SYNTH_07_INCONSISTENT_MEASUREMENTS` | `inconsistent_measurements.json` | 2 | 0 | 2 | `ERR_PHYS_INCONSISTENT`, `ERR_PHYS_OUT_OF_BOUNDS` | **VERIFIED** |
| **LIVE REAL CAPTURE** | `raw/aircraft_raw.json` | 19 | 19 | 0 | None (`PASS`) | **VERIFIED** |
