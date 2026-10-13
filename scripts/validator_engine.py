#!/usr/bin/env python3
"""
BHIV vNEXT MASTERDB-GEO-QUEST-01: Deterministic Validator & Quarantine Engine
Provides modular, rule-indexed validation with guaranteed record conservation:
  raw_count == accepted_count + quarantined_count

Supports fixed reference timestamp for 100% reproducible test execution.
Differentiates severity (CRITICAL, ERROR, WARNING) and disposition (QUARANTINE, REJECT).
"""

import re
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any, Optional

EXCEPTION_METADATA = {
    "ERR_PROV_MISSING": {"rule_id": "RULE_PROV_01", "severity": "CRITICAL", "disposition": "QUARANTINE"},
    "ERR_REQUIRED_NULL": {"rule_id": "RULE_TYPE_01", "severity": "CRITICAL", "disposition": "QUARANTINE"},
    "ERR_TYPE_MALFORMED": {"rule_id": "RULE_TYPE_02", "severity": "ERROR", "disposition": "QUARANTINE"},
    "ERR_ID_DUPLICATE": {"rule_id": "RULE_ID_01", "severity": "ERROR", "disposition": "QUARANTINE"},
    "ERR_SCHEMA_MISMATCH": {"rule_id": "RULE_SCHEMA_01", "severity": "CRITICAL", "disposition": "QUARANTINE"},
    "ERR_TIME_FUTURE": {"rule_id": "RULE_TIME_01", "severity": "ERROR", "disposition": "QUARANTINE"},
    "ERR_TIME_STALE": {"rule_id": "RULE_TIME_02", "severity": "WARNING", "disposition": "QUARANTINE"},
    "ERR_TIME_ANOMALY": {"rule_id": "RULE_TIME_01", "severity": "ERROR", "disposition": "QUARANTINE"},
    "ERR_PHYS_OUT_OF_BOUNDS": {"rule_id": "RULE_PHYS_01", "severity": "ERROR", "disposition": "QUARANTINE"},
    "ERR_PHYS_INCONSISTENT": {"rule_id": "RULE_PHYS_02", "severity": "ERROR", "disposition": "QUARANTINE"},
    "ERR_CONSERVATION_VIOLATION": {"rule_id": "RULE_CONS_01", "severity": "CRITICAL", "disposition": "REJECT"}
}

def add_diagnostic_error(errors: List[Dict[str, Any]], code: str, message: str) -> None:
    meta = EXCEPTION_METADATA.get(code, {"rule_id": "UNKNOWN", "severity": "ERROR", "disposition": "QUARANTINE"})
    errors.append({
        "rule_id": meta["rule_id"],
        "code": code,
        "severity": meta["severity"],
        "disposition": meta["disposition"],
        "message": message
    })

def check_conservation(raw_count: int, accepted_count: int, quarantined_count: int) -> Dict[str, Any]:
    """
    Enforces the mathematical conservation law:
      raw_count == accepted_count + quarantined_count
    Returns diagnostic details and triggers ERR_CONSERVATION_VIOLATION if violated.
    """
    verified = (raw_count == accepted_count + quarantined_count)
    discrepancy = raw_count - (accepted_count + quarantined_count)
    return {
        "rule_id": "RULE_CONS_01",
        "code": None if verified else "ERR_CONSERVATION_VIOLATION",
        "severity": None if verified else "CRITICAL",
        "disposition": "ACCEPT" if verified else "REJECT",
        "raw_count": raw_count,
        "accepted_count": accepted_count,
        "quarantined_count": quarantined_count,
        "conservation_verified": verified,
        "discrepancy": discrepancy,
        "message": "Conservation law satisfied" if verified else f"Conservation law violated: raw ({raw_count}) != accepted ({accepted_count}) + quarantined ({quarantined_count}), discrepancy={discrepancy}"
    }

def is_valid_hex_id(hex_str: Any) -> bool:
    """Validate 24-bit ICAO aircraft hex address."""
    if not hex_str or not isinstance(hex_str, str):
        return False
    hex_str = hex_str.strip()
    return bool(re.fullmatch(r"^[0-9a-fA-F]{1,6}$", hex_str))

def validate_and_process_batch(
    raw_records: List[Any],
    provenance_meta: Optional[Dict[str, Any]] = None,
    ref_time_utc: Optional[str] = None,
    stale_threshold_seconds: float = 3600.0,
    source_fixture_name: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Deterministically processes and partitions raw aircraft records into
    accepted and quarantined collections.
    """
    if provenance_meta is None:
        provenance_meta = {}

    eval_time = ref_time_utc or datetime.now(timezone.utc).isoformat()
    source_url = provenance_meta.get("source_url")
    acquisition_utc = provenance_meta.get("utc_acquisition_timestamp") or provenance_meta.get("raw_acquisition_utc")

    # Global provenance check
    prov_missing = False
    if not source_url or not acquisition_utc:
        prov_missing = True

    accepted_records: List[Dict[str, Any]] = []
    quarantined_records: List[Dict[str, Any]] = []
    seen_hexes = set()
    exception_counts: Dict[str, int] = {}

    for idx, raw_rec in enumerate(raw_records):
        errors: List[Dict[str, Any]] = []

        # RULE_PROV_01: Ingestion provenance check
        if prov_missing:
            add_diagnostic_error(
                errors,
                "ERR_PROV_MISSING",
                f"Missing provenance source URL or acquisition timestamp (source_url={source_url}, acquisition_utc={acquisition_utc})"
            )

        # RULE_SCHEMA_01: Structure conformance
        if not isinstance(raw_rec, dict):
            add_diagnostic_error(
                errors,
                "ERR_SCHEMA_MISMATCH",
                f"Record at index {idx} is not a valid dictionary object"
            )
            quarantined_records.append({
                "record_index": idx,
                "source_fixture": source_fixture_name,
                "raw_record": raw_rec,
                "errors": errors,
                "quarantined_at_utc": eval_time
            })
            for err in errors:
                exception_counts[err["code"]] = exception_counts.get(err["code"], 0) + 1
            continue

        # RULE_SCHEMA_01 & RULE_TYPE_01: Minimum required schema fields
        raw_hex = raw_rec.get("hex")
        raw_lat = raw_rec.get("lat")
        raw_lon = raw_rec.get("lon")

        if raw_hex is None and raw_lat is None and raw_lon is None and len(raw_rec) < 4:
            add_diagnostic_error(
                errors,
                "ERR_SCHEMA_MISMATCH",
                "Record lacks minimum state vector keys (hex, lat, lon)"
            )

        # RULE_TYPE_01: Null required primary key
        if raw_hex is None or (isinstance(raw_hex, str) and not raw_hex.strip()):
            add_diagnostic_error(
                errors,
                "ERR_REQUIRED_NULL",
                "Required primary identifier 'hex' is null or empty"
            )
            norm_hex = None
        elif not isinstance(raw_hex, str) or not is_valid_hex_id(raw_hex):
            add_diagnostic_error(
                errors,
                "ERR_TYPE_MALFORMED",
                f"Malformed hex identifier format: '{raw_hex}'"
            )
            norm_hex = str(raw_hex).strip().upper()
        else:
            norm_hex = raw_hex.strip().upper()
            # RULE_ID_01: Duplicate transponder identifier within batch
            if norm_hex in seen_hexes:
                add_diagnostic_error(
                    errors,
                    "ERR_ID_DUPLICATE",
                    f"Duplicate transponder hex identifier in batch: '{norm_hex}'"
                )
            else:
                seen_hexes.add(norm_hex)

        # Coordinate parsing & validation
        norm_lat = None
        norm_lon = None
        if raw_lat is None or raw_lon is None:
            add_diagnostic_error(
                errors,
                "ERR_REQUIRED_NULL",
                f"Missing required coordinates (lat={raw_lat}, lon={raw_lon})"
            )
        else:
            try:
                lat_float = float(raw_lat)
                if not (-90.0 <= lat_float <= 90.0):
                    add_diagnostic_error(
                        errors,
                        "ERR_PHYS_OUT_OF_BOUNDS",
                        f"Latitude out of WGS84 bounds: {lat_float}"
                    )
                else:
                    norm_lat = round(lat_float, 6)
            except (ValueError, TypeError):
                add_diagnostic_error(
                    errors,
                    "ERR_TYPE_MALFORMED",
                    f"Non-numeric latitude: '{raw_lat}'"
                )

            try:
                lon_float = float(raw_lon)
                if not (-180.0 <= lon_float <= 180.0):
                    add_diagnostic_error(
                        errors,
                        "ERR_PHYS_OUT_OF_BOUNDS",
                        f"Longitude out of WGS84 bounds: {lon_float}"
                    )
                else:
                    norm_lon = round(lon_float, 6)
            except (ValueError, TypeError):
                add_diagnostic_error(
                    errors,
                    "ERR_TYPE_MALFORMED",
                    f"Non-numeric longitude: '{raw_lon}'"
                )

        # Altitude parsing & normalization
        raw_alt_baro = raw_rec.get("alt_baro")
        norm_alt_baro = None
        is_on_ground = False
        if raw_alt_baro is not None:
            if isinstance(raw_alt_baro, bool):
                add_diagnostic_error(
                    errors,
                    "ERR_TYPE_MALFORMED",
                    f"Altitude cannot be a boolean value: {raw_alt_baro}"
                )
            elif isinstance(raw_alt_baro, str) and raw_alt_baro.strip().lower() == "ground":
                is_on_ground = True
                norm_alt_baro = 0
            else:
                try:
                    alt_val = float(raw_alt_baro)
                    if not (-2000 <= alt_val <= 85000):
                        add_diagnostic_error(
                            errors,
                            "ERR_PHYS_OUT_OF_BOUNDS",
                            f"Altitude outside physical bounds: {alt_val} ft"
                        )
                    else:
                        norm_alt_baro = round(alt_val)
                except (ValueError, TypeError):
                    add_diagnostic_error(
                        errors,
                        "ERR_TYPE_MALFORMED",
                        f"Non-numeric barometric altitude: '{raw_alt_baro}'"
                    )

        # Speed parsing & validation
        raw_gs = raw_rec.get("gs")
        norm_gs = None
        if raw_gs is not None:
            if isinstance(raw_gs, bool):
                add_diagnostic_error(
                    errors,
                    "ERR_TYPE_MALFORMED",
                    f"Ground speed cannot be a boolean value: {raw_gs}"
                )
            else:
                try:
                    gs_val = float(raw_gs)
                    if not (0.0 <= gs_val <= 1500.0):
                        add_diagnostic_error(
                            errors,
                            "ERR_PHYS_OUT_OF_BOUNDS",
                            f"Ground speed out of physical bounds: {gs_val} kts"
                        )
                    else:
                        norm_gs = round(gs_val, 1)
                except (ValueError, TypeError):
                    add_diagnostic_error(
                        errors,
                        "ERR_TYPE_MALFORMED",
                        f"Non-numeric ground speed: '{raw_gs}'"
                    )

        # Heading parsing & validation
        raw_track = raw_rec.get("track")
        norm_track = None
        if raw_track is not None:
            try:
                track_val = float(raw_track)
                if not (0.0 <= track_val <= 360.0):
                    add_diagnostic_error(
                        errors,
                        "ERR_PHYS_OUT_OF_BOUNDS",
                        f"Heading out of compass bounds [0, 360]: {track_val} deg"
                    )
                else:
                    norm_track = round(track_val, 2)
            except (ValueError, TypeError):
                add_diagnostic_error(
                    errors,
                    "ERR_TYPE_MALFORMED",
                    f"Non-numeric heading: '{raw_track}'"
                )

        # Vertical rate
        raw_baro_rate = raw_rec.get("baro_rate")
        norm_baro_rate = None
        if raw_baro_rate is not None:
            try:
                rate_val = float(raw_baro_rate)
                if not (-15000 <= rate_val <= 15000):
                    add_diagnostic_error(
                        errors,
                        "ERR_PHYS_OUT_OF_BOUNDS",
                        f"Vertical rate exceeds aerodynamic limits: {rate_val} fpm"
                    )
                else:
                    norm_baro_rate = round(rate_val)
            except (ValueError, TypeError):
                add_diagnostic_error(
                    errors,
                    "ERR_TYPE_MALFORMED",
                    f"Non-numeric baro rate: '{raw_baro_rate}'"
                )

        # RULE_PHYS_02: Cross-field physical consistency
        if is_on_ground and norm_gs is not None and norm_gs > 120.0:
            add_diagnostic_error(
                errors,
                "ERR_PHYS_INCONSISTENT",
                f"Surface aircraft reported impossible ground speed of {norm_gs} kts (> 120 kts surface limit)"
            )

        # RULE_TIME_01 & RULE_TIME_02: Timestamps and latencies
        raw_seen = raw_rec.get("seen")
        raw_seen_pos = raw_rec.get("seen_pos")

        if raw_seen is not None:
            try:
                seen_val = float(raw_seen)
                if seen_val < 0:
                    add_diagnostic_error(
                        errors,
                        "ERR_TIME_FUTURE",
                        f"Negative observation age (future timestamp anomaly): {seen_val}s"
                    )
                elif seen_val > stale_threshold_seconds:
                    add_diagnostic_error(
                        errors,
                        "ERR_TIME_STALE",
                        f"Observation latency ({seen_val}s) exceeds stale threshold ({stale_threshold_seconds}s)"
                    )
            except (ValueError, TypeError):
                pass

        if raw_seen_pos is not None:
            try:
                seen_pos_val = float(raw_seen_pos)
                if seen_pos_val < 0:
                    add_diagnostic_error(
                        errors,
                        "ERR_TIME_FUTURE",
                        f"Negative position age (future timestamp anomaly): {seen_pos_val}s"
                    )
                elif seen_pos_val > stale_threshold_seconds:
                    add_diagnostic_error(
                        errors,
                        "ERR_TIME_STALE",
                        f"Position latency ({seen_pos_val}s) exceeds stale threshold ({stale_threshold_seconds}s)"
                    )
            except (ValueError, TypeError):
                pass

        # Final record disposition
        if errors:
            quarantined_records.append({
                "record_index": idx,
                "source_fixture": source_fixture_name,
                "raw_record": raw_rec,
                "errors": errors,
                "quarantined_at_utc": eval_time
            })
            for err in errors:
                exception_counts[err["code"]] = exception_counts.get(err["code"], 0) + 1
        else:
            def safe_round(v, decimals=2):
                if v is not None:
                    try:
                        return round(float(v), decimals)
                    except (ValueError, TypeError):
                        return None
                return None

            cleaned_rec = {
                "aircraft_hex_id": norm_hex,
                "callsign": str(raw_rec.get("flight")).strip().upper() if raw_rec.get("flight") else None,
                "registration": str(raw_rec.get("r")).strip().upper() if raw_rec.get("r") else None,
                "aircraft_type_icao": str(raw_rec.get("t")).strip().upper() if raw_rec.get("t") else None,
                "squawk_code": str(raw_rec.get("squawk")).strip() if raw_rec.get("squawk") else None,
                "emitter_category": str(raw_rec.get("category")).strip().upper() if raw_rec.get("category") else None,
                "latitude": norm_lat,
                "longitude": norm_lon,
                "altitude_baro_ft": norm_alt_baro,
                "altitude_geom_ft": safe_round(raw_rec.get("alt_geom"), 0),
                "is_on_ground": is_on_ground,
                "ground_speed_kts": norm_gs,
                "true_track_deg": norm_track,
                "vertical_rate_fpm": norm_baro_rate,
                "position_age_seconds": safe_round(raw_rec.get("seen_pos")),
                "last_seen_seconds": safe_round(raw_rec.get("seen")),
                "distance_from_center_nm": safe_round(raw_rec.get("dst")),
                "bearing_from_center_deg": safe_round(raw_rec.get("dir")),
                "signal_rssi_db": safe_round(raw_rec.get("rssi"), 1),
                "provenance": {
                    "source_system": "adsb.lol",
                    "source_url": source_url or "https://api.adsb.lol/v2/lat/19.0760/lon/72.8777/dist/100",
                    "query_center_lat": 19.0760,
                    "query_center_lon": 72.8777,
                    "query_radius_nm": 100,
                    "raw_acquisition_utc": acquisition_utc or eval_time,
                    "cleaning_pipeline_utc": eval_time,
                    "pipeline_stage": "CLEANED_AND_NORMALIZED",
                    "schema_version": "1.0.0"
                }
            }
            accepted_records.append(cleaned_rec)

    total_input = len(raw_records)
    total_accepted = len(accepted_records)
    total_quarantined = len(quarantined_records)
    conservation_result = check_conservation(total_input, total_accepted, total_quarantined)

    summary = {
        "evaluation_time_utc": eval_time,
        "total_input_records": total_input,
        "accepted_records_count": total_accepted,
        "quarantined_records_count": total_quarantined,
        "conservation_verified": conservation_result["conservation_verified"],
        "conservation_details": conservation_result,
        "exception_counts": exception_counts
    }

    return accepted_records, quarantined_records, summary
