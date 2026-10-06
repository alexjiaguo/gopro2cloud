"""
test_core.py - Self-contained unit & integration check for gopro2cloud.core.
Runs using Python standard library http.server; requires zero external services.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from gopro2cloud.core import (
    discover_camera,
    list_camera_media,
    parse_chapter_key,
    extract_recording_date,
    sync_all,
    CameraNotFoundError,
)

# Mock GoPro media JSON
MOCK_MEDIA_DATA = {
    "id": "1234567890",
    "media": [{
        "d": "100GOPRO",
        "fs": [
            # Day 1: Chapter 1 recorded at 1790508438 (2026-09-27)
            {"n": "GX010475.MP4", "cre": "1790508438", "mod": "1790508438", "s": "1000"},
            # Day 1 Chapter 2 recorded 20 minutes later (still shares Chapter 1 date)
            {"n": "GX020475.MP4", "cre": "1790509638", "mod": "1790509638", "s": "2000"},
            # Day 2: Single file recorded at 1790594298 (2026-09-28)
            {"n": "GX010476.MP4", "cre": "1790594298", "mod": "1790594298", "s": "3000"},
            # LRV file (should be excluded by default)
            {"n": "GL010475.LRV", "cre": "1790508438", "mod": "1790508438", "s": "100"},
        ]
    }]
}

class MockGoProHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet logs during test

    def do_GET(self):
        if self.path == "/gp/gpMediaList":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(MOCK_MEDIA_DATA).encode("utf-8"))
        elif self.path.startswith("/videos/DCIM/100GOPRO/"):
            filename = os.path.basename(self.path)
            # Find dummy size
            content = b"TEST_VIDEO_DATA_" + filename.encode()
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()


def run_tests():
    print("=" * 60)
    print("Running gopro2cloud Self-Checks...")
    print("=" * 60)

    # 1. Test chapter parsing
    base_id, chap = parse_chapter_key("GX010475.MP4")
    assert base_id == "0475" and chap == 1, f"Failed parse chapter: {base_id}, {chap}"
    base_id2, chap2 = parse_chapter_key("GX020475.MP4")
    assert base_id2 == "0475" and chap2 == 2, f"Failed parse chapter 2: {base_id2}, {chap2}"
    print("✓ Chapter key parsing test passed")

    # 2. Test recording date formatting
    d = extract_recording_date(1790508438)
    assert d == "2026-09-27", f"Expected 2026-09-27, got {d}"
    print("✓ Date extraction test passed")

    # 3. Start local mock GoPro server
    server = HTTPServer(("127.0.0.1", 0), MockGoProHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        # Test discovery on local port
        cam_info = discover_camera(override_ip="127.0.0.1", override_port=port)

        # Test list_camera_media
        media = list_camera_media(cam_info, include_lrv=False)
        assert len(media) == 3, f"Expected 3 MP4 files, got {len(media)}"
        
        # Verify chapter 2 shares chapter 1's date
        chap1 = next(m for m in media if m["name"] == "GX010475.MP4")
        chap2 = next(m for m in media if m["name"] == "GX020475.MP4")
        assert chap1["recorded_date"] == "2026-09-27", f"Expected 2026-09-27, got {chap1['recorded_date']}"
        assert chap2["recorded_date"] == "2026-09-27", f"Chapter 2 date {chap2['recorded_date']} didn't match Chapter 1"
        print("✓ Media listing and Chapter Date grouping test passed")

        # Test dry-run sync
        results = sync_all(
            dest_remote="local-test",
            mode="stream",
            dry_run=True,
            override_ip="127.0.0.1",
            override_port=port,
        )
        assert len(results["uploaded"]) == 3, f"Expected 3 dry_run files, got {len(results['uploaded'])}"
        print("✓ Dry run sync test passed")

    finally:
        server.shutdown()
        server.server_close()

    # 4. Test camera not found error
    try:
        discover_camera(override_ip="192.0.2.1")  # TEST-NET non-routable IP
        assert False, "Expected CameraNotFoundError"
    except CameraNotFoundError:
        print("✓ CameraNotFoundError gracefully raised when camera offline")

    print("=" * 60)
    print("All gopro2cloud core checks PASSED successfully! 🎉")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
