"""
test_storage_uri.py - Unit tests for StorageURI parser and target resolution in UniCloud.
"""

import os
from unicloud.storage import StorageURI, parse_uri, resolve_target


def test_storage_uri():
    print("=" * 60)
    print("Running UniCloud StorageURI & Resolution Tests...")
    print("=" * 60)

    # 1. Test HTTP Stream
    stream_uri = parse_uri("http://172.28.158.51:80/videos/DCIM/100GOPRO/GX010475.MP4")
    assert stream_uri.uri_type == "stream"
    assert stream_uri.name == "GX010475.MP4"
    assert stream_uri.formatted() == "http://172.28.158.51:80/videos/DCIM/100GOPRO/GX010475.MP4"
    print("✓ HTTP stream parsing passed")

    # 2. Test Cloud Remote (Folder and File)
    remote_folder = parse_uri("gdrive:GoPro/Backups/")
    assert remote_folder.uri_type == "remote"
    assert remote_folder.remote_name == "gdrive"
    assert remote_folder.is_directory is True
    assert remote_folder.formatted() == "gdrive:GoPro/Backups/"

    remote_file = parse_uri("onedrive:Photos/sample.mp4")
    assert remote_file.uri_type == "remote"
    assert remote_file.remote_name == "onedrive"
    assert remote_file.is_directory is False
    assert remote_file.name == "sample.mp4"
    assert remote_file.formatted() == "onedrive:Photos/sample.mp4"
    print("✓ Cloud remote parsing (folder & file) passed")

    # 3. Test Local Paths
    local_path = parse_uri("/Volumes/Backup/Data")
    assert local_path.uri_type == "local"
    assert local_path.remote_name is None
    assert local_path.name == "Data"

    home_path = parse_uri("~/Documents/report.pdf")
    assert home_path.uri_type == "local"
    assert home_path.path == os.path.expanduser("~/Documents/report.pdf")
    assert home_path.is_directory is False
    assert home_path.name == "report.pdf"
    print("✓ Local filesystem path parsing passed")

    # 4. Test Target Resolution
    # Single file into remote folder
    src_file = parse_uri("/local/path/clip.mp4")
    dest_dir = parse_uri("gdrive:GoPro/")
    resolved = resolve_target(src_file, dest_dir)
    assert resolved.formatted() == "gdrive:GoPro/clip.mp4"
    assert resolved.is_directory is False

    # Single file into remote file (explicit name)
    dest_explicit = parse_uri("gdrive:GoPro/custom_name.mp4")
    resolved_explicit = resolve_target(src_file, dest_explicit)
    assert resolved_explicit.formatted() == "gdrive:GoPro/custom_name.mp4"

    # Directory into directory should remain as directory
    src_dir = parse_uri("/Volumes/Backup/")
    dest_remote_dir = parse_uri("s3:mybucket/backup")
    resolved_dir = resolve_target(src_dir, dest_remote_dir)
    assert resolved_dir.formatted() == "s3:mybucket/backup"
    print("✓ Target resolution logic passed")

    print("=" * 60)
    print("All StorageURI tests PASSED! 🎉")
    print("=" * 60)


if __name__ == "__main__":
    test_storage_uri()
