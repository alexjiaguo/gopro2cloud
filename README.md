<div align="center">

# 📷 gopro2cloud

### The Free, Zero-Disk, Open-Source Alternative to GoPro Cloud Subscription.

Stream and sync 100+ GB of 4K/5.3K footage from your GoPro **directly** to Google Drive, Dropbox, OneDrive, or AWS S3 over high-speed USB — with **zero laptop disk space** and **no monthly fees**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](pyproject.toml)
[![Storage: 0 MB Local](https://img.shields.io/badge/Local%20Disk-0%20MB%20Footprint-success.svg)]()
[![Free Alternative](https://img.shields.io/badge/GoPro%20Subscription-$0%2Fyear-orange.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Features](#-why-gopro2cloud) • [Comparison](#-gopro2cloud-vs-gopro-subscription) • [Quick Start](#-quick-start) • [CLI Usage](#-cli-usage) • [AI Agent & MCP](#-ai-agent--mcp-server) • [Contributing](#-contributing)

</div>

---

## 💡 Why gopro2cloud?

If you own a GoPro, you already know the frustration:
- **GoPro Subscription costs \$49.99 – \$99.99/year**, just to back up footage you already have other cloud storage for (Google One, Microsoft 365, Dropbox, or AWS S3).
- **Camera Wi-Fi Auto-Upload is painfully slow**, drains your battery, and notoriously causes the camera to overheat while uploading 4K/5.3K video.
- **Plugging into your Mac/PC to transfer files manually is broken:** macOS Image Capture and MTP drivers frequently freeze or corrupt on single files larger than 4 GB.
- **Laptop SSDs run out of space:** Offloading a 128 GB or 256 GB microSD card onto a modern MacBook with only 30 GB of free SSD space is physically impossible without tedious manual chunking.

**`gopro2cloud` solves all of this.**

When you connect a modern GoPro (HERO 9, 10, 11, 12, 13) via USB-C, it automatically runs an internal high-speed HTTP server over a virtual network interface. `gopro2cloud` discovers this socket, queries the media catalogue, and **streams your master video files directly into your cloud storage at 35–40 MB/s without writing a single byte to your laptop hard drive.**

---

## 🥊 gopro2cloud vs. GoPro Paid Subscription

| Feature | GoPro Paid Cloud Subscription | Native Desktop / Quik App | **gopro2cloud (This Tool)** |
| :--- | :---: | :---: | :---: |
| **Annual Cost** | **\$49.99 – \$99.99 / year** 💸 | Free (Requires Desktop) | **$0 Forever (Free & Open Source)** 🚀 |
| **Cloud Destination** | GoPro Cloud only (Vendor Lock-in) | Local Disk Only | **Any Cloud** (Google Drive, Dropbox, OneDrive, S3, R2, B2) |
| **Local Disk Required** | High (downloads cached copies) | Full card size required (100+ GB) | **0 MB (Pure In-Memory Stream)** ⚡ |
| **Transfer Speed** | Slow (Wi-Fi ~5–10 MB/s) | Medium (USB MTP crashes on >4GB) | **Fast (USB HTTP ~35–40 MB/s)** 🏎️ |
| **Camera Overheating** | High (Wi-Fi upload gets very hot) | Low | **Low (Powered & cool over USB)** |
| **Data Privacy & Ownership** | Stored on GoPro servers | Local | **100% Private (Direct to YOUR cloud)** |
| **Smart Date Categorization** | Cloud timeline | Flat DCIM folder mess | **Automated `YYYY-MM-DD/` Folders** 📁 |
| **Multi-Chapter Handling** | Sometimes split in UI | Scattered `GX01`, `GX02` files | **Chapters unified under Chapter 1 Date** |
| **Deduplication** | Automatic | None (overwrites or duplicates) | **Automatic (Skips existing cloud files)** |
| **AI Agent / CLI Scriptable** | ❌ No | ❌ No | **✅ Yes (CLI + FastMCP Server + Skills)** |

---

## ✨ Key Features

- **🚀 Direct In-Memory Streaming:** Uses `rclone copyurl` to pipe video bytes straight from the camera socket into your cloud bucket. No local scratch files, no SSD wear.
- **📁 Smart Date & Chapter Organization:** Automatically sorts recordings into `<remote>/YYYY-MM-DD/` directories. Long 4K recordings split across multiple chapters (`GX010475.MP4`, `GX020475.MP4`) are kept together under Chapter 1's date.
- **🔁 Intelligent Deduplication:** Checks destination folders before transferring. If a video already exists in your cloud with matching name and size, it is automatically skipped.
- **🛡️ 100% Card Safety:** `gopro2cloud` never deletes or modifies media on your microSD card unless you explicitly request a post-sync purge.
- **🤖 Built for the AI Era (FastMCP):** Ships with a native Model Context Protocol (MCP) server and Agent Skills. You can plug in your GoPro and simply say: *"Hey, back up my GoPro to Google Drive"*.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python:** 3.11 or newer
- **rclone:** The universal cloud transfer utility (free & open source)
  ```bash
  # macOS
  brew install rclone

  # Linux
  sudo apt install rclone   # or curl https://rclone.org/install.sh | sudo bash

  # Windows
  winget install Rclone.Rclone
  ```

### 2. Configure Your Cloud (1 Minute)
Connect your favorite cloud provider to `rclone` (Google Drive, Dropbox, OneDrive, S3):
```bash
rclone config
```
*(Just name your remote, e.g. `gdrive`, choose your provider, and approve in the browser popup).*

### 3. Install gopro2cloud
```bash
git clone https://github.com/alexjiaguo/gopro2cloud.git
cd gopro2cloud
pip install -e .
```

---

## 💻 CLI Usage

Plug your GoPro into your computer using a USB-C cable and turn it ON.

### 1. Check Status
Verify your camera link, local disk space, and cloud connections:
```bash
gopro2cloud status
```
```text
============================================================
      gopro2cloud: Camera & Cloud Status Check
============================================================
1. Probing GoPro over USB...
   [✓] Connected to GoPro at 172.28.158.51:80
       Found 24 video files (104.78 GB total)

2. Local host storage: 58.12 GB free

3. Cloud remote index: 'gdrive:GoPro'
   [✓] Found 8 existing files already backed up in 'gdrive:GoPro'
============================================================
```

### 2. View Categorized Media
Inspect all videos grouped by their real recording date:
```bash
gopro2cloud list
```
```text
Found 24 files (104.78 GB total) across 3 recording dates:

📁 2026-09-27/ (3 files, 4.85 GB)
   • GX010467.MP4      46.4 MB  -> 2026-09-27/GX010467.MP4
   • GX010468.MP4      4.05 GB  -> 2026-09-27/GX010468.MP4
📁 2026-09-28/ (18 files, 77.25 GB)
   • GX010475.MP4     11.06 GB  -> 2026-09-28/GX010475.MP4
   • GX020475.MP4      8.94 GB  -> 2026-09-28/GX020475.MP4  [Chapter 2 kept together]
```

### 3. Start Streaming Sync
Stream everything directly to your cloud destination:
```bash
# Direct zero-disk streaming into Google Drive
gopro2cloud sync --dest gdrive:GoPro

# Dry-run to preview what will be skipped and uploaded
gopro2cloud sync --dest gdrive:GoPro --dry-run

# Upload to Dropbox or AWS S3 instead
gopro2cloud sync --dest dropbox:GoPro_Backups
gopro2cloud sync --dest s3:my-video-bucket/gopro
```

---

## 🤖 AI Agent & MCP Server

`gopro2cloud` includes a native **FastMCP Server** that exposes camera discovery and transfer tools directly to AI coding assistants like **Antigravity, Claude Desktop, Cursor, and Windsurf**.

Add this to your MCP configuration (`claude_desktop_config.json` or `mcp_config.json`):

```json
{
  "mcpServers": {
    "gopro2cloud": {
      "command": "python3",
      "args": ["-m", "gopro2cloud.mcp_server"]
    }
  }
}
```

Now you can control your camera conversationally:
> *"Hey, what videos are on my GoPro?"*  
> *"Check if my GoPro is connected and sync the newest clips to Google Drive."*

---

## 🗺️ Roadmap

- [x] Zero-disk direct HTTP streaming (`rclone copyurl`)
- [x] Intelligent recording date & chapter grouping
- [x] Recursive deduplication (skips existing files)
- [x] Multi-cloud support (Google Drive, Dropbox, OneDrive, S3/R2/B2)
- [x] Standalone CLI + Self-contained integration test suite
- [x] FastMCP Server & AI Agent Skills
- [ ] Wireless offload over local Wi-Fi station mode
- [ ] Lightweight background menu bar tray icon (macOS / Windows)
- [ ] Automatic camera card cleanup option (with strict safety verification)

---

## 🌟 Support & Contributing

If this project saved you \$50/year on GoPro subscriptions or saved your laptop hard drive from filling up:

- ⭐ **Star this repository** on GitHub!
- 🍴 **Fork it** to add support for custom cloud scripts, hooks, or notifications.
- 🐛 **Report issues** or submit Pull Requests — contributions are warmly welcome!

---

## 📄 License

Distributed under the [MIT License](LICENSE). Open source and free for everyone.
