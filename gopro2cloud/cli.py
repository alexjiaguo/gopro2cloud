"""
gopro2cloud.cli - Command-line interface for gopro2cloud.
"""

import sys
import os
import argparse
from gopro2cloud.core import (
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

def cmd_status(args):
    print("=" * 60)
    print("      gopro2cloud: Camera & Cloud Status Check")
    print("=" * 60)
    
    # 1. Camera
    print("1. Probing GoPro over USB...")
    try:
        cam = discover_camera(args.ip)
        media = list_camera_media(cam)
        total_bytes = sum(f["size"] for f in media)
        print(f"   [✓] Connected to GoPro at {cam['ip']}:{cam['port']}")
        print(f"       Found {len(media)} video files ({format_size(total_bytes)} total)")
    except CameraNotFoundError as e:
        print(f"   [✗] {e}")

    # 2. Local Disk
    free_gb = get_free_disk_gb()
    print(f"\n2. Local host storage: {free_gb:.2f} GB free")

    # 3. Cloud Remote
    dest = args.dest or os.getenv("GOPRO2CLOUD_DEST", "gdrive:GoPro")
    print(f"\n3. Cloud remote index: '{dest}'")
    idx = get_remote_index(dest)
    print(f"   [✓] Found {len(idx)} existing files already backed up in '{dest}'")
    print("=" * 60)

def cmd_list(args):
    try:
        cam = discover_camera(args.ip)
    except CameraNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    media = list_camera_media(cam, include_lrv=args.include_lrv)
    if not media:
        print("No media files found on camera.")
        return

    # Group by recording date
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

def cmd_sync(args):
    dest = args.dest or os.getenv("GOPRO2CLOUD_DEST", "gdrive:GoPro")
    mode = args.mode or os.getenv("GOPRO2CLOUD_MODE", "stream")

    print("=" * 65)
    print(f"  gopro2cloud sync -> {dest}")
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

def main():
    parser = argparse.ArgumentParser(
        prog="gopro2cloud",
        description="Stream and sync GoPro videos directly to any cloud storage."
    )
    parser.add_argument("--ip", help="Explicit GoPro IP override (default: auto-discover)")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # status
    p_status = subparsers.add_parser("status", help="Probe GoPro connection and cloud status")
    p_status.add_argument("--dest", help="Cloud destination remote (e.g. gdrive:GoPro)")

    # list
    p_list = subparsers.add_parser("list", help="List camera media grouped by recording date")
    p_list.add_argument("--include-lrv", action="store_true", help="Include .LRV preview files")

    # sync
    p_sync = subparsers.add_parser("sync", help="Sync GoPro media to cloud storage")
    p_sync.add_argument("--dest", help="Cloud destination (default: $GOPRO2CLOUD_DEST or gdrive:GoPro)")
    p_sync.add_argument("--mode", choices=["stream", "staged"], default="stream", help="Upload mode (default: stream)")
    p_sync.add_argument("--include-lrv", action="store_true", help="Include .LRV preview files")
    p_sync.add_argument("--dry-run", action="store_true", help="Simulate sync without uploading")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "status":
        cmd_status(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "sync":
        cmd_sync(args)

if __name__ == "__main__":
    main()
