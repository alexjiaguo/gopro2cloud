"""
unicloud.cli - Unified command-line interface for UniCloud.
"""

import sys
import os
import shutil
import argparse
import subprocess
from unicloud.storage import parse_uri
from unicloud.jobs import (
    start_job,
    get_job_status,
    list_jobs,
    pause_job,
    resume_job,
    cancel_job,
    Job,
)
from unicloud.core import (
    execute_transfer,
    list_remotes,
    discover_camera,
    list_camera_media,
    get_remote_index,
    get_free_disk_gb,
    sync_all,
    CameraNotFoundError,
)


def format_size(bytes_val: int) -> str:
    """Format bytes into human-readable string (MB/GB)."""
    if bytes_val >= 1024 ** 3:
        return f"{bytes_val / (1024 ** 3):.2f} GB"
    return f"{bytes_val / (1024 ** 2):.1f} MB"


# ==========================================
# Universal Cloud & Local CLI Handlers
# ==========================================

def cmd_cp(args):
    """Copy files or directories across local, cloud, or streams."""
    src = args.src
    dest = args.dest
    mode = "sync" if getattr(args, "sync", False) else "copy"

    action = "Sync" if mode == "sync" else "Copy"
    print("=" * 65)
    print(f"  UniCloud: {action}")
    print(f"  Source:      {src}")
    print(f"  Destination: {dest}")
    if args.dry_run:
        print("  [DRY RUN - No actual files transferred]")
    print("=" * 65)

    def on_prog(src_p, dest_p, msg):
        print(f"  {msg}")

    res = execute_transfer(
        src=src,
        dest=dest,
        mode=mode,
        dry_run=args.dry_run,
        on_progress=on_prog,
    )

    print("\n" + "=" * 65)
    if res["success"]:
        print(f"  [✓] {action} completed successfully.")
        print("=" * 65)
    else:
        print(f"  [✗] {action} failed.")
        if res.get("error"):
            print(f"  Error: {res['error']}")
        print("=" * 65)
        sys.exit(1)


def cmd_ls(args):
    """List contents of a local directory or remote cloud storage."""
    target = args.target.strip()
    target_uri = parse_uri(target)

    print(f"Listing: {target_uri.formatted()}\n")
    if target_uri.uri_type == "local":
        path = os.path.expanduser(target_uri.path)
        if not os.path.exists(path):
            print(f"Path does not exist: {path}", file=sys.stderr)
            sys.exit(1)
        if os.path.isfile(path):
            size = os.path.getsize(path)
            print(f"  {format_size(size):>10}  {os.path.basename(path)}")
        else:
            for item in sorted(os.listdir(path)):
                p = os.path.join(path, item)
                is_d = os.path.isdir(p)
                suffix = "/" if is_d else ""
                size_str = "<DIR>" if is_d else format_size(os.path.getsize(p))
                print(f"  {size_str:>10}  {item}{suffix}")
    else:
        cmd = ["rclone", "lsf", target_uri.formatted(), "-R" if args.recursive else ""]
        cmd = [c for c in cmd if c]
        proc = subprocess.run(cmd)
        if proc.returncode != 0:
            sys.exit(proc.returncode)


def cmd_remotes(args):
    """List all configured rclone cloud remotes."""
    remotes = list_remotes()
    print("=" * 60)
    print("              UniCloud: Connected Remotes")
    print("=" * 60)
    if not remotes:
        print("  No remotes configured. Run 'rclone config' to connect clouds.")
    else:
        for r in remotes:
            print(f"  ☁️  {r}")
    print("=" * 60)


def cmd_config(args):
    """Guided cloud configuration check and onboarding assistant."""
    print("=" * 60)
    print("           UniCloud: Cloud Provider Configuration")
    print("=" * 60)
    if shutil.which("rclone") is None:
        print("  [!] rclone is not found on your system PATH.")
        print("      Please install via: brew install rclone (macOS) or apt install rclone (Linux)")
        print("=" * 60)
        return

    remotes = list_remotes()
    print(f"  Connected Cloud Remotes ({len(remotes)} configured):")
    if remotes:
        for r in remotes:
            print(f"    • {r}")
    else:
        print("    (No remotes configured yet)")

    print("\n  To add a new cloud provider (Google Drive, OneDrive, Dropbox, S3, R2):")
    print("    Run: rclone config")
    print("    Follow the prompt and approve OAuth login in your browser popup.")
    print("=" * 60)


def cmd_web(args):
    """Launch the local interactive visual dashboard."""
    from unicloud.web import run_web_server
    port = getattr(args, "port", 8080)
    no_open = getattr(args, "no_open", False)
    run_web_server(port=port, open_browser=not no_open)


# ==========================================
# Background Jobs CLI Handlers
# ==========================================

def render_progress_bar(pct: float, width: int = 24) -> str:
    filled = int(width * (pct / 100.0))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:.1f}%"


def cmd_jobs_list(args):
    """List all background transfer jobs."""
    jobs = list_jobs(status=args.status if hasattr(args, "status") else None)
    print("=" * 80)
    print("                      UniCloud: Background Task Manager")
    print("=" * 80)
    if not jobs:
        print("  No active or historical jobs found.")
        print("  Start a new transfer with: unicloud jobs start <src> <dest>")
        print("=" * 80)
        return

    print(f"  {'ID':<10} {'STATUS':<12} {'MODE':<8} {'SPEED':<14} {'ETA':<10} {'TRANSFER'}")
    print("  " + "-" * 76)
    for j in jobs:
        status_badge = j.status.upper()
        if j.status == "running":
            status_badge = f"▶ {j.status.upper()}"
        elif j.status == "paused":
            status_badge = f"⏸ {j.status.upper()}"
        elif j.status == "completed":
            status_badge = f"✓ {j.status.upper()}"
        elif j.status == "failed":
            status_badge = f"✗ {j.status.upper()}"

        trans_str = f"{j.src} -> {j.dest}"
        if len(trans_str) > 30:
            trans_str = trans_str[:27] + "..."
        print(f"  {j.id:<10} {status_badge:<12} {j.mode:<8} {j.speed:<14} {j.eta:<10} {trans_str}")
    print("=" * 80)


def cmd_jobs_start(args):
    """Launch a background transfer job."""
    extra = []
    if getattr(args, "drive_root_folder_id", None):
        extra.extend(["--drive-root-folder-id", args.drive_root_folder_id])
    if getattr(args, "transfers", None):
        extra.extend(["--transfers", str(args.transfers)])
    if getattr(args, "checkers", None):
        extra.extend(["--checkers", str(args.checkers)])

    mode = "sync" if args.sync else "copy"
    job = start_job(
        src=args.src,
        dest=args.dest,
        mode=mode,
        exclude_from=args.exclude_from,
        extra_flags=extra,
    )

    print("=" * 65)
    print(f"  UniCloud: Background Job Launched")
    print("=" * 65)
    print(f"  Job ID:      {job.id}")
    print(f"  Status:      {job.status.upper()}")
    print(f"  Process PID: {job.pid}")
    print(f"  Mode:        {job.mode.upper()}")
    print(f"  Source:      {job.src}")
    print(f"  Destination: {job.dest}")
    print(f"  Log File:    {job.log_file}")
    print("-" * 65)
    print(f"  Monitor with:  unicloud jobs status {job.id}")
    print(f"  Pause with:    unicloud jobs pause {job.id}")
    print(f"  Cancel with:   unicloud jobs cancel {job.id}")
    print("=" * 65)


def cmd_jobs_status(args):
    """Inspect detailed real-time telemetry and status of a job."""
    job = get_job_status(args.job_id)
    if not job:
        print(f"Error: Job '{args.job_id}' not found.", file=sys.stderr)
        sys.exit(1)

    print("=" * 65)
    print(f"  UniCloud Job Telemetry: {job.id}")
    print("=" * 65)
    print(f"  Status:      {job.status.upper()} {'(PID: ' + str(job.pid) + ')' if job.pid else ''}")
    print(f"  Source:      {job.src}")
    print(f"  Destination: {job.dest}")
    print(f"  Mode:        {job.mode.upper()}")
    print(f"  Progress:    {render_progress_bar(job.percentage)}")
    print(f"  Speed:       {job.speed}")
    print(f"  ETA:         {job.eta}")
    if job.error:
        print(f"  Error:       {job.error}")

    print("-" * 65)
    print(f"  Recent Log Entries ({job.log_file}):")
    if os.path.exists(job.log_file):
        with open(job.log_file, "r", errors="ignore") as f:
            lines = [l.rstrip() for l in f.readlines() if l.strip()]
            for l in lines[-6:]:
                print(f"    {l}")
    else:
        print("    (No log output yet)")
    print("=" * 65)


def cmd_jobs_pause(args):
    """Pause an active job."""
    success = pause_job(args.job_id)
    if success:
        print(f"[✓] Job '{args.job_id}' paused successfully.")
    else:
        print(f"[✗] Failed to pause job '{args.job_id}'. Check if job is actively running.")
        sys.exit(1)


def cmd_jobs_resume(args):
    """Resume a paused or interrupted job."""
    success = resume_job(args.job_id)
    if success:
        print(f"[✓] Job '{args.job_id}' resumed successfully.")
    else:
        print(f"[✗] Failed to resume job '{args.job_id}'.")
        sys.exit(1)


def cmd_jobs_cancel(args):
    """Cancel and terminate a job."""
    success = cancel_job(args.job_id)
    if success:
        print(f"[✓] Job '{args.job_id}' canceled.")
    else:
        print(f"[✗] Failed to cancel job '{args.job_id}'.")
        sys.exit(1)


def cmd_jobs_log(args):
    """Display raw log file output for a job."""
    job = get_job_status(args.job_id)
    if not job or not os.path.exists(job.log_file):
        print(f"Log for job '{args.job_id}' not found.", file=sys.stderr)
        sys.exit(1)

    lines_to_show = getattr(args, "lines", 20)
    with open(job.log_file, "r", errors="ignore") as f:
        lines = f.readlines()
        for l in lines[-lines_to_show:]:
            print(l, end="")


# ==========================================
# Camera & Legacy Handlers
# ==========================================

def cmd_camera_status(args):
    print("=" * 60)
    print("      UniCloud: Camera & Cloud Status Check")
    print("=" * 60)
    
    print("1. Probing GoPro over USB...")
    try:
        cam = discover_camera(args.ip)
        media = list_camera_media(cam)
        total_bytes = sum(f["size"] for f in media)
        print(f"   [✓] Connected to GoPro at {cam['ip']}:{cam['port']}")
        print(f"       Found {len(media)} video files ({format_size(total_bytes)} total)")
    except CameraNotFoundError as e:
        print(f"   [✗] {e}")

    free_gb = get_free_disk_gb()
    print(f"\n2. Local host storage: {free_gb:.2f} GB free")

    dest = args.dest or os.getenv("GOPRO2CLOUD_DEST", "gdrive:GoPro")
    print(f"\n3. Cloud remote index: '{dest}'")
    idx = get_remote_index(dest)
    print(f"   [✓] Found {len(idx)} existing files already backed up in '{dest}'")
    print("=" * 60)


def cmd_camera_list(args):
    try:
        cam = discover_camera(args.ip)
    except CameraNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    media = list_camera_media(cam, include_lrv=args.include_lrv)
    if not media:
        print("No media files found on camera.")
        return

    by_date: dict[str, list] = {}
    for item in media:
        d = item["recorded_date"]
        by_date.setdefault(d, []).append(item)

    total_bytes = sum(f["size"] for f in media)
    print(f"\nFound {len(media)} files ({format_size(total_bytes)} total) across {len(by_date)} recording dates:\n")

    for d in sorted(by_date.keys()):
        files = by_date[d]
        d_size = sum(f["size"] for f in files)
        print(f"📁 {d}/ ({len(files)} files, {format_size(d_size)})")
        for f in files:
            print(f"   • {f['name']:<14} {format_size(f['size']):>10}  -> {d}/{f['name']}")
    print()


def cmd_camera_sync(args):
    dest = args.dest or os.getenv("GOPRO2CLOUD_DEST", "gdrive:GoPro")
    mode = args.mode or os.getenv("GOPRO2CLOUD_MODE", "stream")

    print("=" * 65)
    print(f"  UniCloud Camera Sync -> {dest}")
    print(f"  Mode: {mode.upper()} {'(Zero Local Disk)' if mode == 'stream' else '(Staged Cache)'}")
    if args.dry_run:
        print("  [DRY RUN - No files will be transferred]")
    print("=" * 65)

    def on_progress(idx, total, item, event, msg):
        prefix = f"[{idx}/{total}] {item['name']} ({format_size(item['size'])})"
        if event == "skipped":
            print(f"  {prefix}: [SKIPPED] {msg}")
        elif event == "starting":
            print(f"  {prefix}: [SYNC] {msg}")
        elif event == "completed":
            print(f"  {prefix}: [✓ DONE] {msg}")
        elif event == "fallback":
            print(f"  {prefix}: [!] {msg}")
        elif event == "failed":
            print(f"  {prefix}: [✗ FAILED] {msg}")
        elif event == "dry_run":
            print(f"  {prefix}: [PLAN] {msg}")

    try:
        results = sync_all(
            dest_remote=dest,
            mode=mode,
            include_lrv=args.include_lrv,
            dry_run=args.dry_run,
            override_ip=args.ip,
            on_progress=on_progress,
        )
    except CameraNotFoundError as e:
        print(f"\n[!] Camera error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 65)
    print(f"Sync Summary:")
    print(f"  Total on camera: {results['total_files']}")
    print(f"  Uploaded:        {len(results['uploaded'])}")
    print(f"  Skipped (exist): {len(results['skipped'])}")
    print(f"  Failed:          {len(results['failed'])}")
    print("=" * 65)

    if results["failed"]:
        sys.exit(2)


# Backward-compatible aliases for legacy gopro2cloud CLI functions
cmd_status = cmd_camera_status
cmd_list = cmd_camera_list
cmd_sync = cmd_camera_sync


# ==========================================
# Main CLI Entrypoint: unicloud
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        prog="unicloud",
        description="UniCloud: Universal multi-cloud transfer and local-to-cloud management platform."
    )
    parser.add_argument("--version", action="version", version="UniCloud v0.3.0")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # cp
    p_cp = subparsers.add_parser("cp", help="Copy files or directories across local, cloud, or streams")
    p_cp.add_argument("src", help="Source URI (e.g. /local/dir, gdrive:folder, http://stream)")
    p_cp.add_argument("dest", help="Destination URI (e.g. onedrive:target, /local/dest)")
    p_cp.add_argument("--dry-run", action="store_true", help="Simulate copy without transferring")

    # sync
    p_sync = subparsers.add_parser("sync", help="Synchronize directory (mirror source to destination)")
    p_sync.add_argument("src", help="Source directory URI")
    p_sync.add_argument("dest", help="Destination directory URI")
    p_sync.add_argument("--dry-run", action="store_true", help="Simulate sync without modifying files")

    # ls
    p_ls = subparsers.add_parser("ls", help="List directory contents of a local or cloud remote")
    p_ls.add_argument("target", help="Local directory or cloud remote (e.g. gdrive:Photos or /Volumes/Backup)")
    p_ls.add_argument("-R", "--recursive", action="store_true", help="Recursively list all files")

    # remotes
    subparsers.add_parser("remotes", help="List configured cloud storage accounts")

    # config
    subparsers.add_parser("config", help="Check and configure cloud storage provider remotes")

    # web / ui
    p_web = subparsers.add_parser("web", aliases=["ui"], help="Launch the visual interactive web dashboard")
    p_web.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    p_web.add_argument("--no-open", action="store_true", help="Do not automatically open browser")

    # jobs
    p_jobs = subparsers.add_parser("jobs", help="Manage background transfer jobs (start, pause, resume, cancel)")
    jobs_sub = p_jobs.add_subparsers(dest="job_command", help="Job action")

    # jobs list
    p_jl = jobs_sub.add_parser("list", help="List active and past background jobs")
    p_jl.add_argument("--status", choices=["running", "paused", "completed", "failed", "canceled"], help="Filter by status")

    # jobs start
    p_js = jobs_sub.add_parser("start", help="Launch a background transfer job")
    p_js.add_argument("src", help="Source URI (e.g. /Volumes/Backup or onedrive:Photos)")
    p_js.add_argument("dest", help="Destination URI (e.g. gdrive:graduate_period_files)")
    p_js.add_argument("--sync", action="store_true", help="Mirror source directory instead of copy")
    p_js.add_argument("--exclude-from", help="Path to exclude filter file")
    p_js.add_argument("--drive-root-folder-id", help="Google Drive root folder ID")
    p_js.add_argument("--transfers", type=int, default=4, help="Number of parallel file transfers (default: 4)")
    p_js.add_argument("--checkers", type=int, default=8, help="Number of parallel checksum checkers (default: 8)")

    # jobs status
    p_jst = jobs_sub.add_parser("status", help="Query real-time job telemetry and progress")
    p_jst.add_argument("job_id", help="Target Job ID")

    # jobs pause
    p_jp = jobs_sub.add_parser("pause", help="Pause an active transfer job")
    p_jp.add_argument("job_id", help="Target Job ID")

    # jobs resume
    p_jr = jobs_sub.add_parser("resume", help="Resume a paused or failed transfer job")
    p_jr.add_argument("job_id", help="Target Job ID")

    # jobs cancel
    p_jc = jobs_sub.add_parser("cancel", help="Cancel and terminate a background job")
    p_jc.add_argument("job_id", help="Target Job ID")

    # jobs log
    p_jlog = jobs_sub.add_parser("log", help="Inspect raw transfer log for a job")
    p_jlog.add_argument("job_id", help="Target Job ID")
    p_jlog.add_argument("-n", "--lines", type=int, default=25, help="Number of lines to show (default: 25)")

    # camera
    p_cam = subparsers.add_parser("camera", help="Camera and device streaming subcommands")
    cam_sub = p_cam.add_subparsers(dest="cam_command", help="Camera action")
    
    p_cam_stat = cam_sub.add_parser("status", help="Probe GoPro camera over USB")
    p_cam_stat.add_argument("--ip", help="GoPro IP override")
    p_cam_stat.add_argument("--dest", help="Cloud destination remote (e.g. gdrive:GoPro)")

    p_cam_list = cam_sub.add_parser("list", help="List camera media grouped by date")
    p_cam_list.add_argument("--ip", help="GoPro IP override")
    p_cam_list.add_argument("--include-lrv", action="store_true", help="Include LRV preview files")

    p_cam_sync = cam_sub.add_parser("sync", help="Offload GoPro directly to cloud storage")
    p_cam_sync.add_argument("--ip", help="GoPro IP override")
    p_cam_sync.add_argument("--dest", help="Cloud destination remote (default: gdrive:GoPro)")
    p_cam_sync.add_argument("--mode", choices=["stream", "staged"], default="stream")
    p_cam_sync.add_argument("--include-lrv", action="store_true")
    p_cam_sync.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "cp":
        args.sync = False
        cmd_cp(args)
    elif args.command == "sync":
        args.sync = True
        cmd_cp(args)
    elif args.command == "ls":
        cmd_ls(args)
    elif args.command == "remotes":
        cmd_remotes(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command in ("web", "ui"):
        cmd_web(args)
    elif args.command == "jobs":
        if args.job_command == "list" or not args.job_command:
            cmd_jobs_list(args)
        elif args.job_command == "start":
            cmd_jobs_start(args)
        elif args.job_command == "status":
            cmd_jobs_status(args)
        elif args.job_command == "pause":
            cmd_jobs_pause(args)
        elif args.job_command == "resume":
            cmd_jobs_resume(args)
        elif args.job_command == "cancel":
            cmd_jobs_cancel(args)
        elif args.job_command == "log":
            cmd_jobs_log(args)
        else:
            p_jobs.print_help()
            sys.exit(1)
    elif args.command == "camera":
        if args.cam_command == "status":
            cmd_camera_status(args)
        elif args.cam_command == "list":
            cmd_camera_list(args)
        elif args.cam_command == "sync":
            cmd_camera_sync(args)
        else:
            p_cam.print_help()
            sys.exit(1)


# ==========================================
# Legacy Entrypoints (Backwards Compatibility)
# ==========================================

def main_gopro_legacy():
    """Backwards-compatible entrypoint for 'gopro2cloud' command."""
    parser = argparse.ArgumentParser(
        prog="gopro2cloud",
        description="Stream and sync GoPro videos and cloud files directly to cloud storage."
    )
    parser.add_argument("--ip", help="Explicit GoPro IP override")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    p_status = subparsers.add_parser("status", help="Probe GoPro connection and cloud status")
    p_status.add_argument("--dest", help="Cloud destination remote (e.g. gdrive:GoPro)")

    p_list = subparsers.add_parser("list", help="List camera media grouped by recording date")
    p_list.add_argument("--include-lrv", action="store_true")

    p_sync = subparsers.add_parser("sync", help="Sync GoPro media to cloud storage")
    p_sync.add_argument("--dest", help="Cloud destination")
    p_sync.add_argument("--mode", choices=["stream", "staged"], default="stream")
    p_sync.add_argument("--include-lrv", action="store_true")
    p_sync.add_argument("--dry-run", action="store_true")

    p_cc = subparsers.add_parser("cloud-copy", aliases=["cloudcopy", "copy-cloud"])
    p_cc.add_argument("src", help="Source cloud path")
    p_cc.add_argument("dest", help="Destination cloud path")
    p_cc.add_argument("--dry-run", action="store_true")

    p_cs = subparsers.add_parser("cloud-sync", aliases=["cloudsync", "sync-cloud"])
    p_cs.add_argument("src", help="Source cloud folder")
    p_cs.add_argument("dest", help="Destination cloud folder")
    p_cs.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "status":
        cmd_camera_status(args)
    elif args.command == "list":
        cmd_camera_list(args)
    elif args.command == "sync":
        cmd_camera_sync(args)
    elif args.command in ("cloud-copy", "cloudcopy", "copy-cloud"):
        args.sync = False
        cmd_cp(args)
    elif args.command in ("cloud-sync", "cloudsync", "sync-cloud"):
        args.sync = True
        cmd_cp(args)


def main_cloudsync():
    """Backwards-compatible entrypoint for 'cloudsync' standalone command."""
    parser = argparse.ArgumentParser(
        prog="cloudsync",
        description="Direct in-memory cloud-to-cloud file copy and directory sync (zero local disk usage)."
    )
    parser.add_argument("src", help="Source cloud path")
    parser.add_argument("dest", help="Destination cloud path")
    parser.add_argument("--sync", action="store_true", help="Synchronize directory instead of copy")
    parser.add_argument("--dry-run", action="store_true", help="Simulate transfer")

    args = parser.parse_args()
    cmd_cp(args)


if __name__ == "__main__":
    main()
