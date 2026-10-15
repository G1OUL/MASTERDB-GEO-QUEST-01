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
    assert "ERR_REQUIRED_NULL" in codes

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

def test_manifest_fixture_resolution():
    """Verify manifest fixture IDs and filenames resolve to real fixture files."""
    manifest_path = os.path.join(FIXTURES_DIR, "manifest.json")
    assert os.path.isfile(manifest_path), f"Manifest file not found: {manifest_path}"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    fixtures = manifest.get("fixtures", [])
    assert len(fixtures) == 7, f"Expected 7 fixtures in manifest, found {len(fixtures)}"

    seen_ids = set()
    seen_files = set()
    for item in fixtures:
        fid = item["fixture_id"]
        fname = item["file_name"]

        assert fid not in seen_ids, f"Duplicate fixture_id: {fid}"
        assert fname not in seen_files, f"Duplicate file_name: {fname}"
        seen_ids.add(fid)
        seen_files.add(fname)

        fpath = os.path.join(FIXTURES_DIR, fname)
        assert os.path.isfile(fpath), f"Manifest fixture file does not exist on disk: {fpath}"

        with open(fpath, "r", encoding="utf-8") as f:
            fdata = json.load(f)
        assert fdata.get("fixture_id") == fid, (
            f"Fixture internal id '{fdata.get('fixture_id')}' != manifest id '{fid}' in {fname}"
        )

def test_declared_exception_codes_exist_in_register_and_validator():
    """Verify every declared expected exception code exists in the exception register and validator metadata."""
    reg_path = os.path.join(PROJECT_ROOT, "validation", "exception_register.json")
    assert os.path.isfile(reg_path), f"Exception register not found: {reg_path}"
    with open(reg_path, "r", encoding="utf-8") as f:
        register_data = json.load(f)

    registered_codes = {entry["code"]: entry for entry in register_data.get("exception_codes", [])}
    validator_metadata = validator_engine.EXCEPTION_METADATA

    manifest_path = os.path.join(FIXTURES_DIR, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for item in manifest.get("fixtures", []):
        raw_expected = item.get("expected_exception_code")
        if raw_expected:
            codes = [c.strip() for c in raw_expected.split("/") if c.strip()]
            for code in codes:
                assert code in registered_codes, (
                    f"Manifest declared code '{code}' in {item['file_name']} not in exception_register.json"
                )
                assert code in validator_metadata, (
                    f"Manifest declared code '{code}' in {item['file_name']} not in validator EXCEPTION_METADATA"
                )

        # Also verify against individual fixture file declarations
        fpath = os.path.join(FIXTURES_DIR, item["file_name"])
        with open(fpath, "r", encoding="utf-8") as f:
            fdata = json.load(f)
        file_expected = fdata.get("expected_exception_code")
        if file_expected:
            codes = [c.strip() for c in file_expected.split("/") if c.strip()]
            for code in codes:
                assert code in registered_codes, (
                    f"Fixture declared code '{code}' in {item['file_name']} not in exception_register.json"
                )
                assert code in validator_metadata, (
                    f"Fixture declared code '{code}' in {item['file_name']} not in validator EXCEPTION_METADATA"
                )

def test_actual_fixture_exceptions_match_manifest():
    """Verify actual fixture exception codes match the manifest's documented expectations."""
    manifest_path = os.path.join(FIXTURES_DIR, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for item in manifest.get("fixtures", []):
        fname = item["file_name"]
        fdata = load_fixture(fname)

        # Confirm file-level declaration aligns with manifest declaration
        assert fdata.get("expected_exception_code") == item.get("expected_exception_code"), (
            f"Fixture {fname} expected_exception_code ({fdata.get('expected_exception_code')}) "
            f"does not match manifest ({item.get('expected_exception_code')})"
        )

        prov = fdata.get("metadata_override")
        if prov is None:
            prov = {
                "source_url": "https://api.adsb.lol/v2/test",
                "utc_acquisition_timestamp": "2026-10-13T12:00:00Z"
            }

        acc, quar, summ = validator_engine.validate_and_process_batch(
            fdata["ac"],
            provenance_meta=prov,
            ref_time_utc="2026-10-13T12:00:00Z",
            source_fixture_name=fname
        )

        assert summ["conservation_verified"] is True

        # Extract actual unique exception codes
        actual_codes = set()
        for q in quar:
            for err in q["errors"]:
                actual_codes.add(err["code"])

        # Extract expected codes
        raw_expected = item.get("expected_exception_code")
        if raw_expected is None:
            expected_codes = set()
        else:
            expected_codes = set(c.strip() for c in raw_expected.split("/") if c.strip())

        assert actual_codes == expected_codes, (
            f"Actual codes {actual_codes} != expected codes {expected_codes} for {fname}"
        )

        # Verify disposition
        if item["expected_disposition"] == "ACCEPT":
            assert len(acc) == len(fdata["ac"])
            assert len(quar) == 0
        elif item["expected_disposition"] == "QUARANTINE":
            assert len(quar) > 0

def test_exception_severity_and_disposition_consistency():
    """Verify exception severity and disposition are consistent across the validator engine and register."""
    reg_path = os.path.join(PROJECT_ROOT, "validation", "exception_register.json")
    with open(reg_path, "r", encoding="utf-8") as f:
        register_data = json.load(f)

    registered_codes = {entry["code"]: entry for entry in register_data.get("exception_codes", [])}
    validator_metadata = validator_engine.EXCEPTION_METADATA

    # Register has exactly 11 stable codes and engine has exactly 11 stable codes
    assert len(registered_codes) == 11, f"Expected 11 codes in register, found {len(registered_codes)}"
    assert len(validator_metadata) == 11, f"Expected 11 codes in validator metadata, found {len(validator_metadata)}"
    assert set(registered_codes.keys()) == set(validator_metadata.keys())

    for code, emeta in validator_metadata.items():
        rmeta = registered_codes[code]
        assert emeta["rule_id"] == rmeta["rule_id"], f"rule_id mismatch on {code}"
        assert emeta["severity"] == rmeta["severity"], f"severity mismatch on {code}"
        assert emeta["disposition"] == rmeta["default_disposition"], f"disposition mismatch on {code}"

    # Verify that every error emitted across all synthetic fixtures adheres to this metadata
    manifest_path = os.path.join(FIXTURES_DIR, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for item in manifest.get("fixtures", []):
        fdata = load_fixture(item["file_name"])
        prov = fdata.get("metadata_override")
        if prov is None:
            prov = {
                "source_url": "https://api.adsb.lol/v2/test",
                "utc_acquisition_timestamp": "2026-10-13T12:00:00Z"
            }

        acc, quar, summ = validator_engine.validate_and_process_batch(
            fdata["ac"],
            provenance_meta=prov,
            ref_time_utc="2026-10-13T12:00:00Z",
            source_fixture_name=item["file_name"]
        )

        for q in quar:
            for err in q["errors"]:
                code = err["code"]
                assert code in validator_metadata, f"Unexpected code {code} emitted"
                expected_meta = validator_metadata[code]
                assert err["severity"] == expected_meta["severity"], (
                    f"Severity mismatch for {code}: emitted {err['severity']} != registered {expected_meta['severity']}"
                )
                assert err["disposition"] == expected_meta["disposition"], (
                    f"Disposition mismatch for {code}: emitted {err['disposition']} != registered {expected_meta['disposition']}"
                )
                assert err["rule_id"] == expected_meta["rule_id"], (
                    f"Rule ID mismatch for {code}: emitted {err['rule_id']} != registered {expected_meta['rule_id']}"
                )

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main(["-v", __file__]))
