"""
test_unicloud.py - Comprehensive test suite for UniCloud universal transfers.
Tests local-to-cloud, cloud-to-cloud, cloud-to-local, stream-to-cloud, and CLI dispatch.
"""

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import unicloud
from unicloud.storage import parse_uri, resolve_target
from unicloud.core import execute_transfer, list_remotes
from unicloud.cli import main


def run_unicloud_tests():
    print("=" * 60)
    print("Running UniCloud Universal Engine & CLI Tests...")
    print("=" * 60)

    # 1. Package version & exports
    assert unicloud.__version__ == "0.3.0", f"Expected version 0.3.0, got {unicloud.__version__}"
    assert hasattr(unicloud, "execute_transfer")
    assert hasattr(unicloud, "StorageURI")
    print("✓ Package version & exports verified")

    mock_success = MagicMock(returncode=0, stdout="", stderr="")

    # 2. Local-to-Cloud single file transfer (copyto)
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
        with patch("unicloud.core.run_rclone", return_value=mock_success) as mock_rclone:
            res = execute_transfer(
                src=tmp_file.name,
                dest="gdrive:Documents/",
                mode="copy",
                dry_run=True,
            )
            assert res["success"] is True
            assert res["mode"] == "copyto"
            assert res["dest"] == f"gdrive:Documents/{os.path.basename(tmp_file.name)}"
            # Verify rclone command arguments
            cmd_called = mock_rclone.call_args[0][0]
            assert cmd_called[0] == "rclone"
            assert cmd_called[1] == "copyto"
            assert "--dry-run" in cmd_called
    print("✓ Local-to-Cloud single file (copyto) passed")

    # 3. Local-to-Cloud directory transfer (copy)
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("unicloud.core.run_rclone", return_value=mock_success) as mock_rclone:
            res = execute_transfer(
                src=tmp_dir,
                dest="s3:mybucket/backup",
                mode="copy",
                dry_run=True,
            )
            assert res["success"] is True
            assert res["mode"] == "copy"
            cmd_called = mock_rclone.call_args[0][0]
            assert cmd_called[1] == "copy"
    print("✓ Local-to-Cloud directory (copy) passed")

    # 4. Local-to-Cloud directory sync (sync)
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("unicloud.core.run_rclone", return_value=mock_success) as mock_rclone:
            res = execute_transfer(
                src=tmp_dir,
                dest="gdrive:Backup",
                mode="sync",
                dry_run=True,
            )
            assert res["success"] is True
            assert res["mode"] == "sync"
            cmd_called = mock_rclone.call_args[0][0]
            assert cmd_called[1] == "sync"
    print("✓ Local-to-Cloud directory sync passed")

    # 5. Cloud-to-Local download (copyto)
    with patch("unicloud.core.run_rclone", return_value=mock_success) as mock_rclone:
        res = execute_transfer(
            src="gdrive:Documents/contract.pdf",
            dest="~/Downloads/",
            mode="copy",
            dry_run=True,
        )
        assert res["success"] is True
        assert res["mode"] == "copyto"
        assert res["dest"] == os.path.expanduser("~/Downloads/contract.pdf")
        cmd_called = mock_rclone.call_args[0][0]
        assert cmd_called[1] == "copyto"
    print("✓ Cloud-to-Local file download passed")

    # 6. Stream-to-Cloud transfer (copyurl)
    with patch("unicloud.core.run_rclone", return_value=mock_success) as mock_rclone:
        res = execute_transfer(
            src="http://172.28.158.51/videos/DCIM/GX010475.MP4",
            dest="gdrive:GoPro/2026-09-27/",
            mode="copy",
            dry_run=True,
        )
        assert res["success"] is True
        assert res["mode"] == "copyurl"
        assert res["dest"] == "gdrive:GoPro/2026-09-27/GX010475.MP4"
        cmd_called = mock_rclone.call_args[0][0]
        assert cmd_called[1] == "copyurl"
    print("✓ Stream-to-Cloud zero-disk streaming passed")

    # 7. Remotes listing
    mock_remotes_proc = MagicMock(returncode=0, stdout="gdrive:\nonedrive:\ns3:\n", stderr="")
    with patch("subprocess.run", return_value=mock_remotes_proc):
        remotes = list_remotes()
        assert remotes == ["gdrive:", "onedrive:", "s3:"]
    print("✓ Remote listing passed")

    # 8. Test CLI dispatch
    with patch("sys.argv", ["unicloud", "cp", "/path/file.txt", "gdrive:dest/", "--dry-run"]):
        with patch("unicloud.cli.execute_transfer", return_value={"success": True, "mode": "copyto", "dest": "gdrive:dest/file.txt"}) as mock_exec:
            main()
            assert mock_exec.called
            assert mock_exec.call_args[1]["dry_run"] is True
    print("✓ CLI dispatch 'unicloud cp' passed")

    with patch("sys.argv", ["unicloud", "sync", "/path/dir", "gdrive:dest", "--dry-run"]):
        with patch("unicloud.cli.execute_transfer", return_value={"success": True, "mode": "sync", "dest": "gdrive:dest"}) as mock_exec:
            main()
            assert mock_exec.called
            assert mock_exec.call_args[1]["mode"] == "sync"
    print("✓ CLI dispatch 'unicloud sync' passed")

    # 9. Test CLI dispatch 'unicloud jobs'
    with patch("sys.argv", ["unicloud", "jobs", "list"]):
        with patch("unicloud.cli.list_jobs", return_value=[]) as mock_list:
            main()
            assert mock_list.called
    print("✓ CLI dispatch 'unicloud jobs list' passed")

    with patch("sys.argv", ["unicloud", "jobs", "start", "/Volumes/Backup", "gdrive:dest"]):
        mock_job = MagicMock(id="job1234", status="running", pid=123, mode="copy", src="/Volumes/Backup", dest="gdrive:dest", log_file="/tmp/log")
        with patch("unicloud.cli.start_job", return_value=mock_job) as mock_start:
            main()
            assert mock_start.called
            assert mock_start.call_args[1]["src"] == "/Volumes/Backup"
            assert mock_start.call_args[1]["dest"] == "gdrive:dest"
    print("✓ CLI dispatch 'unicloud jobs start' passed")

    # 10. Test CLI dispatch 'unicloud web'
    with patch("sys.argv", ["unicloud", "web", "--no-open"]):
        with patch("unicloud.cli.cmd_web") as mock_web:
            main()
            assert mock_web.called
    print("✓ CLI dispatch 'unicloud web' passed")

    print("=" * 60)
    print("All UniCloud Tests PASSED! 🎉")
    print("=" * 60)


if __name__ == "__main__":
    run_unicloud_tests()
