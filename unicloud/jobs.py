"""
unicloud.jobs - Persistent background job manager, queue, and process supervisor.
Replaces fragile PID and shell scripts with atomic state tracking, pause/resume, and live telemetry.
"""

import os
import sys
import json
import time
import uuid
import signal
import shutil
import tempfile
import subprocess
import threading
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

from unicloud.storage import parse_uri, resolve_target
from unicloud.core import RCLONE_BASE_FLAGS

DEFAULT_DATA_DIR = os.path.expanduser("~/.unicloud")
JOBS_FILE = os.path.join(DEFAULT_DATA_DIR, "jobs.json")
LOGS_DIR = os.path.join(DEFAULT_DATA_DIR, "logs")


def ensure_directories():
    """Ensure data and logs directories exist."""
    os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)


@dataclass
class Job:
    id: str
    src: str
    dest: str
    mode: str  # "copy" or "sync"
    status: str  # "running", "paused", "completed", "failed", "canceled"
    pid: Optional[int]
    transferred_bytes: int = 0
    total_bytes: int = 0
    percentage: float = 0.0
    speed: str = "0 B/s"
    eta: str = "unknown"
    current_file: Optional[str] = None
    log_file: str = ""
    error: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0
    extra_flags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        return cls(**data)


class JobStore:
    """Thread-safe, atomic JSON job storage."""
    _lock = threading.Lock()

    @classmethod
    def load_all(cls) -> Dict[str, Job]:
        ensure_directories()
        with cls._lock:
            if not os.path.exists(JOBS_FILE):
                return {}
            try:
                with open(JOBS_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    return {k: Job.from_dict(v) for k, v in raw.items()}
            except Exception:
                return {}

    @classmethod
    def save_all(cls, jobs: Dict[str, Job]):
        ensure_directories()
        with cls._lock:
            data = {k: v.to_dict() for k, v in jobs.items()}
            # Atomic write via temp file
            dir_name = os.path.dirname(JOBS_FILE)
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
                json.dump(data, tf, indent=2)
                temp_path = tf.name
            shutil.move(temp_path, JOBS_FILE)

    @classmethod
    def get(cls, job_id: str) -> Optional[Job]:
        jobs = cls.load_all()
        return jobs.get(job_id)

    @classmethod
    def update(cls, job: Job):
        jobs = cls.load_all()
        job.updated_at = time.time()
        jobs[job.id] = job
        cls.save_all(jobs)

    @classmethod
    def remove(cls, job_id: str):
        jobs = cls.load_all()
        if job_id in jobs:
            del jobs[job_id]
            cls.save_all(jobs)


def is_pid_alive(pid: Optional[int]) -> bool:
    """Check if process with given PID exists."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def parse_rclone_log_stats(log_file: str) -> dict:
    """Parse rclone --stats-one-line or json log output for telemetry."""
    if not os.path.exists(log_file):
        return {}

    stats = {
        "transferred": 0,
        "total": 0,
        "percentage": 0.0,
        "speed": "0 B/s",
        "eta": "unknown",
        "current_file": None,
    }

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        
        # Look backwards for latest progress line
        # Format example: " 1.250 GiB / 10.000 GiB, 12%, 35.40 MiB/s, ETA 4m12s"
        import re
        stats_regex = re.compile(
            r"([0-9.]+\s*[KMGT]?i?B)\s*/\s*([0-9.]+\s*[KMGT]?i?B),\s*([0-9.]+)%,\s*([0-9.]+\s*[KMGT]?i?B/s)(?:,\s*ETA\s*([^\s,]+))?"
        )
        for line in reversed(lines):
            m = stats_regex.search(line)
            if m:
                stats["percentage"] = float(m.group(3))
                stats["speed"] = m.group(4)
                stats["eta"] = m.group(5) or "unknown"
                break
    except Exception:
        pass

    return stats


def start_job(
    src: str,
    dest: str,
    mode: str = "copy",
    exclude_from: Optional[str] = None,
    extra_flags: Optional[List[str]] = None,
) -> Job:
    """
    Start an asynchronous, persistent background transfer job.
    Returns the initialized Job object.
    """
    ensure_directories()
    job_id = str(uuid.uuid4())[:8]
    log_file = os.path.join(LOGS_DIR, f"{job_id}.log")

    src_uri = parse_uri(src)
    dest_uri = parse_uri(dest)
    resolved_dest = resolve_target(src_uri, dest_uri)

    is_sync = (mode.lower() == "sync")
    if is_sync:
        subcmd = "sync"
    elif src_uri.uri_type == "stream":
        subcmd = "copyurl"
    elif not src_uri.is_directory and not (src_uri.uri_type == "local" and os.path.isdir(src_uri.path)):
        subcmd = "copyto"
    else:
        subcmd = "copy"

    cmd = [
        "rclone", subcmd,
        src_uri.formatted(),
        resolved_dest.formatted(),
    ] + RCLONE_BASE_FLAGS + [
        "--stats", "2s",
        "--stats-one-line",
        "--log-file", log_file,
        "--log-level", "INFO",
    ]

    if exclude_from:
        exp_exclude = os.path.expanduser(exclude_from)
        if os.path.exists(exp_exclude):
            cmd.extend(["--filter-from", exp_exclude])

    if extra_flags:
        cmd.extend(extra_flags)

    # Spawn process in independent session (survives shell closing)
    with open(log_file, "a") as log_out:
        log_out.write(f"--- UniCloud Job {job_id} Launched at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        log_out.write(f"Command: {' '.join(cmd)}\n\n")
        log_out.flush()

        proc = subprocess.Popen(
            cmd,
            stdout=log_out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    job = Job(
        id=job_id,
        src=src_uri.formatted(),
        dest=resolved_dest.formatted(),
        mode=subcmd,
        status="running",
        pid=proc.pid,
        log_file=log_file,
        created_at=time.time(),
        updated_at=time.time(),
        extra_flags=extra_flags or [],
    )

    JobStore.update(job)
    return job


def get_job_status(job_id: str) -> Optional[Job]:
    """Retrieve up-to-date status and telemetry for a job."""
    job = JobStore.get(job_id)
    if not job:
        return None

    # Check if process is still running if marked running
    if job.status == "running":
        if not is_pid_alive(job.pid):
            # Process terminated: inspect return status in log or mark completed
            telemetry = parse_rclone_log_stats(job.log_file)
            job.percentage = telemetry.get("percentage", 100.0) if telemetry else 100.0
            job.speed = "0 B/s"
            job.eta = "done"

            # Check if there were fatal errors in log
            has_error = False
            error_msg = None
            if os.path.exists(job.log_file):
                with open(job.log_file, "r", errors="ignore") as f:
                    content = f.read()
                    if "Failed to" in content or "ERROR :" in content:
                        for line in reversed(content.splitlines()):
                            if "ERROR :" in line or "Failed to" in line:
                                error_msg = line.strip()
                                has_error = True
                                break

            job.status = "failed" if has_error else "completed"
            job.error = error_msg
            job.pid = None
            JobStore.update(job)
        else:
            # Active: parse progress
            telemetry = parse_rclone_log_stats(job.log_file)
            if telemetry:
                job.percentage = telemetry.get("percentage", job.percentage)
                job.speed = telemetry.get("speed", job.speed)
                job.eta = telemetry.get("eta", job.eta)
                JobStore.update(job)

    return job


def list_jobs(status: Optional[str] = None) -> List[Job]:
    """List all registered jobs, optionally filtering by status."""
    all_jobs = list(JobStore.load_all().values())
    # Refresh statuses
    updated = []
    for j in all_jobs:
        refreshed = get_job_status(j.id)
        if refreshed:
            if status is None or refreshed.status.lower() == status.lower():
                updated.append(refreshed)
    # Sort by created_at descending
    updated.sort(key=lambda x: x.created_at, reverse=True)
    return updated


def pause_job(job_id: str) -> bool:
    """Pause an active background transfer job using SIGSTOP."""
    job = get_job_status(job_id)
    if not job:
        return False

    if job.status != "running" or not job.pid:
        return False

    try:
        os.kill(job.pid, signal.SIGSTOP)
        job.status = "paused"
        job.speed = "0 B/s (paused)"
        JobStore.update(job)
        return True
    except OSError:
        return False


def resume_job(job_id: str) -> bool:
    """Resume a paused transfer job. Sends SIGCONT if PID alive, or re-launches if process terminated."""
    job = get_job_status(job_id)
    if not job:
        return False

    if job.status not in ("paused", "failed"):
        return False

    if job.pid and is_pid_alive(job.pid):
        try:
            os.kill(job.pid, signal.SIGCONT)
            job.status = "running"
            JobStore.update(job)
            return True
        except OSError:
            pass

    # Process died or was suspended; re-launch transfer (rclone skips already transferred files)
    new_job = start_job(
        src=job.src,
        dest=job.dest,
        mode=job.mode,
        extra_flags=job.extra_flags,
    )
    # Adopt existing job ID
    JobStore.remove(new_job.id)
    job.pid = new_job.pid
    job.status = "running"
    job.log_file = new_job.log_file
    JobStore.update(job)
    return True


def cancel_job(job_id: str) -> bool:
    """Cancel and terminate an active or paused job."""
    job = get_job_status(job_id)
    if not job:
        return False

    if job.pid and is_pid_alive(job.pid):
        try:
            os.kill(job.pid, signal.SIGTERM)
            time.sleep(0.5)
            if is_pid_alive(job.pid):
                os.kill(job.pid, signal.SIGKILL)
        except OSError:
            pass

    job.status = "canceled"
    job.pid = None
    JobStore.update(job)
    return True
