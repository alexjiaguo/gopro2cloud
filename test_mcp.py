"""
test_mcp.py - Unit test for UniCloud FastMCP tools.
"""

from unittest.mock import patch, MagicMock
from unicloud.mcp_server import (
    cloud_list_remotes,
    cloud_browse,
    cloud_transfer_files,
    cloud_job_start,
    cloud_job_status,
    cloud_job_list,
    cloud_job_pause,
    cloud_job_resume,
    cloud_job_cancel,
)


def run_mcp_tests():
    print("=" * 60)
    print("Running UniCloud MCP Tool Tests...")
    print("=" * 60)

    # 1. Remotes listing
    with patch("unicloud.mcp_server.list_remotes", return_value=["gdrive:", "onedrive:"]):
        remotes = cloud_list_remotes()
        assert "gdrive:" in remotes
        assert "onedrive:" in remotes
    print("✓ MCP cloud_list_remotes passed")

    # 2. Synchronous file transfer tool
    mock_res = {"success": True, "mode": "copyto", "dest": "gdrive:dest/file.txt"}
    with patch("unicloud.mcp_server.execute_transfer", return_value=mock_res):
        res = cloud_transfer_files("file.txt", "gdrive:dest/", dry_run=True)
        assert res["success"] is True
    print("✓ MCP cloud_transfer_files passed")

    # 3. Job lifecycle via MCP
    mock_job = MagicMock(id="mcp123", status="running", pid=456, src="a", dest="b", log_file="/tmp/log")
    mock_job.to_dict.return_value = {"id": "mcp123", "status": "running"}

    with patch("unicloud.mcp_server.start_job", return_value=mock_job):
        started = cloud_job_start("src", "dest")
        assert started["success"] is True
        assert started["job_id"] == "mcp123"

    with patch("unicloud.mcp_server.get_job_status", return_value=mock_job):
        status = cloud_job_status("mcp123")
        assert status["success"] is True
        assert status["job"]["id"] == "mcp123"

    with patch("unicloud.mcp_server.pause_job", return_value=True):
        paused = cloud_job_pause("mcp123")
        assert paused["success"] is True

    with patch("unicloud.mcp_server.resume_job", return_value=True):
        resumed = cloud_job_resume("mcp123")
        assert resumed["success"] is True

    with patch("unicloud.mcp_server.cancel_job", return_value=True):
        canceled = cloud_job_cancel("mcp123")
        assert canceled["success"] is True
    print("✓ MCP cloud_job_* lifecycle tools passed")

    print("=" * 60)
    print("All MCP Tests PASSED! 🎉")
    print("=" * 60)


if __name__ == "__main__":
    run_mcp_tests()
