#!/usr/bin/env python3
"""
BHIV vNEXT MASTERDB-GEO-QUEST-01: Executable Quality Validation Test Suite
Uses pytest to verify all deterministic validation rules, synthetic negative fixtures,
exception codes, quarantine routing, warning vs hard-failure dispositions,
and mathematical record conservation (including negative conservation checks).
"""

import os
import sys
import json
import pytest

# Ensure scripts directory is in python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
FIXTURES_DIR = os.path.join(PROJECT_ROOT, "fixtures", "synthetic")

if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import validator_engine
import reconcile_records

def load_fixture(fixture_file: str) -> dict:
    path = os.path.join(FIXTURES_DIR, fixture_file)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_valid_fixture():
    """RULE_PROV_01..PHYS_02: Verify valid record passes all gates and is accepted."""
    data = load_fixture("valid_record.json")
    prov_meta = {
        "source_url": "https://api.adsb.lol/v2/lat/19.0760/lon/72.8777/dist/100",
        "utc_acquisition_timestamp": "2026-10-13T12:00:00Z"
    }
    acc, quar, summ = validator_engine.validate_and_process_batch(
        data["ac"],
        provenance_meta=prov_meta,
        ref_time_utc="2026-10-13T12:00:00Z",
        source_fixture_name="valid_record.json"
    )
    assert len(acc) == 1
    assert len(quar) == 0
    assert summ["conservation_verified"] is True
    assert acc[0]["aircraft_hex_id"] == "800B81"
    assert acc[0]["latitude"] == 19.088691
    assert acc[0]["provenance"]["source_system"] == "adsb.lol"

def test_missing_provenance():
    """RULE_PROV_01: Verify missing provenance metadata is quarantined with ERR_PROV_MISSING."""
    data = load_fixture("missing_provenance.json")
    acc, quar, summ = validator_engine.validate_and_process_batch(
        data["ac"],
        provenance_meta=data.get("metadata_override", {}),
        ref_time_utc="2026-10-13T12:00:00Z",
        source_fixture_name="missing_provenance.json"
    )
    assert len(acc) == 0
    assert len(quar) == 1
    assert summ["conservation_verified"] is True
    codes = [e["code"] for e in quar[0]["errors"]]
    assert "ERR_PROV_MISSING" in codes
    assert quar[0]["errors"][0]["severity"] == "CRITICAL"
    assert quar[0]["errors"][0]["disposition"] == "QUARANTINE"

def test_malformed_types():
    """RULE_TYPE_01 & RULE_TYPE_02: Verify malformed types and null required fields are quarantined."""
    data = load_fixture("malformed_types.json")
    prov_meta = {
        "source_url": "https://api.adsb.lol/v2/test",
        "utc_acquisition_timestamp": "2026-10-13T12:00:00Z"
    }
    acc, quar, summ = validator_engine.validate_and_process_batch(
        data["ac"],
        provenance_meta=prov_meta,
        ref_time_utc="2026-10-13T12:00:00Z",
        source_fixture_name="malformed_types.json"
    )
    assert len(acc) == 0
    assert len(quar) == 1
    assert summ["conservation_verified"] is True
    codes = [e["code"] for e in quar[0]["errors"]]
    assert "ERR_REQUIRED_NULL" in codes
    assert "ERR_TYPE_MALFORMED" in codes

def test_duplicate_identifiers():
    """RULE_ID_01: Verify duplicate transponder identifiers in batch are routed to quarantine."""
    data = load_fixture("duplicate_identifiers.json")
    prov_meta = {
        "source_url": "https://api.adsb.lol/v2/test",
        "utc_acquisition_timestamp": "2026-10-13T12:00:00Z"
    }
    acc, quar, summ = validator_engine.validate_and_process_batch(
        data["ac"],
        provenance_meta=prov_meta,
        ref_time_utc="2026-10-13T12:00:00Z",
        source_fixture_name="duplicate_identifiers.json"
    )
    assert len(acc) == 1
    assert len(quar) == 1
    assert summ["conservation_verified"] is True
    assert quar[0]["errors"][0]["code"] == "ERR_ID_DUPLICATE"
    assert quar[0]["errors"][0]["severity"] == "ERROR"
    assert quar[0]["raw_record"]["flight"] == "SEJ201_DUP"

def test_schema_mismatch():
    """RULE_SCHEMA_01: Verify records missing core schema structure trigger ERR_SCHEMA_MISMATCH."""
    data = load_fixture("schema_mismatch.json")
    prov_meta = {
        "source_url": "https://api.adsb.lol/v2/test",
        "utc_acquisition_timestamp": "2026-10-13T12:00:00Z"
    }
    acc, quar, summ = validator_engine.validate_and_process_batch(
        data["ac"],
        provenance_meta=prov_meta,
        ref_time_utc="2026-10-13T12:00:00Z",
        source_fixture_name="schema_mismatch.json"
    )
    assert len(acc) == 0
    assert len(quar) == 1
    assert summ["conservation_verified"] is True
    codes = [e["code"] for e in quar[0]["errors"]]
    assert "ERR_SCHEMA_MISMATCH" in codes

def test_stale_future_timestamps():
    """RULE_TIME_01 & RULE_TIME_02: Verify stale observation latency (> 3600s) and future negative latencies."""
    data = load_fixture("stale_future_timestamps.json")
    prov_meta = {
        "source_url": "https://api.adsb.lol/v2/test",
        "utc_acquisition_timestamp": "2026-10-13T12:00:00Z"
    }
    acc, quar, summ = validator_engine.validate_and_process_batch(
        data["ac"],
        provenance_meta=prov_meta,
        ref_time_utc="2026-10-13T12:00:00Z",
        stale_threshold_seconds=3600.0,
        source_fixture_name="stale_future_timestamps.json"
    )
    assert len(acc) == 0
    assert len(quar) == 2
    assert summ["conservation_verified"] is True
    codes_rec1 = [e["code"] for e in quar[0]["errors"]]
    codes_rec2 = [e["code"] for e in quar[1]["errors"]]
    assert "ERR_TIME_STALE" in codes_rec1
    assert "ERR_TIME_FUTURE" in codes_rec2

def test_inconsistent_measurements():
    """RULE_PHYS_01 & RULE_PHYS_02: Verify contradictory physics (ground cruise speed, out of bounds heading/climb)."""
    data = load_fixture("inconsistent_measurements.json")
    prov_meta = {
        "source_url": "https://api.adsb.lol/v2/test",
        "utc_acquisition_timestamp": "2026-10-13T12:00:00Z"
    }
    acc, quar, summ = validator_engine.validate_and_process_batch(
        data["ac"],
        provenance_meta=prov_meta,
        ref_time_utc="2026-10-13T12:00:00Z",
        source_fixture_name="inconsistent_measurements.json"
    )
    assert len(acc) == 0
    assert len(quar) == 2
    assert summ["conservation_verified"] is True
    codes_rec1 = [e["code"] for e in quar[0]["errors"]]
    codes_rec2 = [e["code"] for e in quar[1]["errors"]]
    assert "ERR_PHYS_INCONSISTENT" in codes_rec1
    assert "ERR_PHYS_OUT_OF_BOUNDS" in codes_rec2

def test_warning_vs_hard_failure_disposition():
    """RULE_TIME_02 vs RULE_TYPE_01: Verify warning disposition and severity handling."""
    meta_stale = validator_engine.EXCEPTION_METADATA["ERR_TIME_STALE"]
    meta_required = validator_engine.EXCEPTION_METADATA["ERR_REQUIRED_NULL"]
    meta_conserv = validator_engine.EXCEPTION_METADATA["ERR_CONSERVATION_VIOLATION"]

    assert meta_stale["severity"] == "WARNING"
    assert meta_stale["disposition"] == "QUARANTINE"

    assert meta_required["severity"] == "CRITICAL"
    assert meta_required["disposition"] == "QUARANTINE"

    assert meta_conserv["severity"] == "CRITICAL"
    assert meta_conserv["disposition"] == "REJECT"

def test_conservation_rule_synthetic():
    """RULE_CONS_01: Verify conservation law across all synthetic fixtures (per-fixture and combined batch)."""
    fixture_files = [
        "valid_record.json",
        "missing_provenance.json",
        "malformed_types.json",
        "duplicate_identifiers.json",
        "schema_mismatch.json",
        "stale_future_timestamps.json",
        "inconsistent_measurements.json"
    ]

    # Part A: Per-fixture evaluation against documented expected counts (2 accepted, 8 quarantined)
    per_fixture_acc = 0
    per_fixture_quar = 0
    for fn in fixture_files:
        fix = load_fixture(fn)
        prov = fix.get("metadata_override")
        if prov is None:
            prov = {"source_url": "https://api.adsb.lol/v2/test", "utc_acquisition_timestamp": "2026-10-13T12:00:00Z"}
        acc_i, quar_i, summ_i = validator_engine.validate_and_process_batch(
            fix["ac"],
            provenance_meta=prov,
            ref_time_utc="2026-10-13T12:00:00Z",
            source_fixture_name=fn
        )
        assert summ_i["conservation_verified"] is True
        assert len(fix["ac"]) == len(acc_i) + len(quar_i)
        per_fixture_acc += len(acc_i)
        per_fixture_quar += len(quar_i)

    assert per_fixture_acc == 2  # Matches documented fixture matrix (valid_record: 1, duplicate: 1)
    assert per_fixture_quar == 8  # Matches documented fixture matrix (sum of quarantined)
    assert per_fixture_acc + per_fixture_quar == 10

    # Part B: Combined batch evaluation under uniform valid batch provenance (3 accepted, 7 quarantined)
    all_raw = []
    for fn in fixture_files:
        fix = load_fixture(fn)
        all_raw.extend(fix["ac"])

    prov_meta = {
        "source_url": "https://api.adsb.lol/v2/test",
        "utc_acquisition_timestamp": "2026-10-13T12:00:00Z"
    }
    acc, quar, summ = validator_engine.validate_and_process_batch(
        all_raw,
        provenance_meta=prov_meta,
        ref_time_utc="2026-10-13T12:00:00Z",
        source_fixture_name="combined_synthetic"
    )

    total_raw = len(all_raw)
    assert total_raw == 10
    assert summ["conservation_verified"] is True
    assert total_raw == len(acc) + len(quar)
    # Under uniform valid batch provenance, SYNTH_02's valid telemetry is accepted, yielding exactly 3 accepted and 7 quarantined:
    assert len(acc) == 3
    assert len(quar) == 7

def test_conservation_enforcement_negative():
    """RULE_CONS_01: Negative test verifying that count imbalance triggers ERR_CONSERVATION_VIOLATION."""
    # Test valid balance
    valid_res = validator_engine.check_conservation(raw_count=19, accepted_count=19, quarantined_count=0)
    assert valid_res["conservation_verified"] is True
    assert valid_res["code"] is None
    assert valid_res["discrepancy"] == 0

    # Test imbalanced counts (e.g. dropped records or unhandled leak)
    dropped_res = validator_engine.check_conservation(raw_count=20, accepted_count=12, quarantined_count=7)
    assert dropped_res["conservation_verified"] is False
    assert dropped_res["code"] == "ERR_CONSERVATION_VIOLATION"
    assert dropped_res["severity"] == "CRITICAL"
    assert dropped_res["disposition"] == "REJECT"
    assert dropped_res["discrepancy"] == 1  # 20 - (12 + 7) = 1 record lost

    # Test double counted records
    inflated_res = validator_engine.check_conservation(raw_count=10, accepted_count=8, quarantined_count=4)
    assert inflated_res["conservation_verified"] is False
    assert inflated_res["code"] == "ERR_CONSERVATION_VIOLATION"
    assert inflated_res["discrepancy"] == -2

def test_real_dataset_compatibility():
    """Verify existing 19 live real aircraft records pass 100% cleanly without quarantine."""
    raw_path = os.path.join(PROJECT_ROOT, "raw", "aircraft_raw.json")
    meta_path = os.path.join(PROJECT_ROOT, "raw", "acquisition_metadata.json")

    with open(raw_path, "r", encoding="utf-8") as f:
        raw_payload = json.load(f)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta_payload = json.load(f)

    acc, quar, summ = validator_engine.validate_and_process_batch(
        raw_payload["ac"],
        provenance_meta=meta_payload,
        source_fixture_name="aircraft_raw.json"
    )

    assert len(raw_payload["ac"]) == 19
    assert len(acc) == 19
    assert len(quar) == 0
    assert summ["conservation_verified"] is True
    assert summ["exception_counts"] == {}

def test_reconciliation_contract():
    """Verify reconciliation utility executes cleanly and enforces version separation."""
    report = reconcile_records.reconcile()
    assert report["version_alignment"]["versions_distinct"] is True
    assert report["version_alignment"]["dataset_version"] == "1.0.0-candidate"
    assert report["version_alignment"]["schema_version"] == "1.0.0"
    assert report["count_reconciliation"]["submitted_candidate_records"] == 19
    assert report["count_reconciliation"]["conservation_equation_verified"] is True
    assert report["field_schema_reconciliation"]["field_mismatches_count"] == 0
    assert report["masterdb_integration_boundaries"]["real_integration_evidence_exists"] is False

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main(["-v", __file__]))
