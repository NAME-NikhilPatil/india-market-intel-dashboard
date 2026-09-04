from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import IO, Mapping


def terminate_process_tree(proc: subprocess.Popen, grace_seconds: int = 10) -> None:
    """Stop a timed-out scraper and any Chromium children it launched."""
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
    except OSError:
        return

    try:
        proc.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except OSError:
        return
    proc.wait()


def run_step(
    command: list[str],
    cwd: Path,
    log_handle: IO[str],
    timeout_seconds: int | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> int:
    """Run one scraper step and return 124 after terminating a timeout."""
    log_handle.write("\n$ " + " ".join(command) + f"\n[cwd] {cwd}\n")
    if timeout_seconds:
        log_handle.write(f"[timeout] {timeout_seconds} seconds\n")
    log_handle.flush()

    popen_options: dict[str, object] = {}
    if os.name == "posix":
        # A new session lets us terminate Chromium and its driver together.
        popen_options["start_new_session"] = True
    elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        **popen_options,
    )
    try:
        return proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        log_handle.write(
            f"\nERROR: step timed out after {timeout_seconds} seconds; "
            "terminating process tree.\n"
        )
        log_handle.flush()
        terminate_process_tree(proc)
        return 124
