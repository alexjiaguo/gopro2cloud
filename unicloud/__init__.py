"""
UniCloud - Universal Multi-Cloud Management & Transfer Platform.
Supports local-to-cloud, cloud-to-cloud, and device-to-cloud zero-disk streaming.
"""

from unicloud.storage import StorageURI, parse_uri, resolve_target
from unicloud.core import (
    execute_transfer,
    cloud_transfer,
    list_remotes,
    discover_camera,
    list_camera_media,
    get_remote_index,
    get_free_disk_gb,
    stream_upload_file,
    staged_upload_file,
    sync_all,
    CameraNotFoundError,
    DiskSpaceError,
    TransferError,
)
from unicloud.jobs import (
    Job,
    start_job,
    get_job_status,
    list_jobs,
    pause_job,
    resume_job,
    cancel_job,
)

__version__ = "0.3.0"
__all__ = [
    "StorageURI",
    "parse_uri",
    "resolve_target",
    "execute_transfer",
    "cloud_transfer",
    "list_remotes",
    "discover_camera",
    "list_camera_media",
    "get_remote_index",
    "get_free_disk_gb",
    "stream_upload_file",
    "staged_upload_file",
    "sync_all",
    "CameraNotFoundError",
    "DiskSpaceError",
    "TransferError",
    "Job",
    "start_job",
    "get_job_status",
    "list_jobs",
    "pause_job",
    "resume_job",
    "cancel_job",
]
