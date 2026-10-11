"""
test_core.py - Self-contained unit & integration check for gopro2cloud.core.
Runs using Python standard library; requires zero external services or network access.
"""

import os
import sys
import json
import time
import shutil
import tempfile
from unittest.mock import patch, MagicMock
from gopro2cloud.core import (
    discover_camera,
    list_camera_media,
    parse_chapter_key,
    extract_recording_date,
    build_rclone_cmd,
    cleanup_staging_dir,
    cloud_transfer,
    sync_all,
    RCLONE_BASE_FLAGS,
    CameraNotFoundError,
    DiskSpaceError,
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

def run_tests():
    print("=" * 60)
    print("Running gopro2cloud Self-Checks & Regression Tests...")
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

    # 3. Test rclone command construction & resilience flags
    cmd = build_rclone_cmd("copyurl", ["http://camera/vid.mp4", "gdrive:GoPro/vid.mp4"])
    assert cmd[0] == "rclone" and cmd[1] == "copyurl"
    for flag in ["--drive-chunk-size", "--timeout", "--contimeout", "--retries", "--no-check-certificate"]:
        assert flag in cmd, f"Missing resilience flag: {flag}"
    print("✓ Rclone resilience flags & command builder passed")

    # 4. Test list_camera_media & chapter date unification
    cam_info = {
        "ip": "172.28.158.51",
        "port": 80,
        "endpoint": "/gp/gpMediaList",
        "download_base": "/videos/DCIM/100GOPRO/",
        "media_data": MOCK_MEDIA_DATA,
    }
    media = list_camera_media(cam_info, include_lrv=False)
    assert len(media) == 3, f"Expected 3 MP4 files, got {len(media)}"
    chap1 = next(m for m in media if m["name"] == "GX010475.MP4")
    chap2 = next(m for m in media if m["name"] == "GX020475.MP4")
    assert chap1["recorded_date"] == "2026-09-27"
    assert chap2["recorded_date"] == "2026-09-27", "Chapter 2 did not inherit Chapter 1 date"
    print("✓ Media listing and Chapter Date grouping test passed")

    # 5. Test staging directory cleanup
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "orphan.mp4")
        with open(test_file, "w") as f:
            f.write("stale_data")
        assert os.path.exists(test_file)
        cleared = cleanup_staging_dir(tmpdir)
        assert cleared == 1, f"Expected 1 cleared file, got {cleared}"
        assert not os.path.exists(test_file), "Orphan file was not removed"
    print("✓ Staging directory cleanup test passed")

    # 6. Test cloud_transfer command building (single file copyto vs folder copy/sync)
    mock_success = MagicMock(returncode=0, stdout="", stderr="")
    with patch("gopro2cloud.core.run_rclone", return_value=mock_success):
        res_single = cloud_transfer(
            src="onedrive:Photos/sample.mp4",
            dest="gdrive:GoPro/",
            dry_run=True,
        )
        assert res_single["mode"] == "copyto", f"Expected copyto mode for single file, got {res_single['mode']}"
        assert res_single["dest"] == "gdrive:GoPro/sample.mp4"
        assert res_single["dry_run"] is True
        assert res_single["success"] is True

        res_folder = cloud_transfer(
            src="onedrive:Brazil_Travel_2026",
            dest="gdrive:GoPro/Brazil_Travel_2026",
            is_sync=True,
            dry_run=True,
        )
        assert res_folder["mode"] == "sync", f"Expected sync mode for folder, got {res_folder['mode']}"
        assert res_folder["dest"] == "gdrive:GoPro/Brazil_Travel_2026"
        assert res_folder["success"] is True
    print("✓ Cloud-to-cloud transfer (single-file & folder sync) logic passed")

    # 7. Test dry_run sync_all with mocked camera
    with patch("gopro2cloud.core.discover_camera", return_value=cam_info):
        with patch("gopro2cloud.core.get_remote_index", return_value={}):
            results = sync_all(dest_remote="gdrive:GoPro", mode="stream", dry_run=True)
            assert len(results["uploaded"]) == 3, f"Expected 3 dry_run uploads, got {len(results['uploaded'])}"
    print("✓ Dry run sync with mocked camera passed")

    # 8. Test CameraNotFoundError when camera is unreachable
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        try:
            discover_camera(override_ip="192.0.2.1")
            assert False, "Expected CameraNotFoundError"
        except CameraNotFoundError:
            print("✓ CameraNotFoundError gracefully raised when camera offline")

    # 9. Test CloudSync feature exports and CLI entrypoints
    import gopro2cloud
    assert gopro2cloud.__version__ == "0.2.0", f"Unexpected version: {gopro2cloud.__version__}"
    assert hasattr(gopro2cloud, "cloud_transfer"), "cloud_transfer not exported in gopro2cloud"
    from gopro2cloud.cli import main_cloudsync
    assert callable(main_cloudsync), "main_cloudsync is not callable"
    print("✓ CloudSync package export & CLI entrypoint test passed")

    print("=" * 60)
    print("All gopro2cloud core checks & regression tests PASSED! 🎉")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
