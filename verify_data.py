#!/usr/bin/env python3
import csv
import os
from datetime import datetime

DATA_DIR = "data"
FILES = {
    "service_metrics": "service_metrics.csv",
    "application_logs": "application_logs.csv",
    "deployments": "deployments.csv",
    "incidents": "incidents.csv",
    "service_dependencies": "service_dependencies.csv"
}

EXPECTED_HEADERS = {
    "service_metrics": ["timestamp", "service_name", "cpu_percent", "memory_percent", "request_count", "error_rate", "latency_ms", "db_connections"],
    "application_logs": ["timestamp", "service_name", "severity", "error_code", "message", "trace_id"],
    "deployments": ["deployment_id", "service_name", "version", "deployment_time", "change_type", "changed_components"],
    "incidents": ["incident_id", "timestamp", "severity", "service_name", "symptoms", "actual_root_cause", "resolution", "duration_minutes"],
    "service_dependencies": ["source_service", "target_service", "dependency_type"]
}

def main():
    results = {}
    
    print("=" * 60)
    print("AEGIS INCIDENT CONTINUITY - TELEMETRY DATASET VALIDATION")
    print("=" * 60)
    
    # 1 & 2. Verify all five CSV files exist and print sizes
    print("\n[STEP 1 & 2] Verifying File Existence and Sizes:")
    existence_pass = True
    for key, filename in FILES.items():
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  - {filename}: EXISTS ({size} bytes)")
        else:
            print(f"  - {filename}: MISSING")
            existence_pass = False
    
    results["1. File Existence"] = "PASS" if existence_pass else "FAIL"
    results["2. File Size Tracking"] = "PASS" if existence_pass else "FAIL"
    
    if not existence_pass:
        print("\n[CRITICAL ERROR] One or more CSV files are missing. Aborting validation.")
        print_summary(results)
        return

    # 3. Print row counts and exact headers
    print("\n[STEP 3] Row Counts & Headers:")
    row_counts = {}
    headers = {}
    for key, filename in FILES.items():
        path = os.path.join(DATA_DIR, filename)
        with open(path, "r", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            headers[key] = header
            rows = list(reader)
            row_counts[key] = len(rows)
            print(f"  - {filename}: {len(rows)} rows | Columns: {header}")
            
    results["3. Row Counts & Columns Print"] = "PASS"

    # 4. Verify that all headers exactly match the BigQuery schemas
    print("\n[STEP 4] Verifying BigQuery Schema Header Matches:")
    schema_pass = True
    for key, filename in FILES.items():
        if headers[key] == EXPECTED_HEADERS[key]:
            print(f"  - {filename}: MATCHES BigQuery schema")
        else:
            print(f"  - {filename}: MISMATCH! Expected: {EXPECTED_HEADERS[key]} | Found: {headers[key]}")
            schema_pass = False
    
    results["4. BigQuery Schema Matching"] = "PASS" if schema_pass else "FAIL"

    # 5. Verify release-4821 exists for order-service on 2026-08-17 08:00:00
    print("\n[STEP 5] Checking for deployment release-4821:")
    deploy_path = os.path.join(DATA_DIR, FILES["deployments"])
    r4821_found = False
    with open(deploy_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row["service_name"] == "order-service" and 
                row["version"] == "release-4821" and 
                row["deployment_time"] == "2026-08-17 08:00:00"):
                print(f"  - [FOUND] Deploy ID: {row['deployment_id']} | Time: {row['deployment_time']} | Config: {row['changed_components']}")
                r4821_found = True
                break
    
    results["5. release-4821 Deployment Check"] = "PASS" if r4821_found else "FAIL"

    # 6. Verify release-4822 exists for order-service on 2026-08-17 20:00:00
    print("\n[STEP 6] Checking for deployment release-4822:")
    r4822_found = False
    with open(deploy_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row["service_name"] == "order-service" and 
                row["version"] == "release-4822" and 
                row["deployment_time"] == "2026-08-17 20:00:00"):
                print(f"  - [FOUND] Deploy ID: {row['deployment_id']} | Time: {row['deployment_time']} | Config: {row['changed_components']}")
                r4822_found = True
                break
                
    results["6. release-4822 Deployment Check"] = "PASS" if r4822_found else "FAIL"

    # 7. Verify the P1 incident INC-006 exists
    print("\n[STEP 7] Checking Incidents Registry for INC-006:")
    inc_path = os.path.join(DATA_DIR, FILES["incidents"])
    inc_006_found = False
    with open(inc_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["incident_id"] == "INC-006":
                print(f"  - [FOUND] INC-006 | Service: {row['service_name']} | Severity: {row['severity']} | Root Cause: {row['actual_root_cause']}")
                inc_006_found = True
                break
                
    results["7. P1 INC-006 Registry Check"] = "PASS" if inc_006_found else "FAIL"

    # 8. Verify P1 metrics show db_connections capped at 5 and elevated latency/errors
    print("\n[STEP 8] Verifying P1 Telemetry Metrics (order-service database pool limit):")
    metrics_path = os.path.join(DATA_DIR, FILES["service_metrics"])
    metrics_verify_pass = False
    peak_points = 0
    with open(metrics_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["service_name"] == "order-service" and "2026-08-17" in row["timestamp"]:
                ts = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
                # Check peak hours when connection pool will exhaust
                if (11 <= ts.hour <= 14) or (18 <= ts.hour <= 19):
                    db_conn = int(row["db_connections"])
                    latency = float(row["latency_ms"])
                    err_rate = float(row["error_rate"])
                    
                    if db_conn == 5 and latency > 4000.0 and err_rate > 0.5:
                        peak_points += 1
                        
    # If we have matches in multiple intervals, metric correlation checks out
    if peak_points > 0:
        print(f"  - [PASS] Found {peak_points} metric intervals on Aug 17 where database connections capped at 5 with latency > 4s and error rate > 50%.")
        metrics_verify_pass = True
    else:
        print("  - [FAIL] No metric intervals on Aug 17 matched the pool saturation criteria (connections=5, latency>4s, error_rate>50%).")
        
    results["8. P1 Metric Starvation Correlation"] = "PASS" if metrics_verify_pass else "FAIL"

    # 9. Verify application logs contain the expected database connection pool timeout errors
    print("\n[STEP 9] Verifying Application Logs for Database Pool Timeout Errors:")
    logs_path = os.path.join(DATA_DIR, FILES["application_logs"])
    logs_verify_pass = False
    error_logs_count = 0
    
    with open(logs_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "2026-08-17" in row["timestamp"] and row["service_name"] == "order-service":
                if row["error_code"] == "ERR-DB-POOL-TIMEOUT" and "HikariPool" in row["message"] and "timed out" in row["message"]:
                    error_logs_count += 1
                    if error_logs_count <= 2:
                        print(f"  - Example error log: [{row['timestamp']}] {row['message']} (Trace: {row['trace_id']})")
                        
    if error_logs_count > 0:
        print(f"  - [PASS] Found {error_logs_count} trace-correlated pool timeout logs (ERR-DB-POOL-TIMEOUT) during the incident window.")
        logs_verify_pass = True
    else:
        print("  - [FAIL] Did not locate expected ERR-DB-POOL-TIMEOUT connection pool logs on Aug 17.")
        
    results["9. P1 Logs Timeout Verification"] = "PASS" if logs_verify_pass else "FAIL"

    # 10. Print PASS/FAIL summary
    print_summary(results)

def print_summary(results):
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    all_passed = True
    for test, status in results.items():
        print(f"  {test:<40} : [{status}]")
        if status != "PASS":
            all_passed = False
            
    print("-" * 60)
    if all_passed:
        print("  FINAL STATUS: [PASS] - All telemetry data validation checks passed.")
    else:
        print("  FINAL STATUS: [FAIL] - One or more validation checks failed.")
    print("=" * 60)

if __name__ == "__main__":
    main()
