"""
gopro2cloud - Stream and sync GoPro videos and cloud files directly with zero local disk footprint.
"""

from gopro2cloud.core import (
    discover_camera,
    list_camera_media,
    get_remote_index,
    get_free_disk_gb,
    stream_upload_file,
    staged_upload_file,
    cloud_transfer,
    sync_all,
)

__version__ = "0.2.0"
__all__ = [
    "discover_camera",
    "list_camera_media",
    "get_remote_index",
    "get_free_disk_gb",
    "stream_upload_file",
    "staged_upload_file",
    "cloud_transfer",
    "sync_all",
]
