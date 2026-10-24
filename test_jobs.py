"""
test_jobs.py - Unit and integration tests for UniCloud persistent job manager.
"""

import os
import time
import tempfile
from unittest.mock import patch, MagicMock

from unicloud.jobs import (
    Job,
    JobStore,
    start_job,
    get_job_status,
    pause_job,
    resume_job,
    cancel_job,
    list_jobs,
    parse_rclone_log_stats,
)


def run_job_tests():
    print("=" * 60)
    print("Running UniCloud Job Manager & Telemetry Tests...")
    print("=" * 60)

    # 1. Test JobStore atomic save and retrieval
    test_job = Job(
        id="test1234",
        src="/Volumes/Backup",
        dest="gdrive:Backup",
        mode="copy",
        status="running",
        pid=12345,
        created_at=time.time(),
        updated_at=time.time(),
    )
    JobStore.update(test_job)
    retrieved = JobStore.get("test1234")
    assert retrieved is not None, "Job was not retrieved from JobStore"
    assert retrieved.src == "/Volumes/Backup"
    assert retrieved.status == "running"
    print("✓ JobStore atomic save & load passed")

    # 2. Test rclone stats parsing
    with tempfile.NamedTemporaryFile("w", delete=False) as tf:
        tf.write("2026/10/24 21:00:00 INFO : Starting transfer...\n")
        tf.write(" 4.500 GiB / 10.000 GiB, 45%, 32.50 MiB/s, ETA 3m10s\n")
        log_path = tf.name

    stats = parse_rclone_log_stats(log_path)
    assert stats["percentage"] == 45.0, f"Expected 45%, got {stats['percentage']}"
    assert stats["speed"] == "32.50 MiB/s", f"Expected speed 32.50 MiB/s, got {stats['speed']}"
    assert stats["eta"] == "3m10s", f"Expected ETA 3m10s, got {stats['eta']}"
    os.remove(log_path)
    print("✓ Log telemetry parsing passed")

    # 3. Test start_job with mocked subprocess
    mock_proc = MagicMock()
    mock_proc.pid = 99999
    with patch("subprocess.Popen", return_value=mock_proc):
        job = start_job(
            src="/Volumes/Backup",
            dest="gdrive:Backup",
            mode="sync",
        )
        assert job.id is not None
        assert job.status == "running"
        assert job.pid == 99999
        assert JobStore.get(job.id) is not None
    print("✓ Job start and process registration passed")

    # 4. Test pause_job and resume_job signaling
    with patch("os.kill") as mock_kill:
        # Pause
        paused = pause_job(job.id)
        assert paused is True
        mock_kill.assert_called_with(99999, 17)  # SIGSTOP is 17 on macOS
        refreshed = JobStore.get(job.id)
        assert refreshed.status == "paused"

        # Resume (with alive pid)
        with patch("unicloud.jobs.is_pid_alive", return_value=True):
            resumed = resume_job(job.id)
            assert resumed is True
            mock_kill.assert_called_with(99999, 19)  # SIGCONT is 19 on macOS
            refreshed = JobStore.get(job.id)
            assert refreshed.status == "running"
    print("✓ Job pause and resume signalling passed")

    # 5. Test cancel_job
    with patch("os.kill") as mock_kill:
        with patch("unicloud.jobs.is_pid_alive", return_value=False):
            canceled = cancel_job(job.id)
            assert canceled is True
            refreshed = JobStore.get(job.id)
            assert refreshed.status == "canceled"
            assert refreshed.pid is None
    print("✓ Job cancellation passed")

    # Cleanup test job
    JobStore.remove("test1234")
    JobStore.remove(job.id)

    print("=" * 60)
    print("All Job Manager Tests PASSED! 🎉")
    print("=" * 60)


if __name__ == "__main__":
    run_job_tests()
