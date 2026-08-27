"""
Aroma AI - Agent Routing Latency Benchmark
Measures the actual latency of each stage in the LangGraph orchestration flow:
- router_node (Router LLM query classification)
- route_after_router (Edge routing decision)
- rag_node (Qdrant semantic search)
- route_after_rag (Post-RAG edge routing decision)
- live_search_node / url_scrape_node (Tool nodes)
- answer_node (Synthesis LLM generation)
- Total Orchestration Latency vs LLM Generation Latency
"""

import os
import time
import json
import uuid
import numpy as np
from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import SystemMessage, HumanMessage
from Agent.agent import (
    router_llm,
    ROUTER_PROMPT,
    extract_urls,
    route_after_router,
    route_after_rag,
    rag_node,
    router_node,
    _graph,
    ChatState,
)


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


def run_routing_benchmark():
    os.makedirs("benchmark-results", exist_ok=True)
    print("=" * 75)
    print("          AROMA AI - AGENT ROUTING LATENCY BENCHMARK          ")
    print("=" * 75)

    test_queries = [
        # Direct conversational queries
        {"category": "direct", "query": "What is Redis and how does it work?"},
        {"category": "direct", "query": "Explain the difference between SQL and NoSQL databases."},
        {"category": "direct", "query": "Write a Python function to compute Fibonacci numbers."},
        {"category": "direct", "query": "What are microservices architectures?"},
        # Semantic RAG queries
        {"category": "rag", "query": "What skills are listed in the uploaded resume document?"},
        {"category": "rag", "query": "What is the work experience mentioned in the candidate PDF?"},
        {"category": "rag", "query": "Summarize the project section from the document."},
        # Live search / news queries
        {"category": "search", "query": "What is the latest news and weather in Tokyo today?"},
        {"category": "search", "query": "Current price of Bitcoin and stock market trends today."},
        # URL scraping queries
        {"category": "scrape", "query": "Summarize the contents of https://example.com"},
        {"category": "scrape", "query": "Analyze this LeetCode profile link: leetcode.com/u/testuser"},
    ]

    router_llm_latencies = []
    regex_router_latencies = []
    edge_decision_latencies = []
    rag_retrieval_latencies = []
    full_orchestration_latencies = []

    print("\n[Phase 1] Measuring Router Node Classification Latencies across Query Types...")
    for idx, item in enumerate(test_queries):
        query = item["query"]
        category = item["category"]

        # 1. Measure Heuristic/Regex classification latency
        t0 = time.perf_counter()
        urls_found = bool(extract_urls(query))
        t1 = time.perf_counter()
        regex_lat = (t1 - t0) * 1000.0
        regex_router_latencies.append(regex_lat)

        # 2. Measure LLM Router Node invocation latency
        t0 = time.perf_counter()
        state = {
            "user_msg": query,
            "session_id": f"bench_{uuid.uuid4().hex[:6]}",
            "file_id": "mock_file_id" if category == "rag" else None,
            "user_id": "demo_user",
            "has_urls": False,
            "needs_search": False,
            "has_docs": False,
            "rag_context": "",
            "search_context": "",
            "reply": "",
        }
        res_node = router_node(state)
        t1 = time.perf_counter()
        router_llm_lat = (t1 - t0) * 1000.0
        router_llm_latencies.append(router_llm_lat)

        # 3. Measure Edge Routing decision latency
        t0 = time.perf_counter()
        merged_state = {**state, **res_node}
        next_destination = route_after_router(merged_state)
        t1 = time.perf_counter()
        edge_lat = (t1 - t0) * 1000.0
        edge_decision_latencies.append(edge_lat)

        # 4. Measure RAG node retrieval latency if routed to RAG
        rag_lat = 0.0
        if next_destination == "rag_node" or category == "rag":
            t0 = time.perf_counter()
            rag_res = rag_node(merged_state)
            t1 = time.perf_counter()
            rag_lat = (t1 - t0) * 1000.0
            rag_retrieval_latencies.append(rag_lat)

        total_orchestration = router_llm_lat + edge_lat + rag_lat
        full_orchestration_latencies.append(total_orchestration)

        print(f"  [{category.upper():<6}] '{query[:38]}...' -> Next: {next_destination:<14} | Router LLM: {router_llm_lat:>7.2f} ms | RAG: {rag_lat:>6.2f} ms | Total Orch: {total_orchestration:>7.2f} ms")

    # ----------------------------------------------------
    # PHASE 2: COMPILE STATISTICS
    # ----------------------------------------------------
    router_llm_dist = calculate_distribution(router_llm_latencies)
    regex_dist = calculate_distribution(regex_router_latencies)
    edge_dist = calculate_distribution(edge_decision_latencies)
    rag_dist = calculate_distribution(rag_retrieval_latencies)
    orchestration_dist = calculate_distribution(full_orchestration_latencies)

    results = {
        "router_llm_classification_ms": router_llm_dist,
        "regex_local_classification_ms": regex_dist,
        "edge_routing_logic_ms": edge_dist,
        "rag_vector_retrieval_ms": rag_dist,
        "total_orchestration_latency_ms": orchestration_dist,
        "raw_samples": {
            "router_llm_latencies": router_llm_latencies,
            "regex_latencies": regex_router_latencies,
            "rag_latencies": rag_retrieval_latencies,
            "total_orchestration_latencies": full_orchestration_latencies,
        }
    }

    with open("benchmark-results/routing-benchmark.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print("                    ROUTING LATENCY BREAKDOWN SUMMARY                 ")
    print("=" * 80)
    print(f"{'Component':<35} | {'Avg (ms)':<10} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10}")
    print("-" * 80)
    print(f"{'Router Node (LLM llama-3.3-70b-versatile)':<35} | {router_llm_dist['avg']:>10.2f} | {router_llm_dist['p50']:>10.2f} | {router_llm_dist['p95']:>10.2f} | {router_llm_dist['p99']:>10.2f}")
    print(f"{'Local Regex/Rule Classification':<35} | {regex_dist['avg']:>10.4f} | {regex_dist['p50']:>10.4f} | {regex_dist['p95']:>10.4f} | {regex_dist['p99']:>10.4f}")
    print(f"{'Edge Decision Logic (LangGraph)':<35} | {edge_dist['avg']:>10.4f} | {edge_dist['p50']:>10.4f} | {edge_dist['p95']:>10.4f} | {edge_dist['p99']:>10.4f}")
    print(f"{'RAG Semantic Retrieval (Qdrant)':<35} | {rag_dist['avg']:>10.2f} | {rag_dist['p50']:>10.2f} | {rag_dist['p95']:>10.2f} | {rag_dist['p99']:>10.2f}")
    print(f"{'Total Pre-Synthesis Orchestration':<35} | {orchestration_dist['avg']:>10.2f} | {orchestration_dist['p50']:>10.2f} | {orchestration_dist['p95']:>10.2f} | {orchestration_dist['p99']:>10.2f}")
    print("=" * 80)


if __name__ == "__main__":
    run_routing_benchmark()
