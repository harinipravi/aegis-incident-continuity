#!/usr/bin/env python3
import csv
import datetime
import math
import os
import random

# Set deterministic random seed
random.seed(42)

# Configuration & Constants
START_DATE = datetime.datetime(2026, 7, 19, 0, 0, 0)
END_DATE = datetime.datetime(2026, 8, 18, 0, 0, 0)
INTERVAL_MINUTES = 5
SERVICES = ["gateway-service", "auth-service", "order-service", "inventory-service", "payment-service"]

# Directory setup
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Helper function to generate trace IDs
def generate_trace_id(length=16):
    return "".join(random.choices("0123456789abcdef", k=length))

# --- 1. Service Dependencies ---
DEPENDENCIES = [
    {"source_service": "gateway-service", "target_service": "auth-service", "dependency_type": "HTTP"},
    {"source_service": "gateway-service", "target_service": "order-service", "dependency_type": "HTTP"},
    {"source_service": "order-service", "target_service": "inventory-service", "dependency_type": "gRPC"},
    {"source_service": "order-service", "target_service": "payment-service", "dependency_type": "gRPC"},
]

def write_service_dependencies():
    path = os.path.join(DATA_DIR, "service_dependencies.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        # Match BigQuery schema exactly: source_service,target_service,dependency_type
        writer.writerow(["source_service", "target_service", "dependency_type"])
        for dep in DEPENDENCIES:
            writer.writerow([dep["source_service"], dep["target_service"], dep["dependency_type"]])
    print(f"Created: {path}")

# --- 2. Incidents ---
INCIDENTS = [
    {
        "incident_id": "INC-001",
        "timestamp": "2026-07-22 12:00:00",
        "severity": "P2",
        "service_name": "auth-service",
        "symptoms": "Elevated memory utilization, JVM garbage collection latency spikes, OutOfMemoryError exceptions, and auth-service container restarts causing HTTP 500 errors on gateway",
        "actual_root_cause": "Memory leak in JWT token cache due to missing expiration/eviction policy on cache entries",
        "resolution": "Triggered manual container restart, updated JVM memory cache eviction policy, and updated configuration to apply TTL",
        "duration_minutes": 360
    },
    {
        "incident_id": "INC-002",
        "timestamp": "2026-07-28 09:00:00",
        "severity": "P2",
        "service_name": "payment-service",
        "symptoms": "Stripe API checkout processing failures, request processing thread blockages, and high request latency (5000ms timeout) propagating to order-service and gateway-service",
        "actual_root_cause": "DNS resolution timeouts and failures on calls to external payment gateway provider api.stripe.com",
        "resolution": "Configured internal DNS fallback servers and reduced HTTP socket connection timeout values",
        "duration_minutes": 150
    },
    {
        "incident_id": "INC-003",
        "timestamp": "2026-08-03 10:00:00",
        "severity": "P3",
        "service_name": "inventory-service",
        "symptoms": "Immediate 100% error rate on item availability checks, blocking all order creation checkouts, immediately following deployment of release-4710",
        "actual_root_cause": "Bug in code release-4710 where the inventory database repository class dependency was not properly instantiated in InventoryController",
        "resolution": "Rolled back inventory-service to release-4711 (restoring stable release-4709 build)",
        "duration_minutes": 45
    },
    {
        "incident_id": "INC-004",
        "timestamp": "2026-08-08 17:00:00",
        "severity": "P2",
        "service_name": "order-service",
        "symptoms": "CPU saturation (98%) on order-service, high active DB connections, database performance degradation, and order request latencies spiking to over 2200ms",
        "actual_root_cause": "Ad-hoc dashboard analytics query launched on the orders table without an index on customer_id, causing full table scans under load",
        "resolution": "Terminated long-running query and created database index orders_customer_id_idx on column customer_id",
        "duration_minutes": 180
    },
    {
        "incident_id": "INC-005",
        "timestamp": "2026-08-12 14:00:00",
        "severity": "P3",
        "service_name": "inventory-service",
        "symptoms": "Intermittent latency spikes up to 2400ms and connection timeouts (DeadlineExceeded) when ordering-service calls inventory-service",
        "actual_root_cause": "14.5% packet loss on virtual switch in availability zone us-east-1a affecting internal gRPC calls",
        "resolution": "VPC route tables updated to bypass degraded network path in AWS availability zone",
        "duration_minutes": 120
    },
    {
        "incident_id": "INC-006",
        "timestamp": "2026-08-17 08:00:00",
        "severity": "P1",
        "service_name": "order-service",
        "symptoms": "Severe HTTP 504 gateway timeout and HTTP 500 error rate spikes on checkouts during morning (11:00-15:00) and evening (18:00-19:30) traffic peaks; order-service latency spikes to 5s",
        "actual_root_cause": "Deployment release-4821 misconfigured Hikari connection pool size db.pool.max_active to 5 (down from 50), starving threads during peak business hours",
        "resolution": "Rolled back order-service deployment to release-4822, restoring db.pool.max_active to 50",
        "duration_minutes": 720
    }
]

def write_incidents():
    path = os.path.join(DATA_DIR, "incidents.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        # Match BigQuery schema exactly: incident_id,timestamp,severity,service_name,symptoms,actual_root_cause,resolution,duration_minutes
        writer.writerow(["incident_id", "timestamp", "severity", "service_name", "symptoms", "actual_root_cause", "resolution", "duration_minutes"])
        for inc in INCIDENTS:
            writer.writerow([
                inc["incident_id"],
                inc["timestamp"],
                inc["severity"],
                inc["service_name"],
                inc["symptoms"],
                inc["actual_root_cause"],
                inc["resolution"],
                inc["duration_minutes"]
            ])
    print(f"Created: {path}")

# --- 3. Deployments ---
def generate_deployments():
    deployments = []
    
    def add_deploy(dt, service, version, change_type, changed_components):
        deployments.append({
            "deployment_id": f"DEP-{len(deployments)+1000:04d}",
            "service_name": service,
            "version": version,
            "deployment_time": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "change_type": change_type,
            "changed_components": changed_components
        })

    # Main P1 incident deployments (order-service)
    # Bad deployment that triggers P1:
    add_deploy(
        datetime.datetime(2026, 8, 17, 8, 0, 0),
        "order-service",
        "release-4821",
        "CONFIG_UPDATE",
        '{"db.pool.max_active": 5, "db.pool.timeout_ms": 5000}'
    )
    # Rollback/hotfix deployment that resolves P1:
    add_deploy(
        datetime.datetime(2026, 8, 17, 20, 0, 0),
        "order-service",
        "release-4822",
        "ROLLBACK",
        '{"db.pool.max_active": 50, "db.pool.timeout_ms": 5000}'
    )

    # Historical Incident 3 deployments (inventory-service)
    # Bad release:
    add_deploy(
        datetime.datetime(2026, 8, 3, 10, 0, 0),
        "inventory-service",
        "release-4710",
        "CODE_DEPLOY",
        '{"image": "inventory-service:v1.2.1-buggy"}'
    )
    # Rollback:
    add_deploy(
        datetime.datetime(2026, 8, 3, 10, 45, 0),
        "inventory-service",
        "release-4711",
        "ROLLBACK",
        '{"image": "inventory-service:v1.2.0"}'
    )

    # Generate some periodic normal deployments across services
    for service in SERVICES:
        for i in range(1, 10):
            day_offset = i * 3 + random.randint(0, 2)
            if day_offset >= 30:
                continue
            
            deploy_date = START_DATE + datetime.timedelta(days=day_offset, hours=random.randint(2, 6))
            
            # Avoid deployment times overlapping exactly with our incident times
            if deploy_date.date() == datetime.date(2026, 8, 17) and service == "order-service":
                continue
            if deploy_date.date() == datetime.date(2026, 8, 3) and service == "inventory-service":
                continue

            version = f"release-{random.randint(4000, 4800)}"
            change_type = random.choice(["CODE_DEPLOY", "CONFIG_UPDATE"])
            changed_components = f'{{"image": "{service}:{version}"}}' if change_type == "CODE_DEPLOY" else '{"env.updated": "true"}'
            
            add_deploy(deploy_date, service, version, change_type, changed_components)

    # Sort deployments by deployment_time
    deployments.sort(key=lambda x: x["deployment_time"])
    
    path = os.path.join(DATA_DIR, "deployments.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        # Match BigQuery schema exactly: deployment_id,service_name,version,deployment_time,change_type,changed_components
        writer.writerow(["deployment_id", "service_name", "version", "deployment_time", "change_type", "changed_components"])
        for d in deployments:
            writer.writerow([
                d["deployment_id"],
                d["service_name"],
                d["version"],
                d["deployment_time"],
                d["change_type"],
                d["changed_components"]
            ])
    print(f"Created: {path}")

# --- 4. Service Metrics & Logs Generator ---
def get_incident_status(dt):
    """Returns a dict mapping incident IDs to their active state at the given dt."""
    res = {}
    
    # INC-001 Memory leak auth-service
    t_start = datetime.datetime(2026, 7, 22, 12, 0, 0)
    t_end = datetime.datetime(2026, 7, 22, 18, 0, 0)
    res["INC-001"] = t_start <= dt < t_end

    # INC-002 External Payment Outage
    t_start = datetime.datetime(2026, 7, 28, 9, 0, 0)
    t_end = datetime.datetime(2026, 7, 28, 11, 30, 0)
    res["INC-002"] = t_start <= dt < t_end

    # INC-003 Inventory buggy release
    t_start = datetime.datetime(2026, 8, 3, 10, 0, 0)
    t_end = datetime.datetime(2026, 8, 3, 10, 45, 0)
    res["INC-003"] = t_start <= dt < t_end

    # INC-004 Database CPU Saturation order-service
    t_start = datetime.datetime(2026, 8, 8, 17, 0, 0)
    t_end = datetime.datetime(2026, 8, 8, 20, 0, 0)
    res["INC-004"] = t_start <= dt < t_end

    # INC-005 Inventory network packet loss
    t_start = datetime.datetime(2026, 8, 12, 14, 0, 0)
    t_end = datetime.datetime(2026, 8, 12, 16, 0, 0)
    res["INC-005"] = t_start <= dt < t_end

    # INC-006 Order-service connection pool (Main P1)
    t_start = datetime.datetime(2026, 8, 17, 8, 0, 0)
    t_end = datetime.datetime(2026, 8, 17, 20, 0, 0)
    res["INC-006"] = t_start <= dt < t_end

    return res

def generate_metrics_and_logs():
    metrics_path = os.path.join(DATA_DIR, "service_metrics.csv")
    logs_path = os.path.join(DATA_DIR, "application_logs.csv")
    
    f_metrics = open(metrics_path, "w", newline="")
    f_logs = open(logs_path, "w", newline="")
    
    writer_metrics = csv.writer(f_metrics)
    writer_logs = csv.writer(f_logs)
    
    # Match BigQuery schema exactly:
    # service_metrics: timestamp,service_name,cpu_percent,memory_percent,request_count,error_rate,latency_ms,db_connections
    # application_logs: timestamp,service_name,severity,error_code,message,trace_id
    writer_metrics.writerow(["timestamp", "service_name", "cpu_percent", "memory_percent", "request_count", "error_rate", "latency_ms", "db_connections"])
    writer_logs.writerow(["timestamp", "service_name", "severity", "error_code", "message", "trace_id"])
    
    current_time = START_DATE
    delta = datetime.timedelta(minutes=INTERVAL_MINUTES)
    
    auth_mem_leak_start = datetime.datetime(2026, 7, 22, 12, 0, 0)
    log_count = 0
    
    print("Generating metrics and logs...")
    
    while current_time < END_DATE:
        ts_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        incidents_active = get_incident_status(current_time)
        
        # 1. Compute diurnal base traffic factor
        hour = current_time.hour + current_time.minute / 60.0
        traffic_factor = 0.5 * (math.sin(2 * math.pi * (hour - 8) / 24) + 0.35 * math.sin(4 * math.pi * (hour - 18) / 24) + 1.25)
        if current_time.weekday() >= 5:
            traffic_factor *= 0.8
            
        traffic_factor += random.uniform(-0.05, 0.05)
        traffic_factor = max(0.1, traffic_factor)
        
        gateway_requests = int(300 * traffic_factor)
        
        # --- Auth Service ---
        auth_req = int(gateway_requests * 0.4)
        auth_cpu = 15.0 + auth_req * 0.08 + random.uniform(-2.0, 2.0)
        auth_mem = 48.0 + random.uniform(-0.5, 0.5)
        auth_err_rate = 0.0
        auth_lat = 25.0 + auth_req * 0.05 + random.uniform(-2.0, 2.0)
        auth_db_conn = int(2 + auth_req * 0.02)
        
        # Apply Incident 1: Memory leak
        if incidents_active["INC-001"]:
            elapsed_sec = (current_time - auth_mem_leak_start).total_seconds()
            progress = elapsed_sec / 21600.0  # 6 hours
            
            auth_mem = 48.0 + progress * 50.0 + random.uniform(-0.2, 0.2)
            
            if progress > 0.85:
                auth_cpu = 85.0 + random.uniform(-5.0, 5.0)
                auth_lat = 150.0 + (progress - 0.85) * 2000.0
                auth_err_rate = min(0.95, (progress - 0.85) * 0.8)
            
            # Write leak logs
            if progress > 0.5 and current_time.minute % 15 == 0:
                log_count += 1
                writer_logs.writerow([
                    ts_str, "auth-service", "WARN", "",
                    f"GC overhead limit is reaching threshold. JVM heap memory utilization at {auth_mem:.1f}%. Active sessions: {int(2000 + progress*1000)}",
                    generate_trace_id()
                ])
            if progress > 0.9 and current_time.minute % 5 == 0:
                trace = generate_trace_id()
                log_count += 1
                writer_logs.writerow([
                    ts_str, "auth-service", "ERROR", "ERR-OOM",
                    "java.lang.OutOfMemoryError: Java heap space. Dumped heap to /tmp/java_pid2051.hprof",
                    trace
                ])
                log_count += 1
                writer_logs.writerow([
                    ts_str, "gateway-service", "ERROR", "ERR-DOWNSTREAM-TIMEOUT",
                    "Failed to authenticate inbound token: downstream auth-service timeout. Status 500. Route: GET /api/v1/user/profile",
                    trace
                ])
        
        # Recovery/reboot immediately after INC-001
        if current_time >= datetime.datetime(2026, 7, 22, 18, 0, 0) and current_time < datetime.datetime(2026, 7, 22, 18, 20, 0):
            if current_time == datetime.datetime(2026, 7, 22, 18, 0, 0):
                auth_mem = 22.0
                auth_cpu = 75.0
                auth_lat = 300.0
                auth_err_rate = 0.30
                
                log_count += 1
                writer_logs.writerow([ts_str, "auth-service", "INFO", "", "JVM starting up. Version: OpenJDK 17.0.8. Max Heap size: 2048MB", ""])
                log_count += 1
                writer_logs.writerow([ts_str, "auth-service", "INFO", "", "AuthTokenValidator cache initialized successfully. Cache size capacity: 10000", ""])
            else:
                auth_mem = 40.0
                auth_cpu = 30.0
                auth_lat = 40.0
                auth_err_rate = 0.0
        
        # --- Inventory Service ---
        inv_req = int(gateway_requests * 0.72)
        inv_cpu = 12.0 + inv_req * 0.05 + random.uniform(-1.0, 1.0)
        inv_mem = 55.0 + random.uniform(-0.5, 0.5)
        inv_err_rate = 0.0
        inv_lat = 18.0 + inv_req * 0.03 + random.uniform(-1.0, 1.0)
        inv_db_conn = int(3 + inv_req * 0.015)

        # Apply Incident 3: Bad Code Release
        if incidents_active["INC-003"]:
            inv_err_rate = 0.95
            inv_cpu = 8.0 + random.uniform(-1.0, 1.0)
            inv_lat = 4.0 + random.uniform(-1.0, 1.0)
            
            if current_time.minute % 5 == 0:
                for _ in range(2):
                    trace = generate_trace_id()
                    log_count += 1
                    writer_logs.writerow([
                        ts_str, "inventory-service", "ERROR", "ERR-NPE",
                        "java.lang.NullPointerException: Cannot invoke 'com.aegis.inventory.InventoryService.getItemStock(String)' because 'this.inventoryStore' is null at com.aegis.inventory.InventoryController.checkAvailability(InventoryController.java:45)",
                        trace
                    ])
                    log_count += 1
                    writer_logs.writerow([
                        ts_str, "order-service", "ERROR", "ERR-DOWNSTREAM-FAIL",
                        f"Failed downstream gRPC call to inventory-service. checkAvailability failed. Trace ID: {trace}",
                        trace
                    ])
                    log_count += 1
                    writer_logs.writerow([
                        ts_str, "gateway-service", "ERROR", "ERR-CHECKOUT-FAIL",
                        f"Internal Server Error on route POST /api/v1/orders/checkout. Trace ID: {trace}",
                        trace
                    ])
        
        # Apply Incident 5: Network packet loss / AZ jitter
        if incidents_active["INC-005"]:
            inv_lat = random.choice([20.0, 150.0, 1200.0, 2400.0]) + random.uniform(0, 100)
            inv_err_rate = random.uniform(0.08, 0.20)
            inv_cpu = 18.0 + random.uniform(-2.0, 2.0)
            
            if current_time.minute % 10 == 0:
                trace = generate_trace_id()
                log_count += 1
                writer_logs.writerow([
                    ts_str, "inventory-service", "WARN", "",
                    "VPC network packet retransmission rate is high on eth0: 14.5% packet loss. Potential routing issue in AWS AZ us-east-1a.",
                    ""
                ])
                log_count += 1
                writer_logs.writerow([
                    ts_str, "order-service", "ERROR", "ERR-NETWORK-TIMEOUT",
                    f"gRPC call to inventory-service timed out: DeadlineExceeded. Timeout set to 1500ms. Trace ID: {trace}",
                    trace
                ])
                log_count += 1
                writer_logs.writerow([
                    ts_str, "gateway-service", "ERROR", "ERR-GATEWAY-TIMEOUT",
                    f"Upstream Timeout on POST /api/v1/orders. Trace ID: {trace}",
                    trace
                ])

        # --- Payment Service ---
        pay_req = int(gateway_requests * 0.18)
        pay_cpu = 8.0 + pay_req * 0.06 + random.uniform(-1.0, 1.0)
        pay_mem = 40.0 + random.uniform(-0.5, 0.5)
        pay_err_rate = 0.0
        pay_lat = 120.0 + pay_req * 0.1 + random.uniform(-10.0, 10.0)
        pay_db_conn = int(1 + pay_req * 0.01)
        
        # Apply Incident 2: External Payment Gateway DNS/timeout
        if incidents_active["INC-002"]:
            pay_lat = 5000.0 + random.uniform(0.0, 50.0)
            pay_err_rate = 0.90
            pay_cpu = 15.0
            
            if current_time.minute % 10 == 0:
                trace = generate_trace_id()
                log_count += 1
                writer_logs.writerow([
                    ts_str, "payment-service", "ERROR", "ERR-EXTERNAL-TIMEOUT",
                    "ConnectTimeoutException: Connect to api.stripe.com:443 failed: connect timed out. DNS resolution took 120ms.",
                    trace
                ])
                log_count += 1
                writer_logs.writerow([
                    ts_str, "order-service", "ERROR", "ERR-DOWNSTREAM-FAIL",
                    f"Payment failed for Order. Downstream payment-service error. Trace ID: {trace}",
                    trace
                ])
                log_count += 1
                writer_logs.writerow([
                    ts_str, "gateway-service", "ERROR", "ERR-CHECKOUT-FAIL",
                    f"Payment Failed. Route: POST /api/v1/orders/checkout. Trace ID: {trace}",
                    trace
                ])

        # --- Order Service ---
        order_req = int(gateway_requests * 0.6)
        order_cpu = 18.0 + order_req * 0.08 + random.uniform(-2.0, 2.0)
        order_mem = 50.0 + random.uniform(-0.5, 0.5)
        order_err_rate = 0.0
        
        base_processing_lat = 30.0 + order_req * 0.05 + random.uniform(-2.0, 2.0)
        order_lat = base_processing_lat + inv_lat + (0.3 * pay_lat)
        
        order_db_conn = int(2 + order_req * 0.06)
        order_db_conn = min(order_db_conn, 45)

        # Propagate downstream error rates to order-service
        order_err_rate = min(1.0, inv_err_rate * 0.8 + pay_err_rate * 0.25)

        # Apply Incident 4: Database CPU Saturation
        if incidents_active["INC-004"]:
            order_cpu = 96.0 + random.uniform(-2.0, 2.0)
            order_db_conn = 48
            order_lat = base_processing_lat + 2200.0
            order_err_rate = max(order_err_rate, 0.45)
            
            if current_time.minute % 15 == 0:
                trace = generate_trace_id()
                log_count += 1
                writer_logs.writerow([
                    ts_str, "order-service", "WARN", "ERR-DB-SLOWQUERY",
                    f"Slow Query Warning: SELECT * FROM orders WHERE customer_id = 91823 AND status = 'COMPLETED' ORDER BY created_at DESC took 4250ms. No matching index found. Executing sequential table scan.",
                    trace
                ])
                log_count += 1
                writer_logs.writerow([
                    ts_str, "gateway-service", "ERROR", "ERR-GATEWAY-TIMEOUT",
                    f"Gateway read timeout on GET /api/v1/orders. Trace ID: {trace}",
                    trace
                ])

        # Apply Incident 6: Main P1 connection pool exhaustion (Aug 17)
        if incidents_active["INC-006"]:
            desired_db_conn = int(2 + order_req * 0.06)
            
            if desired_db_conn >= 5:
                # Connection pool hard cap
                order_db_conn = 5
                
                # Active queueing wait time spikes to Hikari connection timeout limits
                excess_ratio = desired_db_conn / 5.0
                pool_wait = 5000.0 * min(excess_ratio, 1.2) + random.uniform(-50, 50)
                pool_wait = min(pool_wait, 5000.0)
                
                order_lat = base_processing_lat + pool_wait + inv_lat + (0.3 * pay_lat)
                order_err_rate = max(order_err_rate, 0.65)
                
                if current_time.minute % 5 == 0:
                    trace = generate_trace_id()
                    log_count += 1
                    writer_logs.writerow([
                        ts_str, "order-service", "WARN", "",
                        "HikariPool-1 - Connection pool status: Active=5, Idle=0, Pending=18, MaxAllowed=5. Thread starvation warning.",
                        ""
                    ])
                    log_count += 1
                    writer_logs.writerow([
                        ts_str, "order-service", "ERROR", "ERR-DB-POOL-TIMEOUT",
                        f"SQLTransientConnectionException: HikariPool-1 - Connection is not available, request timed out after 5000ms. Trace ID: {trace}",
                        trace
                    ])
                    log_count += 1
                    writer_logs.writerow([
                        ts_str, "gateway-service", "ERROR", "ERR-GATEWAY-TIMEOUT",
                        f"Bad Gateway (504): order-service failed to respond in time. Trace ID: {trace}",
                        trace
                    ])
            else:
                # Normal low-traffic state
                order_db_conn = desired_db_conn
                order_lat = base_processing_lat + inv_lat + (0.3 * pay_lat)
                
                if order_db_conn >= 4 and current_time.minute % 15 == 0:
                    log_count += 1
                    writer_logs.writerow([
                        ts_str, "order-service", "WARN", "",
                        f"HikariPool-1 - Close to capacity limit. Active={order_db_conn}, MaxLimit=5. Consider scaling pool size.",
                        ""
                    ])

        # --- Gateway Service ---
        gateway_cpu = 10.0 + gateway_requests * 0.06 + random.uniform(-1.0, 1.0)
        gateway_mem = 35.0 + random.uniform(-0.5, 0.5)
        gateway_lat = 5.0 + auth_lat + order_lat
        gateway_err_rate = max(auth_err_rate, order_err_rate)
        gateway_db_conn = 0

        # --- Write Metrics for all services ---
        # service_metrics schema: timestamp,service_name,cpu_percent,memory_percent,request_count,error_rate,latency_ms,db_connections
        writer_metrics.writerow([
            ts_str, "gateway-service", f"{gateway_cpu:.2f}", f"{gateway_mem:.2f}",
            gateway_requests, f"{gateway_err_rate:.4f}", f"{gateway_lat:.2f}", gateway_db_conn
        ])
        writer_metrics.writerow([
            ts_str, "auth-service", f"{auth_cpu:.2f}", f"{auth_mem:.2f}",
            auth_req, f"{auth_err_rate:.4f}", f"{auth_lat:.2f}", auth_db_conn
        ])
        writer_metrics.writerow([
            ts_str, "order-service", f"{order_cpu:.2f}", f"{order_mem:.2f}",
            order_req, f"{order_err_rate:.4f}", f"{order_lat:.2f}", order_db_conn
        ])
        writer_metrics.writerow([
            ts_str, "inventory-service", f"{inv_cpu:.2f}", f"{inv_mem:.2f}",
            inv_req, f"{inv_err_rate:.4f}", f"{inv_lat:.2f}", inv_db_conn
        ])
        writer_metrics.writerow([
            ts_str, "payment-service", f"{pay_cpu:.2f}", f"{pay_mem:.2f}",
            pay_req, f"{pay_err_rate:.4f}", f"{pay_lat:.2f}", pay_db_conn
        ])

        # --- 5. Sampled Normal Logs ---
        if current_time.minute == 0:
            writer_logs.writerow([ts_str, "gateway-service", "INFO", "", "Gateway routing configurations successfully reloaded. Active routes: /api/v1/*", ""])
            writer_logs.writerow([ts_str, "auth-service", "INFO", "", "Session cleaner worker run completed. Cleaned 0 expired tokens.", ""])
            writer_logs.writerow([ts_str, "order-service", "INFO", "", f"Heartbeat check: Database is reachable. Active connections: {order_db_conn}.", ""])
            writer_logs.writerow([ts_str, "inventory-service", "INFO", "", "Stock sync worker ran successfully. 0 items update required.", ""])
            writer_logs.writerow([ts_str, "payment-service", "INFO", "", "Gateway healthcheck: stripe connectivity OK.", ""])

        if random.random() < 0.015:
            trace = generate_trace_id()
            user_id = random.randint(10000, 99999)
            order_id = random.randint(50000, 59999)
            
            writer_logs.writerow([ts_str, "gateway-service", "INFO", "", f"Inbound Request: POST /api/v1/orders/checkout, User: {user_id}", trace])
            writer_logs.writerow([ts_str, "auth-service", "INFO", "", f"Token validation successful for user {user_id}", trace])
            writer_logs.writerow([ts_str, "order-service", "INFO", "", f"Creating order {order_id} for user {user_id}. Checking inventory...", trace])
            writer_logs.writerow([ts_str, "inventory-service", "INFO", "", f"Stock check: Item available in warehouse. Reserving stock.", trace])
            writer_logs.writerow([ts_str, "order-service", "INFO", "", f"Inventory reservation confirmed. Initiating payment for order {order_id}...", trace])
            writer_logs.writerow([ts_str, "payment-service", "INFO", "", f"Authorizing payment via credit card for amount: $45.99. Order {order_id}", trace])
            writer_logs.writerow([ts_str, "payment-service", "INFO", "", f"Payment transaction successful. AuthCode: stripe_ch_{generate_trace_id()[:8]}", trace])
            writer_logs.writerow([ts_str, "order-service", "INFO", "", f"Payment successful. Confirming order status to PLACED. Order {order_id}", trace])
            writer_logs.writerow([ts_str, "gateway-service", "INFO", "", f"Inbound Request POST /api/v1/orders/checkout completed with 201 Created. Trace ID: {trace}", trace])

        current_time += delta
        
    f_metrics.close()
    f_logs.close()
    print(f"Created: {metrics_path}")
    print(f"Created: {logs_path}")

def main():
    print("Starting Synthetic Data Generation...")
    write_service_dependencies()
    write_incidents()
    generate_deployments()
    generate_metrics_and_logs()
    print("All synthetic datasets generated successfully!")

if __name__ == "__main__":
    main()
