"""
Aroma AI - Voice Pipeline End-to-End Latency Benchmark
Measures actual latency across every stage of the Aroma voice interface:
1. Audio file upload & conversion (FFmpeg WebM -> WAV 16kHz)
2. Speech-to-Text (Deepgram Nova-2)
3. Agent / LLM Processing (LangGraph chat)
4. Text-to-Speech (Deepgram Aura-Asteria)
5. Total End-to-End Voice Response Time vs Isolated Audio I/O
6. Statistical distributions (p50, p75, p90, p95, p99, avg, min, max)
"""

import os
import time
import json
import uuid
import subprocess
import requests
import numpy as np
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()

from main import app, speech_to_text, text_to_speech
from Agent.agent import chat


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


def run_voice_benchmark():
    os.makedirs("benchmark-results", exist_ok=True)
    os.makedirs("temp_voice_test", exist_ok=True)
    client = TestClient(app)
    api_key = os.getenv("DEEPGRAM_API_KEY")

    print("=" * 75)
    print("           AROMA AI - VOICE PIPELINE LATENCY BENCHMARK         ")
    print("=" * 75)

    test_utterances = [
        "Hello, what is Aroma AI?",
        "How does vector search work in Qdrant?",
        "Why is Redis faster than PostgreSQL?",
        "Summarize how LangGraph manages agent state.",
    ]

    print("\n[Phase 1] Synthesizing Real WebM Audio Inputs via Deepgram + FFmpeg...")
    audio_files = []
    for idx, text in enumerate(test_utterances):
        mp3_path = f"temp_voice_test/input_{idx}.mp3"
        webm_path = f"temp_voice_test/input_{idx}.webm"

        # Generate audio with Deepgram TTS
        res = requests.post(
            "https://api.deepgram.com/v1/speak?model=aura-asteria-en",
            headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
            json={"text": text},
            timeout=15
        )
        with open(mp3_path, "wb") as f:
            f.write(res.content)

        # Transcode to WebM (Opus) to mirror browser MediaRecorder output
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-c:a", "libopus", webm_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        audio_files.append((text, webm_path))
        print(f"  Generated sample {idx+1}: '{text}' -> {webm_path}")

    # ----------------------------------------------------
    # PHASE 2: DETAILED STAGE-BY-STAGE COMPONENT MEASUREMENT
    # ----------------------------------------------------
    print("\n[Phase 2] Running Stage-by-Stage Component Latency Breakdown...")
    ffmpeg_latencies = []
    stt_latencies = []
    llm_latencies = []
    tts_latencies = []
    total_component_latencies = []
    audio_io_latencies = []

    num_runs_per_sample = 2  # Repeat each sample twice for statistical reliability
    for run in range(num_runs_per_sample):
        for idx, (orig_text, webm_path) in enumerate(audio_files):
            print(f"\n  [Run {run+1} | Sample {idx+1}] Testing: '{orig_text}'")

            # 1. FFmpeg Conversion Stage (.webm -> .wav 16kHz mono)
            wav_path = f"temp_voice_test/converted_{idx}_{uuid.uuid4().hex[:4]}.wav"
            t0 = time.perf_counter()
            subprocess.run(
                ["ffmpeg", "-y", "-i", webm_path, "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", wav_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            t1 = time.perf_counter()
            ffmpeg_ms = (t1 - t0) * 1000.0
            ffmpeg_latencies.append(ffmpeg_ms)

            # 2. Deepgram STT Stage (Nova-2)
            t0 = time.perf_counter()
            with open(wav_path, "rb") as audio:
                res_stt = requests.post(
                    "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true",
                    headers={"Authorization": f"Token {api_key}", "Content-Type": "audio/wav"},
                    data=audio,
                    timeout=15
                )
            t1 = time.perf_counter()
            stt_ms = (t1 - t0) * 1000.0
            stt_latencies.append(stt_ms)
            
            stt_data = res_stt.json()
            transcript = (
                stt_data.get("results", {})
                .get("channels", [{}])[0]
                .get("alternatives", [{}])[0]
                .get("transcript", "")
            )
            if os.path.exists(wav_path):
                os.remove(wav_path)

            # 3. LangGraph Chat & LLM Processing Stage
            t0 = time.perf_counter()
            response_text = chat(transcript or orig_text, "voice_session_bench")
            t1 = time.perf_counter()
            llm_ms = (t1 - t0) * 1000.0
            llm_latencies.append(llm_ms)

            # 4. Deepgram TTS Stage (Aura-Asteria)
            t0 = time.perf_counter()
            res_tts = requests.post(
                "https://api.deepgram.com/v1/speak?model=aura-asteria-en",
                headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
                json={"text": response_text[:1000]}, # TTS first 1000 chars
                timeout=20
            )
            t1 = time.perf_counter()
            tts_ms = (t1 - t0) * 1000.0
            tts_latencies.append(tts_ms)

            audio_io_ms = ffmpeg_ms + stt_ms + tts_ms
            total_e2e_ms = audio_io_ms + llm_ms

            audio_io_latencies.append(audio_io_ms)
            total_component_latencies.append(total_e2e_ms)

            print(f"    - FFmpeg Transcoding: {ffmpeg_ms:>7.2f} ms")
            print(f"    - Deepgram STT:       {stt_ms:>7.2f} ms (Transcribed: '{transcript[:30]}...')")
            print(f"    - LangGraph/LLM Chat: {llm_ms:>7.2f} ms")
            print(f"    - Deepgram TTS:       {tts_ms:>7.2f} ms")
            print(f"    - Isolated Audio I/O: {audio_io_ms:>7.2f} ms")
            print(f"    - TOTAL E2E Voice:    {total_e2e_ms:>7.2f} ms ({total_e2e_ms/1000.0:.2f} s)")

    # ----------------------------------------------------
    # PHASE 3: FASTAPI /voice HTTP ENDPOINT BENCHMARK
    # ----------------------------------------------------
    print("\n[Phase 3] Benchmarking Actual FastAPI /voice HTTP Endpoint...")
    endpoint_e2e_latencies = []
    for idx, (orig_text, webm_path) in enumerate(audio_files):
        with open(webm_path, "rb") as f:
            t0 = time.perf_counter()
            resp = client.post(
                "/voice",
                files={"file": ("voice.webm", f, "audio/webm")}
            )
            t1 = time.perf_counter()
            e2e_ms = (t1 - t0) * 1000.0
            endpoint_e2e_latencies.append(e2e_ms)
            assert resp.status_code == 200, f"/voice failed with {resp.status_code}: {resp.text}"
            print(f"  /voice endpoint call {idx+1}: {e2e_ms:>8.2f} ms ({e2e_ms/1000.0:.2f} s)")

    # ----------------------------------------------------
    # PHASE 4: COMPILE STATISTICS & JSON EXPORT
    # ----------------------------------------------------
    ffmpeg_dist = calculate_distribution(ffmpeg_latencies)
    stt_dist = calculate_distribution(stt_latencies)
    llm_dist = calculate_distribution(llm_latencies)
    tts_dist = calculate_distribution(tts_latencies)
    audio_io_dist = calculate_distribution(audio_io_latencies)
    total_dist = calculate_distribution(total_component_latencies)
    endpoint_dist = calculate_distribution(endpoint_e2e_latencies)

    results = {
        "ffmpeg_transcoding_ms": ffmpeg_dist,
        "deepgram_stt_ms": stt_dist,
        "langgraph_llm_chat_ms": llm_dist,
        "deepgram_tts_ms": tts_dist,
        "audio_io_isolated_ms": audio_io_dist,
        "total_component_e2e_ms": total_dist,
        "fastapi_voice_endpoint_ms": endpoint_dist,
        "time_to_first_audio_byte_note": "Batch REST architecture (/voice). Time-to-first-audio equals total completion time since audio is returned only after full synthesis.",
    }

    with open("benchmark-results/voice-benchmark.json", "w") as f:
        json.dump(results, f, indent=2)

    # Cleanup temp files
    import shutil
    shutil.rmtree("temp_voice_test", ignore_errors=True)

    print("\n" + "=" * 80)
    print("                    VOICE PIPELINE LATENCY BREAKDOWN                  ")
    print("=" * 80)
    print(f"{'Pipeline Stage':<35} | {'Avg (ms)':<10} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10}")
    print("-" * 80)
    print(f"{'1. FFmpeg Transcoding (WebM->WAV)':<35} | {ffmpeg_dist['avg']:>10.2f} | {ffmpeg_dist['p50']:>10.2f} | {ffmpeg_dist['p95']:>10.2f} | {ffmpeg_dist['p99']:>10.2f}")
    print(f"{'2. Deepgram STT (Nova-2)':<35} | {stt_dist['avg']:>10.2f} | {stt_dist['p50']:>10.2f} | {stt_dist['p95']:>10.2f} | {stt_dist['p99']:>10.2f}")
    print(f"{'3. LangGraph Agent + LLM Inference':<35} | {llm_dist['avg']:>10.2f} | {llm_dist['p50']:>10.2f} | {llm_dist['p95']:>10.2f} | {llm_dist['p99']:>10.2f}")
    print(f"{'4. Deepgram TTS (Aura-Asteria)':<35} | {tts_dist['avg']:>10.2f} | {tts_dist['p50']:>10.2f} | {tts_dist['p95']:>10.2f} | {tts_dist['p99']:>10.2f}")
    print("-" * 80)
    print(f"{'Isolated Audio I/O (STT+TTS+FFmpeg)':<35} | {audio_io_dist['avg']:>10.2f} | {audio_io_dist['p50']:>10.2f} | {audio_io_dist['p95']:>10.2f} | {audio_io_dist['p99']:>10.2f}")
    print(f"{'Full E2E Voice Response (Total)':<35} | {endpoint_dist['avg']:>10.2f} | {endpoint_dist['p50']:>10.2f} | {endpoint_dist['p95']:>10.2f} | {endpoint_dist['p99']:>10.2f}")
    print("=" * 80)


if __name__ == "__main__":
    run_voice_benchmark()
