# 📝 Release Notes & Changelog

All notable changes to `gopro2cloud` are documented in this file.  
Format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - 2026-10-24

### 🌟 Major Evolution: Universal Cloud Management Platform (`UniCloud`)
- **Universal Transfer Engine (`StorageURI`):** Evolved from a GoPro-only tool into a universal multi-cloud orchestrator. Seamlessly transfers files between Local Storage (`/Volumes/Backup`, `~/Documents`), 40+ Cloud Providers (`gdrive:`, `onedrive:`, `dropbox:`, `s3:`, `r2:`), and HTTP Streaming devices.
- **Persistent Task Supervisor & Queue:**
  - Replaces fragile shell scripts (`backup.pid`, `start_backup.sh`, `pause_backup.sh`) with an atomic JSON-backed job daemon (`unicloud jobs`).
  - Pause (`SIGSTOP`), Resume (`SIGCONT` / checkpoint restart), and Cancel transfers anytime.
  - Live progress monitoring with real-time transfer speed (MB/s), percentage complete, and ETA calculation.
- **Visual Interactive Web Dashboard (`unicloud web` / `unicloud ui`):**
  - Dependency-free local web interface running on `http://localhost:8080`.
  - Storage gauges for local host and connected clouds.
  - Live task queue table with interactive Pause/Resume/Cancel buttons.
  - Quick transfer launcher for point-and-click data migrations.
- **Unified Modern CLI (`unicloud`):**
  - Canonical commands: `unicloud cp`, `unicloud sync`, `unicloud ls`, `unicloud remotes`, `unicloud config`, `unicloud jobs`, and `unicloud camera`.
  - Global binary wrapper installed in `~/.local/bin/unicloud`.
- **FastMCP 2.0 Server & AI Agent Skills:**
  - Expanded MCP tools: `cloud_list_remotes`, `cloud_browse`, `cloud_transfer_files`, `cloud_job_start`, `cloud_job_status`, `cloud_job_pause`, `cloud_job_resume`, `cloud_job_cancel`.
  - Registered official `cloud-manager` skill in AI Skills Hub and updated the Skills Reference Guide.
- **100% Backwards Compatibility:**
  - Retained all legacy GoPro endpoints and scripts (`gopro2cloud`, `cloudsync`).
  - Re-exported all existing python package symbols from `unicloud.core`.

---

## [0.2.0] - 2026-10-12

### 🚀 Major Feature: Direct Cloud-to-Cloud Sync (`CloudSync`)
- **Direct Cloud-to-Cloud Transfers:** Transfer single files or synchronize entire folder trees directly between any cloud storage providers (OneDrive, Google Drive, Dropbox, AWS S3, Cloudflare R2) with **0 MB local disk footprint**. Data streams in-memory directly across provider APIs.
- **Standalone `cloudsync` CLI:** Introduced a dedicated `cloudsync` binary entry point:
  ```bash
  cloudsync onedrive:Photos/clip.mp4 gdrive:GoPro/
  cloudsync onedrive:Brazil_Travel_2026 gdrive:GoPro/Brazil_Travel_2026 --sync
  ```
- **CLI Aliases:** Added `cloudsync` and `cloudcopy` aliases to the main `gopro2cloud` CLI (`gopro2cloud cloudsync`, `gopro2cloud cloudcopy`).
- **Dry-Run Preview:** Added `--dry-run` simulation to inspect transfer manifests before touching remote files.
- **FastMCP & AI Agent Skill:** Added native `cloud_copy` and `cloud_sync` tools to the FastMCP server and shipped a dedicated `skills/cloud-sync` skill playbook for autonomous agent execution.

### ⚡ Resilience & Reliability Engine
- **Proxy-Resilient 16MB Chunks:** Replaced large 128MB chunks with standardized 16MB buffers, preventing proxy socket stalls and API timeouts on multi-gigabyte files.
- **Dead TCP Socket Watchdog:** Enforced `--timeout 30s`, `--contimeout 15s`, and retry loops (`--retries 5`, `--low-level-retries 10`) to automatically abort dropped sockets and self-recover.
- **Host Storage Deadlock Guard:** Added `cleanup_staging_dir` to automatically sweep orphaned partial files from interrupted runs before checks, guaranteeing travel laptops with low free SSD space (< 4 GB) never deadlock.
- **Local Proxy SSL Bypass:** Defaulted `RCLONE_NO_CHECK_CERTIFICATE=true` and `--no-check-certificate` to eliminate TLS handshake errors in MITM/local proxy environments.
- **Package Exports:** Exported `cloud_transfer` directly from the package root (`from gopro2cloud import cloud_transfer`).

### 🧪 Testing
- Added regression test suite in `test_core.py` covering cloud-to-cloud command construction, date unification, staging directory clearance, and offline camera handling.

---

## [0.1.0] - 2026-10-06

### ✨ Initial Release: Zero-Disk GoPro Cloud Streaming
- **High-Speed USB Streaming:** Discovers connected GoPro cameras (HERO 9–13) over USB-C network interfaces and streams 4K/5.3K video directly to cloud storage at ~35–40 MB/s.
- **Multi-Cloud Support:** Compatible with Google Drive, Dropbox, OneDrive, AWS S3, Cloudflare R2, and Backblaze B2 via `rclone`.
- **Intelligent Chapter & Date Organization:** Organizes footage into `YYYY-MM-DD/` directories and keeps multi-chapter recordings (`GX01`, `GX02`) unified under Chapter 1's date.
- **Automatic Deduplication:** Automatically skips existing cloud files with matching name and size.
- **AI Agent Integration:** Built-in FastMCP server and `gopro-cloud-sync` agent skill.
- **Card Safety Guard:** Read-only ingestion pipeline that never deletes or alters SD card media without explicit user confirmation.
