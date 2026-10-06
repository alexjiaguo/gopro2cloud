---
name: gopro-cloud-sync
description: Automatically discover connected GoPro cameras over USB, categorize videos by recording date, and stream them directly into Google Drive or other cloud storage with zero local disk usage. Triggers on "sync my GoPro", "upload GoPro videos", "backup camera".
---

# GoPro to Cloud Sync Assistant (`gopro-cloud-sync`)

Use this skill when the user wants to offload, sync, or backup footage from a GoPro camera to Google Drive or any other cloud storage service.

## Prerequisites & Architecture
- **Hardware Connection:** GoPro (HERO 9-13) connected via USB-C. The camera creates a virtual USB-Ethernet link (`172.2X.XXX.51:80`).
- **Engine:** Powered by `gopro2cloud` (`gopro2cloud/cli.py` or MCP tools `gopro_status`, `gopro_sync_start`).
- **Storage Backend:** Rclone (`gdrive:`, `dropbox:`, `s3:`, etc.).
- **Zero Local Disk Footprint:** Defaults to streaming directly over HTTP into the cloud without saving multi-gigabyte files to the laptop SSD.

---

## Standard Workflow Playbook

### 1. Pre-Flight Check (Connection & Storage)
Run `python3 -m gopro2cloud.cli status` (or call `gopro_status` via MCP):
- **If Camera Found:** Note camera IP, total file count, and aggregate size.
- **If Camera NOT Found:** Guide user with standard physical triage:
  1. Power ON the GoPro.
  2. Verify the USB-C cable is firmly plugged into both the GoPro and the computer.
  3. Ensure camera USB mode is set to MTP / GoPro Connect (Preferences > Connections > USB Connection).
  4. Wait ~5 seconds for macOS/Linux to initialize the virtual network interface.

### 2. Media Inventory & Confirmation
Run `python3 -m gopro2cloud.cli list` (or call `gopro_list_media`):
- Present a concise, user-friendly summary:
  - Total video files and total size (e.g. `24 files, 104.78 GB`).
  - Breakdown by recording date folders (e.g. `2026-09-27: 3 files`, `2026-09-28: 18 files`). Note that GoPro chaptered videos (`GX01xxxx`, `GX02xxxx`) are automatically kept together under Chapter 1's date.
- Confirm the target cloud destination (default: `gdrive:GoPro`).

### 3. Execution (Zero-Disk Streaming)
Run the sync command:
```bash
python3 -m gopro2cloud.cli sync --dest gdrive:GoPro
```
- By default, files stream directly from camera HTTP to Google Drive via `rclone copyurl`.
- Files already present in the cloud with matching name and size are **automatically skipped**.
- If a stream transfer drops, the engine automatically attempts a safe single-file staged fallback before moving to the next video.

### 4. Post-Sync Reporting & Safety Guard
- Present the final summary: total uploaded, skipped, and any failed items.
- **SAFETY GUARD:** NEVER offer to format or delete files from the GoPro SD card unless:
  1. 100% of files have been verified in the cloud.
  2. The user gives explicit, separate confirmation to wipe the card.
