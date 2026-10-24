"""
unicloud.web - Lightweight, dependency-free local web dashboard for UniCloud.
Provides interactive visual monitoring, job controls (pause/resume), dual-pane transfer, and GoPro status.
"""

import os
import sys
import json
import time
import urllib.parse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from unicloud.storage import parse_uri
from unicloud.core import list_remotes, discover_camera, list_camera_media, get_free_disk_gb, CameraNotFoundError
from unicloud.jobs import start_job, get_job_status, list_jobs, pause_job, resume_job, cancel_job

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UniCloud Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @keyframes pulse-slow { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }
    .animate-pulse-slow { animation: pulse-slow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans antialiased">
  <!-- Top Navigation -->
  <header class="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-sky-400 flex items-center justify-center font-black text-white shadow-lg shadow-indigo-500/25">
          ☁️
        </div>
        <div>
          <span class="font-bold text-lg tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">UniCloud</span>
          <span class="text-xs text-indigo-400 font-mono ml-2 px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20">v0.3.0</span>
        </div>
      </div>
      <div class="flex items-center gap-4 text-sm">
        <div id="cameraPill" class="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-400">
          <span class="w-2 h-2 rounded-full bg-slate-500"></span>
          <span>Probing GoPro...</span>
        </div>
        <button onclick="refreshData()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 transition flex items-center gap-1.5 text-xs font-medium">
          🔄 Refresh
        </button>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-6 py-8 space-y-8">
    <!-- Remotes & Host Overview Cards -->
    <section class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div class="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 backdrop-blur">
        <div class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Local Host Storage</div>
        <div id="localDiskGauge" class="text-2xl font-bold text-white mb-2">Calculating...</div>
        <div class="text-xs text-slate-500">Zero temporary disk used for streaming</div>
      </div>

      <div class="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 backdrop-blur md:col-span-2">
        <div class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Connected Cloud Remotes</div>
        <div id="remotesContainer" class="flex flex-wrap gap-2">
          <span class="text-slate-500 text-sm">Loading remotes...</span>
        </div>
      </div>
    </section>

    <!-- Quick Transfer Launcher -->
    <section class="p-6 rounded-2xl bg-gradient-to-b from-slate-900/80 to-slate-900/40 border border-slate-800 shadow-xl">
      <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
        <span>⚡ Launch Universal Transfer</span>
        <span class="text-xs font-normal text-slate-400">(Local ↔ Cloud or Cloud ↔ Cloud)</span>
      </h2>
      <form id="transferForm" onsubmit="handleStartJob(event)" class="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
        <div class="md:col-span-5 space-y-1">
          <label class="text-xs font-medium text-slate-300">Source URI</label>
          <input type="text" id="srcInput" required placeholder="/Volumes/Backup or onedrive:Photos" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm focus:outline-none focus:border-indigo-500 transition font-mono placeholder:text-slate-600">
        </div>
        <div class="md:col-span-5 space-y-1">
          <label class="text-xs font-medium text-slate-300">Destination URI</label>
          <input type="text" id="destInput" required placeholder="gdrive:Backup_2026 or ~/Downloads/" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm focus:outline-none focus:border-indigo-500 transition font-mono placeholder:text-slate-600">
        </div>
        <div class="md:col-span-2 flex gap-2">
          <button type="submit" class="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-1.5">
            <span>Start</span> 🚀
          </button>
        </div>
      </form>
    </section>

    <!-- Active & Historical Transfers Table -->
    <section class="space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-bold text-white">Active Background Transfers & Queue</h2>
          <p class="text-xs text-slate-400">Resilient task supervisor with pause, resume, and real-time telemetry</p>
        </div>
      </div>

      <div class="rounded-2xl border border-slate-800 bg-slate-900/30 overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm text-slate-300">
            <thead class="bg-slate-900/80 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800 font-mono">
              <tr>
                <th class="px-6 py-4">Job ID</th>
                <th class="px-6 py-4">Status</th>
                <th class="px-6 py-4">Transfer Route</th>
                <th class="px-6 py-4">Progress & Speed</th>
                <th class="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody id="jobsTableBody" class="divide-y divide-slate-800/60 font-mono text-xs">
              <tr>
                <td colspan="5" class="px-6 py-8 text-center text-slate-500">Loading jobs...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </main>

  <script>
    async function fetchAPI(endpoint, method = 'GET', data = null) {
      try {
        const opt = { method, headers: { 'Content-Type': 'application/json' } };
        if (data) opt.body = JSON.stringify(data);
        const res = await fetch(endpoint, opt);
        return await res.json();
      } catch (e) {
        console.error("API error:", e);
        return null;
      }
    }

    async function refreshData() {
      // 1. Fetch remotes & storage
      const remotesData = await fetchAPI('/api/remotes');
      if (remotesData) {
        const rc = document.getElementById('remotesContainer');
        rc.innerHTML = '';
        if (remotesData.remotes && remotesData.remotes.length) {
          remotesData.remotes.forEach(r => {
            const el = document.createElement('div');
            el.className = 'px-3 py-1.5 rounded-xl bg-slate-800/70 border border-slate-700/60 text-slate-200 text-xs flex items-center gap-1.5 font-mono';
            el.innerHTML = `<span>☁️</span> <strong>${r}</strong>`;
            rc.appendChild(el);
          });
        } else {
          rc.innerHTML = '<span class="text-slate-500 text-xs">No remotes. Run "unicloud config"</span>';
        }
        document.getElementById('localDiskGauge').innerText = `${remotesData.free_disk_gb.toFixed(1)} GB Free`;
      }

      // 2. Fetch Camera Status
      const camData = await fetchAPI('/api/camera');
      const cp = document.getElementById('cameraPill');
      if (camData && camData.connected) {
        cp.className = 'flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400';
        cp.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-slow"></span><span>GoPro Connected (${camData.media_count} clips, ${camData.total_gb} GB)</span>`;
      } else {
        cp.className = 'flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-400';
        cp.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-600"></span><span>No GoPro connected over USB</span>`;
      }

      // 3. Fetch Jobs
      const jobsData = await fetchAPI('/api/jobs');
      const tb = document.getElementById('jobsTableBody');
      if (jobsData && jobsData.jobs) {
        if (!jobsData.jobs.length) {
          tb.innerHTML = '<tr><td colspan="5" class="px-6 py-8 text-center text-slate-500 font-sans">No active or historical transfers. Start one above!</td></tr>';
        } else {
          tb.innerHTML = '';
          jobsData.jobs.forEach(j => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-800/30 transition';

            let badge = '';
            if (j.status === 'running') badge = '<span class="px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20">▶ RUNNING</span>';
            else if (j.status === 'paused') badge = '<span class="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">⏸ PAUSED</span>';
            else if (j.status === 'completed') badge = '<span class="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">✓ DONE</span>';
            else if (j.status === 'failed') badge = '<span class="px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">✗ FAILED</span>';
            else badge = `<span class="px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">${j.status.toUpperCase()}</span>`;

            let actions = '';
            if (j.status === 'running') {
              actions = `<button onclick="handlePause('${j.id}')" class="px-2 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 mr-2 border border-amber-500/20">Pause</button>` +
                        `<button onclick="handleCancel('${j.id}')" class="px-2 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/20">Cancel</button>`;
            } else if (j.status === 'paused' || j.status === 'failed') {
              actions = `<button onclick="handleResume('${j.id}')" class="px-2 py-1 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 mr-2 border border-emerald-500/20">Resume</button>` +
                        `<button onclick="handleCancel('${j.id}')" class="px-2 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/20">Cancel</button>`;
            } else {
              actions = '<span class="text-slate-600">-</span>';
            }

            const pct = j.percentage || 0;
            tr.innerHTML = `
              <td class="px-6 py-4 font-bold text-white">${j.id}</td>
              <td class="px-6 py-4">${badge}</td>
              <td class="px-6 py-4 truncate max-w-xs font-sans text-xs">
                <span class="text-slate-300">${j.src}</span><br>
                <span class="text-indigo-400">↳ ${j.dest}</span>
              </td>
              <td class="px-6 py-4 font-sans">
                <div class="flex items-center gap-2 mb-1">
                  <div class="w-24 bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div class="bg-indigo-500 h-2 rounded-full" style="width: ${pct}%"></div>
                  </div>
                  <span class="text-xs text-slate-300 font-mono">${pct.toFixed(1)}%</span>
                </div>
                <div class="text-[11px] text-slate-500 font-mono">${j.speed} • ETA ${j.eta}</div>
              </td>
              <td class="px-6 py-4 text-right font-sans">${actions}</td>
            `;
            tb.appendChild(tr);
          });
        }
      }
    }

    async function handleStartJob(e) {
      e.preventDefault();
      const src = document.getElementById('srcInput').value.trim();
      const dest = document.getElementById('destInput').value.trim();
      if (!src || !dest) return;
      await fetchAPI('/api/jobs/start', 'POST', { src, dest, mode: 'copy' });
      document.getElementById('srcInput').value = '';
      document.getElementById('destInput').value = '';
      refreshData();
    }

    async function handlePause(jobId) {
      await fetchAPI('/api/jobs/pause', 'POST', { job_id: jobId });
      refreshData();
    }

    async function handleResume(jobId) {
      await fetchAPI('/api/jobs/resume', 'POST', { job_id: jobId });
      refreshData();
    }

    async function handleCancel(jobId) {
      if (!confirm(`Cancel job ${jobId}?`)) return;
      await fetchAPI('/api/jobs/cancel', 'POST', { job_id: jobId });
      refreshData();
    }

    // Auto-refresh every 3 seconds
    refreshData();
    setInterval(refreshData, 3000);
  </script>
</body>
</html>
"""


class UniCloudWebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
            return

        if path == "/api/remotes":
            remotes = list_remotes()
            free_disk = get_free_disk_gb()
            self._send_json({"remotes": remotes, "free_disk_gb": free_disk})
            return

        if path == "/api/jobs":
            jobs = list_jobs()
            self._send_json({"jobs": [j.to_dict() for j in jobs]})
            return

        if path == "/api/camera":
            try:
                cam = discover_camera()
                media = list_camera_media(cam)
                total_bytes = sum(f["size"] for f in media)
                self._send_json({
                    "connected": True,
                    "ip": cam["ip"],
                    "media_count": len(media),
                    "total_gb": round(total_bytes / (1024 ** 3), 2),
                })
            except Exception:
                self._send_json({"connected": False})
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if path == "/api/jobs/start":
            src = data.get("src", "")
            dest = data.get("dest", "")
            mode = data.get("mode", "copy")
            if not src or not dest:
                self._send_json({"success": False, "error": "Missing src or dest"}, status=400)
                return
            job = start_job(src=src, dest=dest, mode=mode)
            self._send_json({"success": True, "job_id": job.id})
            return

        if path == "/api/jobs/pause":
            job_id = data.get("job_id", "")
            success = pause_job(job_id)
            self._send_json({"success": success, "job_id": job_id})
            return

        if path == "/api/jobs/resume":
            job_id = data.get("job_id", "")
            success = resume_job(job_id)
            self._send_json({"success": success, "job_id": job_id})
            return

        if path == "/api/jobs/cancel":
            job_id = data.get("job_id", "")
            success = cancel_job(job_id)
            self._send_json({"success": success, "job_id": job_id})
            return

        self.send_error(404, "Not Found")

    def _send_json(self, data: dict, status: int = 200):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        # Silence default terminal request spam
        pass


def run_web_server(port: int = 8080, host: str = "127.0.0.1", open_browser: bool = False):
    """Run the local UniCloud dashboard server."""
    server_address = (host, port)
    try:
        httpd = HTTPServer(server_address, UniCloudWebHandler)
    except OSError:
        # Fallback to alternate port if 8080 is in use
        port = 8081
        server_address = (host, port)
        httpd = HTTPServer(server_address, UniCloudWebHandler)

    url = f"http://{host}:{port}"
    print("=" * 65)
    print("           UniCloud: Visual Web Dashboard Running")
    print("=" * 65)
    print(f"  • Open URL: {url}")
    print("  • Press Ctrl+C in your terminal to stop.")
    print("=" * 65)

    if open_browser:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
        httpd.server_close()
