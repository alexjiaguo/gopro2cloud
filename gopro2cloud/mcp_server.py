"""
gopro2cloud.mcp_server - FastMCP server exposing GoPro discovery, media listing,
and asynchronous cloud sync to AI agents (Antigravity, Claude, Cursor, Windsurf).
"""

import os
import sys
import uuid
import threading
import subprocess
from mcp.server.fastmcp import FastMCP
from gopro2cloud.core import (
    discover_camera,
    list_camera_media,
    get_remote_index,
    get_free_disk_gb,
    sync_all,
    CameraNotFoundError,
)

mcp = FastMCP("gopro2cloud")

# Background job registry
# ponytail: In-memory job registry. Jobs are lost if server restarts, but
# deduplication makes re-running safe with zero wasted bandwidth.
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()

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
        "available_remotes": cloud_list_remotes(),
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
    Each recording date folder is ready for cloud categorization.
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
def cloud_list_remotes() -> list[str]:
    """
    List all configured rclone cloud storage remotes (e.g. gdrive:, dropbox:).
    """
    try:
        proc = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            return [r.strip() for r in proc.stdout.splitlines() if r.strip()]
    except Exception:
        pass
    return []

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
    Returns a job_id that can be polled with gopro_sync_progress(job_id).
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
        "message": f"Sync job {job_id} launched in background targeting '{dest_remote}'. Use gopro_sync_progress('{job_id}') to inspect status.",
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
def gopro_sync_cancel(job_id: str) -> dict:
    """
    Cancel an active background sync job.
    """
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return {"error": f"Job ID '{job_id}' not found."}
        job["status"] = "canceled"
        return {"job_id": job_id, "status": "canceled"}

def main():
    mcp.run()

if __name__ == "__main__":
    main()
