#!/usr/bin/env python3
"""
BHIV vNEXT MASTERDB-GEO-QUEST-01: Synthetic Fixtures Profiling Script
Profiles all synthetic test fixtures separately from real aircraft data.
Calculates actual metrics directly from disk artifacts:
  - Row counts
  - Null counts
  - Duplicate identifiers
  - Invalid values
  - Numerical distributions
  - Provenance completeness
Outputs validation/synthetic_profiling_report.json.
"""

import os
import sys
import json
from datetime import datetime, timezone
from collections import Counter

def profile_synthetic_fixtures(
    fixtures_dir: str = "fixtures/synthetic",
    output_path: str = "validation/synthetic_profiling_report.json"
) -> dict:
    utc_now = datetime.now(timezone.utc).isoformat()
    manifest_path = os.path.join(fixtures_dir, "manifest.json")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    fixture_files = [f["file_name"] for f in manifest["fixtures"]]
    all_records = []
    fixture_summaries = []

    total_records = 0
    hex_list = []
    null_counts = Counter()
    invalid_value_counts = Counter()
    prov_complete_count = 0
    prov_missing_count = 0

    altitudes = []
    speeds = []
    tracks = []
    lats = []
    lons = []

    canonical_fields = [
        "hex", "flight", "r", "t", "squawk", "category", "lat", "lon",
        "alt_baro", "alt_geom", "gs", "track", "baro_rate", "seen", "seen_pos"
    ]

    for item in manifest["fixtures"]:
        fname = item["file_name"]
        fpath = os.path.join(fixtures_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            fdata = json.load(f)

        records = fdata.get("ac", [])
        rec_count = len(records)
        total_records += rec_count

        has_prov = "metadata_override" not in fdata or fdata["metadata_override"].get("source_url") is not None
        if has_prov:
            prov_complete_count += rec_count
        else:
            prov_missing_count += rec_count

        fixture_summaries.append({
            "fixture_id": item["fixture_id"],
            "file_name": fname,
            "description": item["description"],
            "record_count": rec_count,
            "expected_disposition": item["expected_disposition"],
            "expected_exception_code": item["expected_exception_code"],
            "provenance_present": has_prov
        })

        for r in records:
            all_records.append(r)
            # Track nulls
            for fld in canonical_fields:
                if r.get(fld) is None:
                    null_counts[fld] += 1

            # Track identifiers
            h = r.get("hex")
            if h:
                hex_list.append(str(h).strip().upper())
            else:
                invalid_value_counts["null_or_empty_hex"] += 1

            # Coordinates
            lat = r.get("lat")
            lon = r.get("lon")
            if lat is not None:
                try:
                    lat_f = float(lat)
                    if -90.0 <= lat_f <= 90.0:
                        lats.append(lat_f)
                    else:
                        invalid_value_counts["latitude_out_of_bounds"] += 1
                except (ValueError, TypeError):
                    invalid_value_counts["non_numeric_latitude"] += 1

            if lon is not None:
                try:
                    lon_f = float(lon)
                    if -180.0 <= lon_f <= 180.0:
                        lons.append(lon_f)
                    else:
                        invalid_value_counts["longitude_out_of_bounds"] += 1
                except (ValueError, TypeError):
                    invalid_value_counts["non_numeric_longitude"] += 1

            # Kinematics
            gs = r.get("gs")
            if gs is not None:
                try:
                    gs_f = float(gs)
                    if 0.0 <= gs_f <= 1500.0:
                        speeds.append(gs_f)
                    else:
                        invalid_value_counts["speed_out_of_bounds"] += 1
                except (ValueError, TypeError):
                    invalid_value_counts["non_numeric_speed"] += 1

            track = r.get("track")
            if track is not None:
                try:
                    tr_f = float(track)
                    if 0.0 <= tr_f <= 360.0:
                        tracks.append(tr_f)
                    else:
                        invalid_value_counts["heading_out_of_bounds"] += 1
                except (ValueError, TypeError):
                    invalid_value_counts["non_numeric_heading"] += 1

            alt = r.get("alt_baro")
            if alt is not None:
                if isinstance(alt, str) and alt.lower() == "ground":
                    altitudes.append(0)
                else:
                    try:
                        alt_f = float(alt)
                        altitudes.append(alt_f)
                    except (ValueError, TypeError):
                        invalid_value_counts["non_numeric_altitude"] += 1

            # Sensor age
            seen = r.get("seen")
            if seen is not None:
                try:
                    s_f = float(seen)
                    if s_f < 0:
                        invalid_value_counts["negative_sensor_latency"] += 1
                    elif s_f > 3600:
                        invalid_value_counts["stale_sensor_age"] += 1
                except (ValueError, TypeError):
                    pass

    # Check duplicates
    hex_counts = Counter(hex_list)
    duplicate_hexes = {k: v for k, v in hex_counts.items() if v > 1}

    report = {
        "report_name": "BHIV vNEXT MASTERDB-GEO-QUEST-01 Synthetic Fixture Profiling Report",
        "dataset_scope": "SYNTHETIC_TEST_FIXTURES (SEPARATE FROM REAL AIRCRAFT DATA)",
        "profiling_utc": utc_now,
        "fixtures_overview": {
            "total_fixtures": len(manifest["fixtures"]),
            "total_records": total_records,
            "fixture_breakdown": fixture_summaries
        },
        "identifier_metrics": {
            "total_identifiers_present": len(hex_list),
            "unique_identifiers": len(hex_counts),
            "duplicate_identifier_count": sum(v - 1 for v in hex_counts.values() if v > 1),
            "duplicate_identifiers": duplicate_hexes
        },
        "null_value_analysis": {
            "total_records": total_records,
            "null_counts_by_field": dict(null_counts)
        },
        "invalid_value_analysis": {
            "total_anomalies_detected": sum(invalid_value_counts.values()),
            "anomalies_by_category": dict(invalid_value_counts)
        },
        "kinematic_distributions": {
            "altitudes_ft": {
                "count": len(altitudes),
                "min": min(altitudes) if altitudes else None,
                "max": max(altitudes) if altitudes else None,
                "surface_aircraft_count": altitudes.count(0)
            },
            "ground_speeds_kts": {
                "count": len(speeds),
                "min": min(speeds) if speeds else None,
                "max": max(speeds) if speeds else None
            },
            "headings_deg": {
                "count": len(tracks),
                "min": min(tracks) if tracks else None,
                "max": max(tracks) if tracks else None
            },
            "coordinates_wgs84": {
                "latitude_min": min(lats) if lats else None,
                "latitude_max": max(lats) if lats else None,
                "longitude_min": min(lons) if lons else None,
                "longitude_max": max(lons) if lons else None
            }
        },
        "provenance_completeness": {
            "complete_records": prov_complete_count,
            "missing_provenance_records": prov_missing_count,
            "provenance_completeness_rate_pct": round((prov_complete_count / total_records * 100), 2) if total_records > 0 else 0.0
        }
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 70)
    print("SYNTHETIC FIXTURE PROFILING COMPLETE")
    print("=" * 70)
    print(f"Total Fixtures:               {len(manifest['fixtures'])}")
    print(f"Total Synthetic Records:      {total_records}")
    print(f"Duplicate Identifiers:        {report['identifier_metrics']['duplicate_identifier_count']}")
    print(f"Anomalies & Invalid Values:   {report['invalid_value_analysis']['total_anomalies_detected']}")
    print(f"Provenance Completeness:      {report['provenance_completeness']['provenance_completeness_rate_pct']}%")
    print(f"Output Saved To:              {output_path}")
    print("=" * 70)

    return report

if __name__ == "__main__":
    profile_synthetic_fixtures()
