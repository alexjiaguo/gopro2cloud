---
name: cloud-manager
description: Manage universal cloud storage, backup local files to cloud, transfer cross-cloud, and supervise background transfer tasks (pause, resume, telemetry). Triggers on "backup to cloud", "upload to Google Drive", "cloud transfer", "check cloud backup", "sync cloud", "unicloud".
---

# UniCloud Universal Cloud Manager (`cloud-manager`)

Use this skill when the user wants to upload local files or directories to cloud storage, transfer data between cloud accounts (Google Drive, OneDrive, Dropbox, AWS S3, Cloudflare R2), or orchestrate resilient background jobs with pause, resume, and real-time speed monitoring.

---

## ⚡ Core Capabilities

1. **Universal Matrix**:
   - **Local ↔ Cloud**: Upload folders/files (`/Volumes/Backup`), SD cards, or download cloud assets.
   - **Cloud ↔ Cloud**: Transfer directly with zero laptop SSD space.
   - **Device ↔ Cloud**: Stream GoPro video over USB directly to cloud storage.
2. **Persistent Task Supervisor**:
   - Launch background jobs that survive terminal disconnection.
   - Live telemetry: percentage progress bar, MB/s speed, ETA, and logs.
   - Pause (`kill -STOP`), Resume (`kill -CONT` / restart checkpoint), and Cancel anytime.
3. **Enterprise Resilience**:
   - Automatic chunk sizing, rate pacing, retries, and token refresh.

---

## 🚀 CLI Commands Reference

### 1. File & Directory Transfer
```bash
# Upload local file or folder to cloud
unicloud cp /Volumes/Backup gdrive:Backups/
unicloud sync /Volumes/Backup gdrive:Backups/ --dry-run

# Direct cloud-to-cloud transfer (zero local disk)
unicloud cp onedrive:Photos/sample.mp4 gdrive:GoPro/
unicloud sync onedrive:Vacation gdrive:Backup/Vacation

# Browse remote or local storage
unicloud ls gdrive:Photos
unicloud ls /Volumes/Backup -R

# List connected clouds
unicloud remotes
unicloud config
```

### 2. Background Task Management
```bash
# Start background backup job
unicloud jobs start /Volumes/Backup gdrive:graduate_period_files --exclude-from backup_exclude.txt

# List active and past jobs
unicloud jobs list

# Check real-time progress and speed
unicloud jobs status <job_id>

# Pause / Resume / Cancel
unicloud jobs pause <job_id>
unicloud jobs resume <job_id>
unicloud jobs cancel <job_id>

# View job transfer logs
unicloud jobs log <job_id> -n 50
```

### 3. GoPro Camera Stream
```bash
# Probe camera over USB
unicloud camera status

# Stream camera directly to cloud
unicloud camera sync --dest gdrive:GoPro
```

---

## 🤖 MCP Tool Integration
AI agents can invoke UniCloud directly using these FastMCP tools:
- `cloud_list_remotes()`: Lists connected cloud accounts.
- `cloud_browse(remote_path)`: Explores directories on any cloud or local drive.
- `cloud_transfer_files(src, dest, mode, dry_run)`: Performs transfers.
- `cloud_job_start(src, dest, mode, exclude_from)`: Launches background job.
- `cloud_job_status(job_id)`: Fetches live progress and transfer rate.
- `cloud_job_pause(job_id)` / `cloud_job_resume(job_id)` / `cloud_job_cancel(job_id)`: Manages job lifecycle.
- `gopro_status()` / `gopro_sync_start()`: Controls GoPro USB camera streaming.
