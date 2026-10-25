<div align="center">

# ☁️ UniCloud

### The Universal Multi-Cloud Transfer Platform & Local-to-Cloud Orchestrator.

Transfer, synchronize, and back up files across **Local Storage**, **40+ Cloud Providers** (Google Drive, OneDrive, Dropbox, AWS S3, Cloudflare R2), and **USB Streaming Devices** (GoPro HERO 9–13) — with **zero local disk footprint**, **persistent background supervision**, **interactive web dashboard**, and **AI Agent MCP tools**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)]()
[![Local Disk: 0 MB](https://img.shields.io/badge/Local%20Disk-0%20MB%20Footprint-success.svg)]()
[![Free & Open Source](https://img.shields.io/badge/License-Open%20Source-orange.svg)]()

[Architecture](#-architecture) • [Features](#-key-features) • [Quick Start](#-quick-start) • [CLI Reference](#-cli-reference) • [Task Supervisor](#-background-task-manager) • [Web Dashboard](#-visual-web-dashboard) • [AI Agent MCP](#-ai-agent--mcp-server) • [GoPro Streamer](#-gopro-zero-disk-streaming)

</div>

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User & Agent Control Layer                      │
│                                                                        │
│   [ Unified CLI ]          [ FastMCP 2.0 Server ]       [ Web Dashboard]│
│   (cp, sync, ls, jobs)     (Antigravity/Cursor/Claude)  (Local GUI)    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     UniCloud Orchestration Core                        │
│                                                                        │
│  ┌───────────────────────┐  ┌──────────────────────┐  ┌──────────────┐  │
│  │ Unified StorageURI    │  │ Persistent Job Queue │  │ Deduplication│  │
│  │ (local/remote/stream) │  │ (Atomic JSON / State)│  │ & Checksums  │  │
│  └───────────────────────┘  └──────────────────────┘  └──────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Engine & Connector Matrix                       │
│                                                                        │
│  ┌───────────────────────────────┐   ┌───────────────────────────────┐ │
│  │    Universal Cloud Engine     │   │     Specialized Connectors    │ │
│  │  (Rclone Multi-Cloud Mesh)    │   │  (OpenGoPro USB Socket Stream)│ │
│  │  • Google Drive   • Dropbox   │   │  • GoPro HERO 9-13 USB/Wi-Fi  │ │
│  │  • OneDrive       • AWS S3    │   │  • Auto-chapter date grouping │ │
│  │  • Cloudflare R2  • WebDAV/OSS│   │  • Zero-disk pipe (`copyurl`) │ │
│  └───────────────────────────────┘   └───────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

- **🌐 Universal Transfer Matrix (`StorageURI`)**: Transfer files between any combination of Local directories (`/Volumes/Backup`), Cloud Remotes (`gdrive:`, `onedrive:`, `s3:`), and live HTTP streams.
- **☁️ Zero-Disk Cloud-to-Cloud**: Pipe data straight from one cloud to another without staging or downloading a single byte to your laptop hard drive.
- **⚙️ Persistent Background Task Supervisor**: Launch asynchronous background backups that survive terminal disconnection. Pause, resume, and track live speed (MB/s), ETA, and percentage progress.
- **📊 Visual Web Dashboard (`unicloud web`)**: Lightweight local GUI with connected cloud storage gauges, live progress tables, and quick-transfer dialogs.
- **📷 Battle-Tested GoPro Zero-Disk Streamer**: Retains full GoPro HERO 9-13 USB offloading with automatic recording date sorting, multi-chapter grouping, and deduplication.
- **🤖 Built for AI Agents (FastMCP 2.0)**: Native Model Context Protocol server exposing remote browsing, file transfers, and task supervision to Antigravity, Claude Desktop, Cursor, and Windsurf.
- **🔄 100% Backwards Compatible**: Existing `gopro2cloud` and `cloudsync` commands and scripts remain fully functional as aliases.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python:** 3.11 or newer
- **rclone:** The universal cloud transfer utility
  ```bash
  # macOS
  brew install rclone

  # Linux
  sudo apt install rclone
  ```

### 2. Configure Your Cloud Accounts
Connect your cloud storage providers (Google Drive, OneDrive, Dropbox, S3):
```bash
rclone config
```

### 3. Install UniCloud
```bash
git clone https://github.com/alexjiaguo/unicloud.git
cd unicloud
pip install -e .
```

---

## 💻 CLI Reference

### 1. Quick File & Folder Transfer
```bash
# Upload a local file to Google Drive
unicloud cp /Volumes/Backup/presentation.pdf gdrive:Documents/

# Mirror an entire local directory into OneDrive
unicloud sync /Volumes/Backup onedrive:Backup_2026/

# Direct Cloud-to-Cloud copy (Zero Local Disk)
unicloud cp onedrive:Photos/sample.mp4 gdrive:GoPro/
unicloud sync onedrive:Vacation gdrive:Backup/Vacation

# Dry-run preview
unicloud cp /Volumes/Backup gdrive:Backup/ --dry-run
```

### 2. Cloud & Storage Exploration
```bash
# List all configured cloud providers
unicloud remotes

# Browse directory on cloud or local storage
unicloud ls gdrive:Photos
unicloud ls /Volumes/Backup -R

# Run cloud provider configuration assistant
unicloud config
```

---

## ⚙️ Background Task Manager

Replace brittle shell scripts with UniCloud's native, atomic job supervisor:

```bash
# 1. Start background backup job
unicloud jobs start /Volumes/Backup gdrive:graduate_period_files --exclude-from backup_exclude.txt

# 2. List all active and past jobs
unicloud jobs list

# 3. Check live telemetry (progress bar, speed, ETA, recent logs)
unicloud jobs status <job_id>

# 4. Pause an active transfer (SIGSTOP)
unicloud jobs pause <job_id>

# 5. Resume a paused or interrupted transfer (SIGCONT / checkpoint restart)
unicloud jobs resume <job_id>

# 6. Cancel a transfer
unicloud jobs cancel <job_id>

# 7. Tail transfer logs
unicloud jobs log <job_id> -n 50
```

---

## 🖥️ Visual Web Dashboard

Launch the local interactive GUI in your browser:

```bash
unicloud web
# Or alias:
unicloud ui
```
- **Storage Gauges:** Live capacity metrics for local disk and cloud accounts.
- **Task Supervisor Table:** Real-time transfer progress bars, MB/s speed gauges, and pause/resume buttons.
- **Quick Launcher:** Drag-and-drop or select source and destination paths to initiate transfers.

---

## 📷 GoPro Zero-Disk Streaming

All battle-tested GoPro USB HTTP streaming capabilities are preserved:

```bash
# Check camera USB link and cloud index
unicloud camera status

# List media grouped by recording date
unicloud camera list

# Stream footage directly to cloud (0 MB local disk footprint)
unicloud camera sync --dest gdrive:GoPro
unicloud camera sync --dest gdrive:GoPro --dry-run
```

*Legacy aliases (`gopro2cloud status`, `cloudsync onedrive:folder gdrive:folder`) remain 100% operational.*

---

## 🤖 AI Agent & MCP Server

UniCloud exposes full multi-cloud management to AI coding assistants via FastMCP 2.0.

Add to your MCP configuration (`claude_desktop_config.json` or `mcp_config.json`):

```json
{
  "mcpServers": {
    "unicloud": {
      "command": "python3",
      "args": ["-m", "unicloud.mcp_server"]
    }
  }
}
```

Now you can instruct your agent conversationally:
> *"Upload /Volumes/Backup to my Google Drive in the background and tell me the job ID."*  
> *"Check how fast the current backup job is uploading."*  
> *"Copy my vacation photos from OneDrive to Google Drive."*  
> *"Probe my GoPro camera and stream new clips into Google Drive."*

---

## 📄 License

MIT License. Free and open source forever.
