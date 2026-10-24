"""
unicloud.mcp_server - FastMCP server exposing universal multi-cloud transfer,
remote browsing, and GoPro streaming to AI assistants.
"""

import os
import sys
import uuid
import threading
import subprocess
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("unicloud")
except ImportError:
    # Fallback mock for environments without mcp installed
    class FastMCPMock:
        def __init__(self, name):
            self.name = name
        def tool(self):
            def decorator(f):
                return f
            return decorator
        def run(self):
            print("FastMCP is not installed. Run 'pip install mcp>=1.0.0' to enable MCP server.")
    mcp = FastMCPMock("unicloud")

from unicloud.storage import parse_uri
from unicloud.jobs import (
    start_job,
    get_job_status,
    list_jobs,
    pause_job,
    resume_job,
    cancel_job,
)
from unicloud.core import (
    execute_transfer,
    cloud_transfer,
    list_remotes,
    discover_camera,
    list_camera_media,
    get_remote_index,
    get_free_disk_gb,
    sync_all,
    CameraNotFoundError,
)

# Background job registry
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


@mcp.tool()
def cloud_list_remotes() -> list[str]:
    """
    List all configured cloud storage remotes (e.g. gdrive:, onedrive:, dropbox:, s3:).
    """
    return list_remotes()


@mcp.tool()
def cloud_transfer_files(
    src: str,
    dest: str,
    mode: str = "copy",
    dry_run: bool = False,
) -> dict:
    """
    Universal transfer files or directories across local storage, cloud remotes, or HTTP streams.
    Modes:
      - "copy": Copy single file or directory
      - "sync": Reconcile/mirror destination directory to match source
    Examples:
      - Local to Cloud: src="/Volumes/Backup", dest="gdrive:Backup"
      - Cloud to Cloud: src="onedrive:Photos", dest="gdrive:Photos"
      - Cloud to Local: src="gdrive:Docs/file.pdf", dest="~/Downloads/file.pdf"
    """
    return execute_transfer(
        src=src,
        dest=dest,
        mode=mode,
        dry_run=dry_run,
    )


@mcp.tool()
def cloud_browse(remote_path: str, recursive: bool = False) -> dict:
    """
    Browse files and folders inside a local directory or cloud remote.
    Example: remote_path="gdrive:GoPro" or remote_path="/Volumes/Backup"
    """
    uri = parse_uri(remote_path)
    if uri.uri_type == "local":
        path = os.path.expanduser(uri.path)
        if not os.path.exists(path):
            return {"success": False, "error": f"Path not found: {path}", "entries": []}
        entries = []
        for item in sorted(os.listdir(path)):
            p = os.path.join(path, item)
            entries.append({
                "name": item,
                "is_dir": os.path.isdir(p),
                "size": os.path.getsize(p) if os.path.isfile(p) else 0,
            })
        return {"success": True, "path": path, "entries": entries}
    else:
        cmd = ["rclone", "lsjson", uri.formatted()]
        if recursive:
            cmd.insert(2, "-R")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if proc.returncode == 0:
                import json
                return {"success": True, "path": uri.formatted(), "entries": json.loads(proc.stdout)}
            return {"success": False, "error": proc.stderr, "entries": []}
        except Exception as e:
            return {"success": False, "error": str(e), "entries": []}


@mcp.tool()
def cloud_job_start(
    src: str,
    dest: str,
    mode: str = "copy",
    exclude_from: str = "",
    drive_root_folder_id: str = "",
) -> dict:
    """
    Launch a persistent, background transfer task (survives session exits).
    Supports pause, resume, progress monitoring, and retry.
    """
    extra = []
    if drive_root_folder_id:
        extra.extend(["--drive-root-folder-id", drive_root_folder_id])
    
    job = start_job(
        src=src,
        dest=dest,
        mode=mode,
        exclude_from=exclude_from if exclude_from else None,
        extra_flags=extra if extra else None,
    )
    return {
        "success": True,
        "job_id": job.id,
        "status": job.status,
        "pid": job.pid,
        "src": job.src,
        "dest": job.dest,
        "log_file": job.log_file,
    }


@mcp.tool()
def cloud_job_status(job_id: str) -> dict:
    """
    Query real-time transfer telemetry (percentage, speed, ETA, status) for a background job.
    """
    job = get_job_status(job_id)
    if not job:
        return {"success": False, "error": f"Job '{job_id}' not found."}
    return {"success": True, "job": job.to_dict()}


@mcp.tool()
def cloud_job_list(status: str = "") -> list[dict]:
    """
    List all registered background transfer jobs with current states and speeds.
    """
    jobs = list_jobs(status=status if status else None)
    return [j.to_dict() for j in jobs]


@mcp.tool()
def cloud_job_pause(job_id: str) -> dict:
    """
    Pause an active background transfer job.
    """
    success = pause_job(job_id)
    return {"success": success, "job_id": job_id, "status": "paused" if success else "failed"}


@mcp.tool()
def cloud_job_resume(job_id: str) -> dict:
    """
    Resume a paused or interrupted background transfer job.
    """
    success = resume_job(job_id)
    return {"success": success, "job_id": job_id, "status": "running" if success else "failed"}


@mcp.tool()
def cloud_job_cancel(job_id: str) -> dict:
    """
    Cancel and terminate an active or paused background transfer job.
    """
    success = cancel_job(job_id)
    return {"success": success, "job_id": job_id, "status": "canceled" if success else "failed"}


@mcp.tool()
def gopro_status(override_ip: str = "") -> dict:
    """
    Check GoPro USB connection status, host free disk space, and cloud remotes.
    """
    status_info = {
        "camera_connected": False,
        "camera_ip": None,
        "media_count": 0,
        "total_size_gb": 0.0,
        "free_disk_gb": round(get_free_disk_gb(), 2),
        "available_remotes": list_remotes(),
        "error": None,
    }

    try:
        cam = discover_camera(override_ip if override_ip else None)
        media = list_camera_media(cam)
        total_bytes = sum(f["size"] for f in media)

        status_info["camera_connected"] = True
        status_info["camera_ip"] = f"{cam['ip']}:{cam['port']}"
        status_info["media_count"] = len(media)
        status_info["total_size_gb"] = round(total_bytes / (1024 ** 3), 2)
    except CameraNotFoundError as e:
        status_info["error"] = str(e)
    except Exception as e:
        status_info["error"] = f"Unexpected error: {e}"

    return status_info


@mcp.tool()
def gopro_list_media(include_lrv: bool = False, override_ip: str = "") -> dict:
    """
    List all media on the connected GoPro grouped by recording date.
    """
    try:
        cam = discover_camera(override_ip if override_ip else None)
    except CameraNotFoundError as e:
        return {"success": False, "error": str(e), "files": []}

    media = list_camera_media(cam, include_lrv=include_lrv)
    by_date: dict[str, list] = {}
    for item in media:
        d = item["recorded_date"]
        by_date.setdefault(d, []).append({
            "name": item["name"],
            "size_mb": round(item["size"] / (1024 ** 2), 1),
            "size_bytes": item["size"],
            "target_path": f"{d}/{item['name']}",
        })

    return {
        "success": True,
        "total_files": len(media),
        "total_gb": round(sum(f["size"] for f in media) / (1024 ** 3), 2),
        "dates": by_date,
    }


@mcp.tool()
def gopro_sync_start(
    dest_remote: str = "gdrive:GoPro",
    mode: str = "stream",
    include_lrv: bool = False,
    dry_run: bool = False,
    override_ip: str = "",
) -> dict:
    """
    Start an asynchronous background sync job of GoPro media to the cloud.
    """
    job_id = str(uuid.uuid4())[:8]

    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "status": "running",
            "dest_remote": dest_remote,
            "mode": mode,
            "dry_run": dry_run,
            "current_file": None,
            "current_progress": None,
            "uploaded": [],
            "skipped": [],
            "failed": [],
            "error": None,
        }

    def worker():
        def on_prog(idx, total, item, event, msg):
            with _LOCK:
                job = _JOBS.get(job_id)
                if not job:
                    return
                job["current_file"] = f"[{idx}/{total}] {item['name']}"
                job["current_progress"] = msg

        try:
            res = sync_all(
                dest_remote=dest_remote,
                mode=mode,
                include_lrv=include_lrv,
                dry_run=dry_run,
                override_ip=override_ip if override_ip else None,
                on_progress=on_prog,
            )
            with _LOCK:
                job = _JOBS.get(job_id)
                if job:
                    job["status"] = "completed"
                    job["uploaded"] = res["uploaded"]
                    job["skipped"] = res["skipped"]
                    job["failed"] = res["failed"]
        except Exception as ex:
            with _LOCK:
                job = _JOBS.get(job_id)
                if job:
                    job["status"] = "failed"
                    job["error"] = str(ex)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Sync job {job_id} launched in background targeting '{dest_remote}'.",
    }


@mcp.tool()
def gopro_sync_progress(job_id: str) -> dict:
    """
    Query the real-time progress and summary of a GoPro sync background job.
    """
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return {"error": f"Job ID '{job_id}' not found."}
        return dict(job)


@mcp.tool()
def cloud_copy(src: str, dest: str, dry_run: bool = False) -> dict:
    """
    Direct cloud-to-cloud file copy (backwards compatibility).
    """
    return execute_transfer(src=src, dest=dest, mode="copy", dry_run=dry_run)


@mcp.tool()
def cloud_sync(src: str, dest: str, dry_run: bool = False) -> dict:
    """
    Direct cloud-to-cloud folder synchronization (backwards compatibility).
    """
    return execute_transfer(src=src, dest=dest, mode="sync", dry_run=dry_run)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
