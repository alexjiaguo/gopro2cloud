"""
test_web.py - Unit and integration tests for the UniCloud Web Dashboard and REST API.
"""

import time
import json
import urllib.request
import threading
from http.server import HTTPServer
from unittest.mock import patch, MagicMock

from unicloud.web import UniCloudWebHandler


def run_web_tests():
    print("=" * 60)
    print("Running UniCloud Web Dashboard & API Tests...")
    print("=" * 60)

    # Spin up test server on ephemeral port (8899)
    port = 8899
    server = HTTPServer(("127.0.0.1", port), UniCloudWebHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. Test HTML Dashboard
        req = urllib.request.urlopen(f"{base_url}/")
        assert req.status == 200
        html = req.read().decode("utf-8")
        assert "UniCloud" in html
        assert "Active Background Transfers" in html
        print("✓ HTML Dashboard rendering passed")

        # 2. Test GET /api/remotes
        with patch("unicloud.web.list_remotes", return_value=["gdrive:", "onedrive:"]):
            req = urllib.request.urlopen(f"{base_url}/api/remotes")
            assert req.status == 200
            data = json.loads(req.read().decode("utf-8"))
            assert "gdrive:" in data["remotes"]
            assert "free_disk_gb" in data
        print("✓ GET /api/remotes passed")

        # 3. Test GET /api/jobs
        req = urllib.request.urlopen(f"{base_url}/api/jobs")
        assert req.status == 200
        data = json.loads(req.read().decode("utf-8"))
        assert "jobs" in data
        assert isinstance(data["jobs"], list)
        print("✓ GET /api/jobs passed")

        # 4. Test GET /api/camera (offline fallback)
        req = urllib.request.urlopen(f"{base_url}/api/camera")
        assert req.status == 200
        data = json.loads(req.read().decode("utf-8"))
        assert "connected" in data
        print("✓ GET /api/camera passed")

        # 5. Test POST /api/jobs/start
        mock_job = MagicMock(id="web1234")
        with patch("unicloud.web.start_job", return_value=mock_job):
            payload = json.dumps({"src": "/local", "dest": "gdrive:dest"}).encode("utf-8")
            post_req = urllib.request.Request(
                f"{base_url}/api/jobs/start",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            resp = urllib.request.urlopen(post_req)
            assert resp.status == 200
            res_data = json.loads(resp.read().decode("utf-8"))
            assert res_data["success"] is True
            assert res_data["job_id"] == "web1234"
        print("✓ POST /api/jobs/start passed")

    finally:
        server.shutdown()
        server.server_close()

    print("=" * 60)
    print("All Web Dashboard Tests PASSED! 🎉")
    print("=" * 60)


if __name__ == "__main__":
    run_web_tests()
