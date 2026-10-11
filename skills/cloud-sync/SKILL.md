---
name: cloud-sync
description: Transfer and synchronize files and directories directly between cloud storage providers (OneDrive, Google Drive, Dropbox, AWS S3) with zero local disk usage. Triggers on "sync cloud folders", "cloud sync", "transfer from OneDrive to Google Drive", "cloud-to-cloud copy".
---

# Cloud-to-Cloud Sync Assistant (`cloud-sync`)

Use this skill when the user wants to copy or synchronize single files or complete directory hierarchies between two cloud storage accounts (e.g., OneDrive, Google Drive, Dropbox, AWS S3, Cloudflare R2) without consuming laptop SSD space.

## Key Principles & Architecture
- **Zero Local Disk Footprint:** All transfers stream in-memory across cloud provider APIs. No files are downloaded or staged locally.
- **Engine:** Powered by `gopro2cloud` / `cloudsync` via `rclone` with standardized resilience parameters:
  - `--drive-chunk-size 16M` (prevents TCP socket freeze over proxies or residential networks)
  - `--timeout 30s` & `--contimeout 15s` (aborts dead connections quickly)
  - `--retries 5` & `--low-level-retries 10`
  - `--no-check-certificate` (bypasses MITM proxy TLS verification errors)
- **Automatic Deduplication:** Files matching in size and timestamp on the destination are skipped instantly.

---

## Standard Workflow Playbook

### 1. Pre-Flight Remote Inspection
Check existing remote connections and inventory source/target files:
```bash
# Check configured remotes
rclone listremotes

# Audit source folder size and file count
rclone size "<source-remote>:<source-path>" --timeout 30s --no-check-certificate

# Check destination folder
rclone lsf "<dest-remote>:<dest-path>" --timeout 30s --no-check-certificate
```

### 2. Dry-Run Preview
Always run with `--dry-run` to preview the exact transfer list before making remote modifications:
```bash
# Using gopro2cloud CLI
gopro2cloud cloud-sync "<source-remote>:<source-path>" "<dest-remote>:<dest-path>" --dry-run

# Or using the standalone cloudsync command
cloudsync "<source-remote>:<source-path>" "<dest-remote>:<dest-path>" --dry-run
```

### 3. Execution (Zero Local Disk)

#### Single File Copy (`copyto`):
```bash
gopro2cloud cloud-copy "<source-remote>:<path>/file.mp4" "<dest-remote>:<path>/"
```

#### Full Directory Synchronization (`sync` / `copy`):
```bash
# Non-destructive copy (leaves files on destination that don't exist on source)
gopro2cloud cloud-copy "<source-remote>:<folder>" "<dest-remote>:<folder>"

# Full sync (reconciles destination directory)
gopro2cloud cloud-sync "<source-remote>:<folder>" "<dest-remote>:<folder>"
```

### 4. Post-Transfer Audit
Verify that all files and byte sizes match between source and destination:
```bash
rclone check "<source-remote>:<folder>" "<dest-remote>:<folder>" --one-way --no-check-certificate
```
