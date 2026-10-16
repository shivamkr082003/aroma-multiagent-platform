"""Run Aroma locally with one command: backend + frontend, each on a free port.

    python dev.py                 # migrations, then backend + frontend
    python dev.py --backend-only  # just the API
    python dev.py --no-migrate    # skip the database migration step

uvicorn stops with "Address already in use" when its port is taken, and the
frontend would not know about any other port anyway. This picks the first free
port from 8000 (API) and 3000 (web), and tells the frontend where the API is.
Ctrl+C (or closing the terminal) stops everything. Aroma servers left over from
an earlier run are stopped first, since Next.js allows one dev server per project.
"""

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def stop_leftover_servers() -> None:
    """Stop Aroma dev servers from a previous run (only this project's, matched by folder)."""
    try:
        import psutil
    except ImportError:
        return
    frontend = ROOT / "frontend"
    me = os.getpid()
    leftovers = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
        try:
            argv = proc.info["cmdline"] or []
            cwd = Path(proc.info["cwd"] or "/")
            name = proc.info["name"] or ""
        except (psutil.Error, OSError):
            continue
        if proc.info["pid"] == me or not argv:
            continue
        # Match the program and its arguments exactly, never a substring of a
        # command line: a shell whose command merely mentions "uvicorn main:app"
        # must not be mistaken for the server.
        program_names = [Path(arg).name for arg in argv]
        is_api = (cwd == ROOT and "main:app" in argv
                  and ("uvicorn" in program_names[:3] or argv[1:3] == ["-m", "uvicorn"]))
        is_web = cwd == frontend and (
            name.startswith("next-server")
            or (Path(argv[0]).name.startswith("node") and len(argv) > 2
                and Path(argv[1]).name == "next" and argv[2] == "dev")
        )
        if is_api or is_web:
            leftovers.append(proc)
    if not leftovers:
        return
    # Remember their ports so this run can take the same ones (same URL as before).
    held_ports = set()
    for proc in leftovers:
        try:
            held_ports |= {c.laddr.port for c in proc.net_connections(kind="tcp") if c.status == psutil.CONN_LISTEN}
        except (psutil.Error, AttributeError):
            pass
    print("→ Aroma is already running (another terminal or an earlier run): restarting it here…")
    for proc in leftovers:
        try:
            proc.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(leftovers, timeout=8)
    for proc in alive:
        try:
            proc.kill()
        except psutil.Error:
            pass
    # Give the OS a moment to release those ports, so this run gets the same ones again.
    for _ in range(20):
        if all(port_is_free(port) for port in held_ports):
            break
        time.sleep(0.5)


def port_is_free(port: int) -> bool:
    # Something already answering on the port means it's taken, whichever
    # address that server bound to.
    with socket.socket() as probe:
        probe.settimeout(0.3)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            return False
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def free_port(start: int) -> int:
    for port in range(start, start + 50):
        if port_is_free(port):
            return port
    sys.exit(f"No free port between {start} and {start + 49}.")


def wait_until_listening(port: int, proc: subprocess.Popen, timeout: float = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                # Make sure it's our process answering, not one that grabbed the port meanwhile.
                time.sleep(2)
                return proc.poll() is None
        time.sleep(0.5)
    return False


def stop(procs: list[subprocess.Popen]) -> None:
    for proc in procs:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)  # also stops uvicorn's reload worker / next's children
            except ProcessLookupError:
                pass
    for proc in procs:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # show progress immediately, even when piped to a file
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend-only", action="store_true", help="start only the API")
    parser.add_argument("--no-migrate", action="store_true", help="skip `scripts/migrate.py`")
    args = parser.parse_args()

    if not args.no_migrate:
        print("→ Updating the database schema…")
        if subprocess.run([sys.executable, "scripts/migrate.py"], cwd=ROOT).returncode != 0:
            sys.exit("Migration failed; fix the error above (or run with --no-migrate).")

    stop_leftover_servers()

    # Closing the terminal (SIGHUP) or `kill` (SIGTERM) must clean up like Ctrl+C;
    # otherwise the servers, started in their own sessions, outlive this script.
    def _as_interrupt(signum, frame):
        raise KeyboardInterrupt
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _as_interrupt)

    procs: list[subprocess.Popen] = []
    try:
        api_port = free_port(8000)
        if api_port != 8000:
            print(f"→ Port 8000 is busy, using {api_port} for the API")
        procs.append(subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", str(api_port)],
            cwd=ROOT, start_new_session=True,
        ))
        print(f"→ Starting the API on http://localhost:{api_port} (loading models can take ~30s)…")
        if not wait_until_listening(api_port, procs[0]):
            sys.exit("The API did not start; see the error above.")

        web_port = None
        if not args.backend_only:
            npm = shutil.which("npm") or sys.exit("npm not found: install Node.js to run the frontend.")
            web_port = free_port(3000)
            env = {**os.environ, "NEXT_PUBLIC_API_URL": f"http://localhost:{api_port}"}
            procs.append(subprocess.Popen(
                [npm, "run", "dev", "--", "-p", str(web_port)],
                cwd=ROOT / "frontend", env=env, start_new_session=True,
            ))
            if not wait_until_listening(web_port, procs[1], timeout=120):
                sys.exit("The frontend did not start; see the error above. If it says \"Another next dev "
                         "server is already running\", Aroma's frontend is already open in another terminal: "
                         "stop that `npm run dev` (Ctrl+C), then run this again.")

        print("\n" + "─" * 52)
        if web_port:
            print(f"  🌿 Aroma is running →  http://localhost:{web_port}")
        print(f"     API               →  http://localhost:{api_port}/docs")
        print("  Press Ctrl+C to stop.")
        print("─" * 52 + "\n")

        while all(p.poll() is None for p in procs):
            time.sleep(1)
        print("A process exited; stopping the rest.")
    except KeyboardInterrupt:
        print("\nStopping Aroma…")
    finally:
        stop(procs)


if __name__ == "__main__":
    main()
