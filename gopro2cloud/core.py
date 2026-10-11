"""
gopro2cloud.core - Core logic for discovering GoPro over USB, listing media,
indexing cloud targets, and executing resilient streaming / staged uploads.
"""

import os
import re
import sys
import json
import time
import shutil
import urllib.request
import urllib.error
import subprocess
from datetime import datetime, timezone

# Ensure rclone respects local network environment/proxies without cert errors
os.environ.setdefault("RCLONE_NO_CHECK_CERTIFICATE", "true")

# Standard default probe ports and endpoints for OpenGoPro
PROBE_ENDPOINTS = [
    {"port": 80, "path": "/gp/gpMediaList", "download_base": "/videos/DCIM/100GOPRO/"},
    {"port": 8080, "path": "/gopro/media/list", "download_base": "/videos/DCIM/100GOPRO/"},
]

# Standard resilient flags for rclone cloud transfers
# ponytail: Standardized timeouts and chunk sizes to prevent proxy socket drops
# and zombie rclone processes observed in multi-gigabyte transfers.
RCLONE_BASE_FLAGS = [
    "--drive-chunk-size", "16M",
    "--timeout", "30s",
    "--contimeout", "15s",
    "--retries", "5",
    "--low-level-retries", "10",
    "--no-check-certificate",
]

def build_rclone_cmd(subcmd: str, args: list[str]) -> list[str]:
    """Build rclone command with resilience flags positioned right after subcommand."""
    return ["rclone", subcmd] + RCLONE_BASE_FLAGS + list(args)

def run_rclone(
    cmd: list[str],
    timeout: int | None = None,
    capture_output: bool = False,
    max_retries: int = 3,
    retry_delay: float = 3.0,
) -> subprocess.CompletedProcess:
    """
    Execute rclone with standardized resilience flags, timeouts, and automatic retry on failure.
    """
    final_cmd = list(cmd)
    if final_cmd and final_cmd[0] == "rclone":
        if "--drive-chunk-size" not in final_cmd:
            if len(final_cmd) > 1 and not final_cmd[1].startswith("-"):
                final_cmd = [final_cmd[0], final_cmd[1]] + RCLONE_BASE_FLAGS + final_cmd[2:]
            else:
                final_cmd = [final_cmd[0]] + RCLONE_BASE_FLAGS + final_cmd[1:]

    last_proc = None
    for attempt in range(1, max_retries + 1):
        try:
            res = subprocess.run(
                final_cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
            )
            if res.returncode == 0:
                return res
            last_proc = res
        except subprocess.TimeoutExpired as e:
            last_proc = subprocess.CompletedProcess(
                args=final_cmd,
                returncode=124,
                stdout="",
                stderr=f"Command timed out after {timeout}s: {e}",
            )
        except Exception as e:
            last_proc = subprocess.CompletedProcess(
                args=final_cmd,
                returncode=1,
                stdout="",
                stderr=str(e),
            )

        if attempt < max_retries:
            time.sleep(retry_delay)

    return last_proc or subprocess.CompletedProcess(args=final_cmd, returncode=1, stdout="", stderr="Transfer failed")

class CameraNotFoundError(Exception):
    """Raised when GoPro camera cannot be located or reached over USB."""
    pass

class DiskSpaceError(Exception):
    """Raised when available host disk space is insufficient for staged caching."""
    pass



def discover_camera(override_ip: str | None = None, override_port: int | None = None) -> dict:
    """
    Locate connected GoPro over USB network interface and return active endpoint info.
    """
    candidate_ips = []
    
    # 1. Environment variable or explicit override
    env_ip = override_ip or os.getenv("GOPRO_IP")
    if env_ip:
        candidate_ips.append(env_ip.strip())
    else:
        # 2. Probe local network interfaces (macOS/Linux ifconfig or ip)
        try:
            proc = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=3)
            if proc.returncode == 0:
                for match in re.finditer(r"inet\s+(172\.\d+\.\d+)\.\d+", proc.stdout):
                    subnet = match.group(1)
                    camera_ip = f"{subnet}.51"
                    if camera_ip not in candidate_ips:
                        candidate_ips.append(camera_ip)
        except Exception:
            pass

        # Fallback default known GoPro USB IP
        if "172.28.158.51" not in candidate_ips:
            candidate_ips.append("172.28.158.51")

    # Probe candidates against known HTTP endpoints
    for ip in candidate_ips:
        for ep in PROBE_ENDPOINTS:
            port = override_port if override_port else ep["port"]
            url = f"http://{ip}:{port}{ep['path']}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "gopro2cloud"})
                with urllib.request.urlopen(req, timeout=2.5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if "media" in data:
                            return {
                                "ip": ip,
                                "port": port,
                                "endpoint": ep["path"],
                                "download_base": ep["download_base"],
                                "media_data": data,
                            }
            except Exception:
                continue

    raise CameraNotFoundError(
        "Could not communicate with GoPro over USB.\n"
        "  1. Ensure the GoPro is powered ON.\n"
        "  2. Verify USB-C cable is firmly plugged in (Preferences > Connections > USB Connection > MTP or GoPro Connect).\n"
        "  3. Wait 5-10 seconds for the USB-Ethernet link to establish."
    )


def extract_recording_date(epoch_timestamp: int | str) -> str:
    """
    Convert GoPro creation epoch timestamp to YYYY-MM-DD string.
    """
    ts = int(epoch_timestamp)
    # GoPro timestamps are local unix timestamps
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d")


def parse_chapter_key(filename: str) -> tuple[str, int]:
    """
    Parse GoPro filename into (base_id, chapter_number).
    Examples:
      GX010475.MP4 -> ('0475', 1)
      GX020475.MP4 -> ('0475', 2)
      GH010123.MP4 -> ('0123', 1)
      GOPR0123.MP4 -> ('0123', 0)
    """
    m = re.match(r"^(?:GX|GH)(\d{2})(\d{4})\.MP4$", filename, re.IGNORECASE)
    if m:
        chapter = int(m.group(1))
        base_id = m.group(2)
        return (base_id, chapter)
    
    m_legacy = re.match(r"^GOPR(\d{4})\.MP4$", filename, re.IGNORECASE)
    if m_legacy:
        return (m_legacy.group(1), 0)

    # Fallback: whole filename
    return (filename, 0)


def list_camera_media(camera_info: dict, include_lrv: bool = False) -> list[dict]:
    """
    Parse media list from camera JSON.
    Groups chaptered videos so all chapters share Chapter 1's recording date.
    """
    raw_media = camera_info.get("media_data", {}).get("media", [])
    raw_files = []
    for item in raw_media:
        raw_files.extend(item.get("fs", []))

    if not raw_files:
        return []

    # Map chapter 1 (or earliest chapter) dates per base_id
    chapter_dates: dict[str, str] = {}
    parsed_items = []

    for f in raw_files:
        name = f.get("n", "")
        size = int(f.get("s", 0))
        created_ts = int(f.get("cre", 0))
        rec_date = extract_recording_date(created_ts) if created_ts else "Unknown-Date"

        is_mp4 = name.upper().endswith(".MP4")
        is_lrv = name.upper().endswith(".LRV") or name.upper().endswith(".THM")

        if not is_mp4 and not (include_lrv and is_lrv):
            continue

        base_id, chapter = parse_chapter_key(name)
        if base_id not in chapter_dates or chapter <= 1:
            chapter_dates[base_id] = rec_date

        parsed_items.append({
            "name": name,
            "size": size,
            "created_ts": created_ts,
            "raw_date": rec_date,
            "base_id": base_id,
            "download_url": f"http://{camera_info['ip']}:{camera_info['port']}{camera_info['download_base']}{name}",
        })

    # Assign unified chapter date
    for item in parsed_items:
        base_id = item["base_id"]
        item["recorded_date"] = chapter_dates.get(base_id, item["raw_date"])

    return parsed_items


def cleanup_staging_dir(staging_dir: str) -> int:
    """
    Remove orphaned files in staging directory to prevent disk space deadlocks.
    Returns number of cleared items.
    """
    expanded = os.path.expanduser(staging_dir)
    if not os.path.exists(expanded):
        return 0
    cleared = 0
    for name in os.listdir(expanded):
        p = os.path.join(expanded, name)
        try:
            if os.path.isfile(p):
                os.remove(p)
                cleared += 1
            elif os.path.isdir(p):
                shutil.rmtree(p)
                cleared += 1
        except OSError:
            pass
    return cleared


def get_remote_index(dest_remote: str) -> dict[str, int]:
    """
    Recursively inspect destination cloud directory via rclone lsjson.
    Returns mapping of {filename: size_in_bytes} regardless of subfolder.
    """
    dest = dest_remote.rstrip("/")
    cmd = ["rclone", "lsjson", "-R", "--files-only", dest]
    try:
        proc = run_rclone(cmd, timeout=45, capture_output=True, max_retries=2)
        if proc.returncode == 0:
            entries = json.loads(proc.stdout)
            # Map filename -> size
            index = {}
            for item in entries:
                fname = os.path.basename(item.get("Path", ""))
                fsize = int(item.get("Size", 0))
                if fname:
                    index[fname] = fsize
            return index
    except Exception:
        pass
    return {}


def get_free_disk_gb(path: str = ".") -> float:
    """Return available disk space in GB."""
    expanded = os.path.expanduser(path)
    os.makedirs(expanded, exist_ok=True)
    total, used, free = shutil.disk_usage(expanded)
    return free / (1024 ** 3)


def stream_upload_file(file_info: dict, dest_remote: str) -> bool:
    """
    Stream video directly from GoPro HTTP socket into cloud storage via rclone copyurl.
    Zero local disk usage. Uses dynamic process timeout to prevent dead socket stalls.
    """
    target = f"{dest_remote.rstrip('/')}/{file_info['recorded_date']}/{file_info['name']}"
    cmd = [
        "rclone", "copyurl",
        file_info["download_url"],
        target,
        "-P", "--stats-one-line"
    ]
    size_mb = int(file_info.get("size", 0) / (1024 * 1024))
    dynamic_timeout = max(300, size_mb + 300)
    ret = run_rclone(cmd, timeout=dynamic_timeout)
    return ret.returncode == 0


def staged_upload_file(file_info: dict, dest_remote: str, staging_dir: str) -> bool:
    """
    Download single video to local staging directory, upload via rclone move,
    and immediately evict local file to preserve disk space.
    """
    expanded_staging = os.path.expanduser(staging_dir)
    # Proactively clean orphaned leftovers from previous aborted runs
    cleanup_staging_dir(expanded_staging)

    size_gb = file_info["size"] / (1024 ** 3)
    free_gb = get_free_disk_gb(expanded_staging)
    if free_gb < (size_gb + 2.0):
        raise DiskSpaceError(
            f"Insufficient local disk space for staging {file_info['name']}. "
            f"Needs {size_gb + 2.0:.1f} GB, but only {free_gb:.1f} GB free."
        )

    os.makedirs(expanded_staging, exist_ok=True)
    local_path = os.path.join(expanded_staging, file_info["name"])
    target_folder = f"{dest_remote.rstrip('/')}/{file_info['recorded_date']}"

    # Download chunked with socket timeout
    try:
        req = urllib.request.Request(file_info["download_url"], headers={"User-Agent": "gopro2cloud"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(local_path, "wb") as out:
            shutil.copyfileobj(resp, out, length=4 * 1024 * 1024)

        # Upload & move via rclone with resilience flags & bounded timeout
        size_mb = int(file_info.get("size", 0) / (1024 * 1024))
        dynamic_timeout = max(300, size_mb + 300)
        cmd = ["rclone", "move", local_path, target_folder, "-P", "--stats-one-line"]
        ret = run_rclone(cmd, timeout=dynamic_timeout)
        return ret.returncode == 0
    finally:
        # Guarantee cleanup even on error
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass


def cloud_transfer(
    src: str,
    dest: str,
    is_sync: bool = False,
    dry_run: bool = False,
    on_progress: callable = None,
) -> dict:
    """
    Direct cloud-to-cloud file or folder transfer (e.g. OneDrive to Google Drive)
    with zero local disk usage. Supports single files (copyto) and folders (copy/sync).
    """
    src_clean = src.strip()
    dest_clean = dest.strip()

    # Determine whether src is likely a single file or a folder
    src_path = src_clean.split(":")[-1] if ":" in src_clean else src_clean
    dest_path = dest_clean.split(":")[-1] if ":" in dest_clean else dest_clean

    _, ext = os.path.splitext(src_path)
    is_single_file = bool(ext and not src_clean.endswith("/"))

    if is_single_file:
        subcmd = "copyto"
        _, dest_ext = os.path.splitext(dest_path)
        if not dest_ext or dest_clean.endswith("/"):
            fname = os.path.basename(src_path.rstrip("/"))
            final_dest = f"{dest_clean.rstrip('/')}/{fname}"
        else:
            final_dest = dest_clean
    else:
        subcmd = "sync" if is_sync else "copy"
        final_dest = dest_clean

    cmd = ["rclone", subcmd, src_clean, final_dest, "-P", "--stats-one-line"]
    if dry_run:
        cmd.append("--dry-run")

    if on_progress:
        mode_str = "DRY RUN" if dry_run else subcmd.upper()
        on_progress(src_clean, final_dest, f"Starting cloud-to-cloud {mode_str}...")

    ret = run_rclone(cmd, capture_output=False, max_retries=3)
    success = (ret.returncode == 0)

    if on_progress:
        status_msg = "Completed successfully" if success else f"Failed (exit code {ret.returncode})"
        on_progress(src_clean, final_dest, status_msg)

    return {
        "success": success,
        "src": src_clean,
        "dest": final_dest,
        "mode": subcmd,
        "dry_run": dry_run,
        "returncode": ret.returncode,
        "error": ret.stderr if not success else None,
    }


def sync_all(
    dest_remote: str = "gdrive:GoPro",
    mode: str = "stream",
    include_lrv: bool = False,
    dry_run: bool = False,
    override_ip: str | None = None,
    override_port: int | None = None,
    staging_dir: str = "~/Movies/GoPro_Staging",
    on_progress: callable = None,
) -> dict:
    """
    High-level orchestrator:
    1. Discovers camera
    2. Lists media with dated folder categorization
    3. Indexes target cloud storage
    4. Skips already-uploaded files
    5. Streams (or stages) remaining files with automatic single-file fallback
    """
    expanded_staging = os.path.expanduser(staging_dir)
    # Pre-clean staging directory to reclaim any orphaned space
    cleanup_staging_dir(expanded_staging)

    camera = discover_camera(override_ip, override_port=override_port)
    media_files = list_camera_media(camera, include_lrv=include_lrv)
    cloud_index = get_remote_index(dest_remote)

    results = {
        "camera_ip": camera["ip"],
        "total_files": len(media_files),
        "uploaded": [],
        "skipped": [],
        "failed": [],
    }

    for idx, item in enumerate(media_files, start=1):
        name = item["name"]
        size = item["size"]
        size_gb = size / (1024 ** 3)
        date_folder = item["recorded_date"]

        # Check deduplication
        if name in cloud_index and cloud_index[name] == size:
            results["skipped"].append({"name": name, "size": size, "recorded_date": date_folder})
            if on_progress:
                on_progress(idx, len(media_files), item, "skipped", f"Already exists in {date_folder}/")
            continue

        if dry_run:
            results["uploaded"].append({"name": name, "size": size, "recorded_date": date_folder, "mode": "dry_run"})
            if on_progress:
                on_progress(idx, len(media_files), item, "dry_run", f"Planned -> {dest_remote}/{date_folder}/{name}")
            continue

        # Execute upload
        if on_progress:
            on_progress(idx, len(media_files), item, "starting", f"Uploading ({mode}) -> {date_folder}/")

        success = False
        mode_used = mode

        if mode == "stream":
            success = stream_upload_file(item, dest_remote)
            if not success:
                # Decision B: Automatic fallback retry in staged mode
                try:
                    if on_progress:
                        on_progress(idx, len(media_files), item, "fallback", "Streaming failed, falling back to staged mode...")
                    success = staged_upload_file(item, dest_remote, expanded_staging)
                    if success:
                        mode_used = "staged_fallback"
                except Exception as ex:
                    results["failed"].append({"name": name, "error": str(ex)})
                    continue
        else:
            try:
                success = staged_upload_file(item, dest_remote, expanded_staging)
            except Exception as ex:
                results["failed"].append({"name": name, "error": str(ex)})
                continue

        if success:
            results["uploaded"].append({"name": name, "size": size, "recorded_date": date_folder, "mode_used": mode_used})
            if on_progress:
                on_progress(idx, len(media_files), item, "completed", f"Saved to {date_folder}/{name} [{mode_used}]")
        else:
            results["failed"].append({"name": name, "error": "rclone process returned non-zero code"})
            if on_progress:
                on_progress(idx, len(media_files), item, "failed", "Upload failed")

    return results
