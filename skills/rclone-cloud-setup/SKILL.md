---
name: rclone-cloud-setup
description: Assistant for configuring rclone cloud storage remotes (Google Drive, Dropbox, OneDrive, AWS S3, Cloudflare R2) with safe OAuth browser authorization. Triggers on "setup cloud storage", "configure rclone", "connect Google Drive".
---

# Cloud Storage Onboarding Assistant (`rclone-cloud-setup`)

Use this skill when a user needs to connect a new cloud storage destination for `gopro2cloud` or check existing rclone connections.

## Security Mandate
- **NEVER print or echo authorization tokens, secret keys, or passwords** in chat messages or terminal logs.
- Mask all sensitive values (e.g. `client_id`, `client_secret`, access tokens).

---

## 1. Checking Existing Connections
To view currently configured cloud remotes:
```bash
rclone listremotes
```
To test connectivity and available quota for a remote:
```bash
rclone about <remote>:
```

---

## 2. Onboarding New Cloud Providers

### A. Google Drive (`gdrive`)
1. Run `rclone config` interactively.
2. Choose `n` (New remote), name it `gdrive`, type `drive`.
3. Provide your Google Cloud OAuth Client ID and Secret (or press enter for default).
4. Select Scope `1` (Full access).
5. For web browser authorization, approve in the pop-up browser tab.
6. Verify access with: `rclone about gdrive:`

### B. Dropbox (`dropbox`)
1. Run `rclone config`, name it `dropbox`, select `dropbox`.
2. Authorize via browser popup when prompted.
3. Test with: `rclone about dropbox:`

### C. AWS S3 / Cloudflare R2 / Backblaze B2
1. Name it `s3` (or `r2`), type `s3`.
2. Select provider (e.g. `AWS`, `Cloudflare`, `Backblaze`).
3. Enter Access Key ID and Secret Access Key.
4. Set region and endpoint URL if using R2 / MinIO.
5. Test with: `rclone lsd <remote>:`

---

## 3. Verifying Integration with `gopro2cloud`
Once a remote is configured, test that `gopro2cloud` recognizes it:
```bash
python3 -m gopro2cloud.cli status --dest <remote>:GoPro
```
