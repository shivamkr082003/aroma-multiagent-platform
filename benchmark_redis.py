"""
Aroma AI - Redis Performance Benchmark Suite
Measures real-world impact of Redis caching vs PostgreSQL retrieval across:
1. End-to-End Chat API Latency (Redis ON Cold vs Warm vs Redis OFF)
2. PostgreSQL Query Counts & Latencies
3. Redis GET / SET Latencies & Hit Ratios
4. Isolated Micro-benchmarks for Chat History Retrieval (PostgreSQL vs Redis)
5. Statistical Percentiles (p50, p75, p90, p95, p99) and Throughput
"""

import os
import time
import json
import uuid
import numpy as np
from sqlalchemy import event
from fastapi.testclient import TestClient

# Ensure models are imported
from db import engine, SessionLocal
import models.message
import models.session
import models
from models.message import Message
from crud.session import create_session
from crud.message import create_message
from main import app
import redis_client


# ==========================================
# 1. DATABASE QUERY INSTRUMENTATION
# ==========================================
class QueryTracker:
    def __init__(self, target_engine):
        self.engine = target_engine
        self.queries = []
        self.active = False

        @event.listens_for(self.engine, "before_cursor_execute")
        def before_exec(conn, cursor, statement, parameters, context, executemany):
            if self.active:
                context._benchmark_start = time.perf_counter()

        @event.listens_for(self.engine, "after_cursor_execute")
        def after_exec(conn, cursor, statement, parameters, context, executemany):
            if self.active:
                duration_ms = (time.perf_counter() - getattr(context, "_benchmark_start", time.perf_counter())) * 1000.0
                self.queries.append({
                    "statement": statement.strip().replace("\n", " "),
                    "duration_ms": duration_ms
                })

    def start(self):
        self.queries = []
        self.active = True

    def stop(self):
        self.active = False
        return list(self.queries)


# ==========================================
# 2. STATISTICAL HELPER
# ==========================================
def calculate_distribution(latencies_ms: list[float]) -> dict:
    if not latencies_ms:
        return {
            "count": 0, "avg": 0.0, "min": 0.0, "max": 0.0,
            "p50": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0
        }
    arr = np.array(latencies_ms)
    return {
        "count": len(arr),
        "avg": float(np.mean(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "p50": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p90": float(np.percentile(arr, 90)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
    }


# ==========================================
# 3. BENCHMARK RUNNER
# ==========================================
def run_benchmark():
    os.makedirs("benchmark-results", exist_ok=True)
    query_tracker = QueryTracker(engine)
    client = TestClient(app)

    conversation_turns = [
        "Explain what is Redis.",
        "Why is Redis faster than PostgreSQL?",
        "Give me a simple example.",
        "Summarize what you explained.",
    ]

    print("=" * 70)
    print("        AROMA AI - REDIS PERFORMANCE BENCHMARK SUITE        ")
    print("=" * 70)

    # ----------------------------------------------------
    # PHASE 1: WARM-UP REQUESTS
    # ----------------------------------------------------
    print("\n[Phase 1] Running Warm-up Requests...")
    redis_client.set_redis_enabled(True)
    warmup_session = f"warmup_{uuid.uuid4().hex[:8]}"
    for q in ["Hello", "How does caching work?"]:
        client.post("/chat", json={
            "message": q,
            "session_id": warmup_session,
            "user_id": "benchmark_user"
        })
    redis_client.clear_chat(warmup_session)
    print("Warm-up complete. System caches and connection pools primed.")

    # ----------------------------------------------------
    # PHASE 2: MACRO E2E BENCHMARK - REDIS ON
    # ----------------------------------------------------
    print("\n[Phase 2] Running Macro E2E Benchmark: REDIS ENABLED...")
    redis_client.set_redis_enabled(True)
    redis_client.reset_metrics()

    num_sessions = 5  # 5 full 4-turn conversations = 20 requests
    redis_on_cold_records = []
    redis_on_warm_records = []

    for s_idx in range(num_sessions):
        session_id = f"redis_on_session_{s_idx}_{uuid.uuid4().hex[:6]}"
        redis_client.clear_chat(session_id)

        for turn_idx, prompt in enumerate(conversation_turns):
            is_cold = (turn_idx == 0)
            
            # Reset query tracker for this request
            query_tracker.start()
            t0 = time.perf_counter()
            resp = client.post("/chat", json={
                "message": prompt,
                "session_id": session_id,
                "user_id": "benchmark_user"
            })
            t1 = time.perf_counter()
            db_queries = query_tracker.stop()

            e2e_latency_ms = (t1 - t0) * 1000.0
            assert resp.status_code == 200, f"Chat API returned {resp.status_code}: {resp.text}"

            record = {
                "session_id": session_id,
                "turn": turn_idx + 1,
                "prompt": prompt,
                "is_cold": is_cold,
                "e2e_latency_ms": e2e_latency_ms,
                "db_query_count": len(db_queries),
                "db_total_query_time_ms": sum(q["duration_ms"] for q in db_queries),
                "db_queries": db_queries,
                "llm_calls_count": 2, # 1 router_llm + 1 answer_llm
            }

            if is_cold:
                redis_on_cold_records.append(record)
                print(f"  [Redis ON Cold - Session {s_idx+1}] Turn {turn_idx+1}: {e2e_latency_ms:.2f} ms (DB queries: {len(db_queries)})")
            else:
                redis_on_warm_records.append(record)
                print(f"  [Redis ON Warm - Session {s_idx+1}] Turn {turn_idx+1}: {e2e_latency_ms:.2f} ms (DB queries: {len(db_queries)})")

        redis_client.clear_chat(session_id)

    redis_on_metrics = redis_client.get_metrics()
    print(f"\nRedis ON Telemetry: {redis_on_metrics}")

    # ----------------------------------------------------
    # PHASE 3: MACRO E2E BENCHMARK - REDIS OFF
    # ----------------------------------------------------
    print("\n[Phase 3] Running Macro E2E Benchmark: REDIS DISABLED...")
    redis_client.set_redis_enabled(False)
    redis_client.reset_metrics()

    redis_off_records = []

    for s_idx in range(num_sessions):
        session_id = f"redis_off_session_{s_idx}_{uuid.uuid4().hex[:6]}"

        for turn_idx, prompt in enumerate(conversation_turns):
            query_tracker.start()
            t0 = time.perf_counter()
            resp = client.post("/chat", json={
                "message": prompt,
                "session_id": session_id,
                "user_id": "benchmark_user"
            })
            t1 = time.perf_counter()
            db_queries = query_tracker.stop()

            e2e_latency_ms = (t1 - t0) * 1000.0
            assert resp.status_code == 200, f"Chat API returned {resp.status_code}: {resp.text}"

            record = {
                "session_id": session_id,
                "turn": turn_idx + 1,
                "prompt": prompt,
                "is_cold": (turn_idx == 0),
                "e2e_latency_ms": e2e_latency_ms,
                "db_query_count": len(db_queries),
                "db_total_query_time_ms": sum(q["duration_ms"] for q in db_queries),
                "db_queries": db_queries,
                "llm_calls_count": 2, # 1 router_llm + 1 answer_llm
            }
            redis_off_records.append(record)
            print(f"  [Redis OFF - Session {s_idx+1}] Turn {turn_idx+1}: {e2e_latency_ms:.2f} ms (DB queries: {len(db_queries)})")

    redis_off_metrics = redis_client.get_metrics()

    # Re-enable Redis for subsequent tests and normal operations
    redis_client.set_redis_enabled(True)

    # ----------------------------------------------------
    # PHASE 4: ISOLATED MICRO-BENCHMARK (STORAGE RETRIEVAL)
    # ----------------------------------------------------
    print("\n[Phase 4] Running Isolated Micro-Benchmark: Redis GET vs PostgreSQL Read...")
    # Prepare identical test session with 10 messages in both PostgreSQL and Redis
    test_micro_session = f"micro_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    create_session(db, test_micro_session, "benchmark_user")

    sample_history = []
    for i in range(5):
        u_msg = f"User message {i+1} about Redis and PostgreSQL performance."
        a_msg = f"AI response {i+1} explaining memory caching, index structures, and network roundtrips."
        create_message(db, test_micro_session, "benchmark_user", "user", u_msg)
        create_message(db, test_micro_session, "benchmark_user", "ai", a_msg)
        sample_history.append({"role": "user", "content": u_msg})
        sample_history.append({"role": "ai", "content": a_msg})

    # Prime Redis
    redis_client.save_chat_history(test_micro_session, sample_history)

    # Benchmark PostgreSQL History Retrieval (100 iterations)
    num_micro_iterations = 100
    pg_retrieval_latencies = []
    for _ in range(num_micro_iterations):
        t0 = time.perf_counter()
        msgs = (
            db.query(Message)
            .filter(Message.session_id == test_micro_session)
            .order_by(Message.created_at)
            .limit(10)
            .all()
        )
        t1 = time.perf_counter()
        pg_retrieval_latencies.append((t1 - t0) * 1000.0)

    # Benchmark Redis History Retrieval (100 iterations)
    redis_retrieval_latencies = []
    for _ in range(num_micro_iterations):
        t0 = time.perf_counter()
        hist = redis_client.get_chat_history(test_micro_session)
        t1 = time.perf_counter()
        redis_retrieval_latencies.append((t1 - t0) * 1000.0)

    db.close()
    redis_client.clear_chat(test_micro_session)

    # ----------------------------------------------------
    # PHASE 5: COMPILE AND SAVE RESULTS
    # ----------------------------------------------------
    print("\n[Phase 5] Compiling Statistics and Saving Raw JSON Results...")

    redis_off_dist = calculate_distribution([r["e2e_latency_ms"] for r in redis_off_records])
    redis_on_cold_dist = calculate_distribution([r["e2e_latency_ms"] for r in redis_on_cold_records])
    redis_on_warm_dist = calculate_distribution([r["e2e_latency_ms"] for r in redis_on_warm_records])
    redis_on_all_dist = calculate_distribution([r["e2e_latency_ms"] for r in (redis_on_cold_records + redis_on_warm_records)])

    pg_retrieval_dist = calculate_distribution(pg_retrieval_latencies)
    redis_retrieval_dist = calculate_distribution(redis_retrieval_latencies)

    # Calculate throughputs (requests/sec for retrieval)
    pg_throughput = 1000.0 / pg_retrieval_dist["avg"] if pg_retrieval_dist["avg"] > 0 else 0.0
    redis_throughput = 1000.0 / redis_retrieval_dist["avg"] if redis_retrieval_dist["avg"] > 0 else 0.0

    retrieval_improvement_pct = (
        ((pg_retrieval_dist["avg"] - redis_retrieval_dist["avg"]) / pg_retrieval_dist["avg"] * 100)
        if pg_retrieval_dist["avg"] > 0 else 0.0
    )

    # Average DB queries per request
    avg_db_queries_off = float(np.mean([r["db_query_count"] for r in redis_off_records]))
    avg_db_queries_on_cold = float(np.mean([r["db_query_count"] for r in redis_on_cold_records]))
    avg_db_queries_on_warm = float(np.mean([r["db_query_count"] for r in redis_on_warm_records]))

    avg_db_query_time_off = float(np.mean([r["db_total_query_time_ms"] for r in redis_off_records]))
    avg_db_query_time_on_warm = float(np.mean([r["db_total_query_time_ms"] for r in redis_on_warm_records]))

    # Save individual JSON files
    with open("benchmark-results/redis-off.json", "w") as f:
        json.dump({
            "mode": "REDIS_OFF",
            "stats": redis_off_dist,
            "avg_db_queries_per_request": avg_db_queries_off,
            "avg_db_query_time_ms": avg_db_query_time_off,
            "records": redis_off_records,
            "telemetry": redis_off_metrics,
        }, f, indent=2)

    with open("benchmark-results/redis-on-cold.json", "w") as f:
        json.dump({
            "mode": "REDIS_ON_COLD",
            "stats": redis_on_cold_dist,
            "avg_db_queries_per_request": avg_db_queries_on_cold,
            "records": redis_on_cold_records,
        }, f, indent=2)

    with open("benchmark-results/redis-on-warm.json", "w") as f:
        json.dump({
            "mode": "REDIS_ON_WARM",
            "stats": redis_on_warm_dist,
            "avg_db_queries_per_request": avg_db_queries_on_warm,
            "avg_db_query_time_ms": avg_db_query_time_on_warm,
            "records": redis_on_warm_records,
            "telemetry": redis_on_metrics,
        }, f, indent=2)

    with open("benchmark-results/retrieval-micro.json", "w") as f:
        json.dump({
            "postgresql_retrieval": {
                "distribution_ms": pg_retrieval_dist,
                "throughput_ops_sec": pg_throughput,
                "raw_latencies_ms": pg_retrieval_latencies,
            },
            "redis_retrieval": {
                "distribution_ms": redis_retrieval_dist,
                "throughput_ops_sec": redis_throughput,
                "raw_latencies_ms": redis_retrieval_latencies,
            },
            "improvement_pct": retrieval_improvement_pct,
            "throughput_speedup": (redis_throughput / pg_throughput if pg_throughput > 0 else 1.0),
        }, f, indent=2)

    comparison_data = {
        "summary": {
            "macro_e2e": {
                "redis_off": redis_off_dist,
                "redis_on_cold": redis_on_cold_dist,
                "redis_on_warm": redis_on_warm_dist,
                "redis_on_all": redis_on_all_dist,
            },
            "micro_retrieval": {
                "postgresql_avg_ms": pg_retrieval_dist["avg"],
                "redis_avg_ms": redis_retrieval_dist["avg"],
                "postgresql_p50_ms": pg_retrieval_dist["p50"],
                "redis_p50_ms": redis_retrieval_dist["p50"],
                "postgresql_p95_ms": pg_retrieval_dist["p95"],
                "redis_p95_ms": redis_retrieval_dist["p95"],
                "postgresql_p99_ms": pg_retrieval_dist["p99"],
                "redis_p99_ms": redis_retrieval_dist["p99"],
                "improvement_pct": retrieval_improvement_pct,
                "postgresql_throughput_ops_sec": pg_throughput,
                "redis_throughput_ops_sec": redis_throughput,
            },
            "database_impact": {
                "avg_db_queries_off": avg_db_queries_off,
                "avg_db_queries_on_cold": avg_db_queries_on_cold,
                "avg_db_queries_on_warm": avg_db_queries_on_warm,
                "avg_db_query_time_off_ms": avg_db_query_time_off,
                "avg_db_query_time_on_warm_ms": avg_db_query_time_on_warm,
            },
            "redis_telemetry": redis_on_metrics,
            "llm_calls_per_request": 2,
        }
    }

    with open("benchmark-results/comparison.json", "w") as f:
        json.dump(comparison_data, f, indent=2)

    print("\nBenchmark results saved successfully to benchmark-results/")

    # ----------------------------------------------------
    # PRINT SUMMARY TABLES
    # ----------------------------------------------------
    print("\n" + "=" * 80)
    print("                 BENCHMARK RESULTS & COMPARISON TABLE                 ")
    print("=" * 80)
    print(f"{'Metric':<35} | {'Redis OFF':<15} | {'Redis ON (Warm)':<15} | {'Improvement':<12}")
    print("-" * 80)
    print(f"{'Chat History Retrieval Latency (avg)':<35} | {pg_retrieval_dist['avg']:>11.3f} ms | {redis_retrieval_dist['avg']:>11.3f} ms | {retrieval_improvement_pct:>10.2f}%")
    print(f"{'Chat History Retrieval (p50)':<35} | {pg_retrieval_dist['p50']:>11.3f} ms | {redis_retrieval_dist['p50']:>11.3f} ms | {((pg_retrieval_dist['p50']-redis_retrieval_dist['p50'])/pg_retrieval_dist['p50']*100):>10.2f}%")
    print(f"{'Chat History Retrieval (p95)':<35} | {pg_retrieval_dist['p95']:>11.3f} ms | {redis_retrieval_dist['p95']:>11.3f} ms | {((pg_retrieval_dist['p95']-redis_retrieval_dist['p95'])/pg_retrieval_dist['p95']*100):>10.2f}%")
    print(f"{'Chat History Retrieval (p99)':<35} | {pg_retrieval_dist['p99']:>11.3f} ms | {redis_retrieval_dist['p99']:>11.3f} ms | {((pg_retrieval_dist['p99']-redis_retrieval_dist['p99'])/pg_retrieval_dist['p99']*100):>10.2f}%")
    print(f"{'History Retrieval Throughput':<35} | {pg_throughput:>9.1f} ops/s | {redis_throughput:>9.1f} ops/s | {(redis_throughput/pg_throughput):>10.2f}x")
    print(f"{'Redis Cache Hit Ratio':<35} | {'0.0%':>15} | {redis_on_metrics['hit_ratio']:>14.1f}% | {'N/A':>12}")
    print(f"{'PostgreSQL DB Queries / Request':<35} | {avg_db_queries_off:>15.1f} | {avg_db_queries_on_warm:>15.1f} | {((avg_db_queries_off-avg_db_queries_on_warm)/avg_db_queries_off*100):>10.2f}%")
    print(f"{'LLM Calls / Request':<35} | {'2 (No reduction)':>15} | {'2 (No reduction)':>15} | {'0.0%':>12}")
    print(f"{'End-to-End Request Latency (avg)':<35} | {redis_off_dist['avg']:>11.2f} ms | {redis_on_warm_dist['avg']:>11.2f} ms | {((redis_off_dist['avg']-redis_on_warm_dist['avg'])/redis_off_dist['avg']*100):>10.2f}%")
    print(f"{'End-to-End Request Latency (p50)':<35} | {redis_off_dist['p50']:>11.2f} ms | {redis_on_warm_dist['p50']:>11.2f} ms | {((redis_off_dist['p50']-redis_on_warm_dist['p50'])/redis_off_dist['p50']*100):>10.2f}%")
    print(f"{'End-to-End Request Latency (p95)':<35} | {redis_off_dist['p95']:>11.2f} ms | {redis_on_warm_dist['p95']:>11.2f} ms | {((redis_off_dist['p95']-redis_on_warm_dist['p95'])/redis_off_dist['p95']*100):>10.2f}%")
    print(f"{'End-to-End Request Latency (p99)':<35} | {redis_off_dist['p99']:>11.2f} ms | {redis_on_warm_dist['p99']:>11.2f} ms | {((redis_off_dist['p99']-redis_on_warm_dist['p99'])/redis_off_dist['p99']*100):>10.2f}%")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
