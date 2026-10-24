"""
unicloud.storage - StorageURI abstraction for local paths, cloud remotes, and HTTP streams.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class StorageURI:
    """Represents a unified storage endpoint (local, cloud remote, or HTTP stream)."""
    raw: str
    uri_type: str  # "local", "remote", "stream"
    remote_name: Optional[str] = None
    path: str = ""
    is_directory: bool = False

    @property
    def name(self) -> str:
        """Basename of the file or directory."""
        clean_path = self.path.rstrip("/\\")
        return os.path.basename(clean_path) if clean_path else ""

    def exists(self) -> bool:
        """Check existence for local filesystem paths."""
        if self.uri_type == "local":
            return os.path.exists(self.path)
        return False

    def formatted(self) -> str:
        """Return formatted string suitable for rclone or HTTP requests."""
        if self.uri_type == "stream":
            return self.raw
        if self.uri_type == "remote":
            return f"{self.remote_name}:{self.path}"
        return self.path

    def __str__(self) -> str:
        return self.formatted()


def parse_uri(uri: str | StorageURI) -> StorageURI:
    """
    Parse a string or StorageURI into a normalized StorageURI.

    Supported patterns:
      - HTTP streams: "http://172.28.158.51/video.mp4", "https://..."
      - Cloud remotes: "gdrive:GoPro", "onedrive:Photos/2026", "s3:my-bucket/prefix"
      - Local paths: "/Volumes/Backup", "~/Documents/file.txt", "./local_dir"
      - File URIs: "file:///Volumes/Backup"
    """
    if isinstance(uri, StorageURI):
        return uri

    raw = str(uri).strip()

    # 1. Check HTTP/HTTPS stream
    if raw.startswith("http://") or raw.startswith("https://"):
        return StorageURI(
            raw=raw,
            uri_type="stream",
            remote_name=None,
            path=raw,
            is_directory=raw.endswith("/"),
        )

    # 2. Check File URI
    if raw.startswith("file://"):
        raw = raw[7:]

    # 3. Check Windows drive letter (e.g. C:\ or D:/)
    is_windows_drive = bool(re.match(r"^[a-zA-Z]:[\\/]", raw))

    # 4. Check Cloud Remote (e.g. remote_name:path)
    if ":" in raw and not is_windows_drive:
        parts = raw.split(":", 1)
        remote_name = parts[0].strip()
        remote_path = parts[1].strip()

        # Check directory heuristic
        is_dir = remote_path.endswith("/") or remote_path.endswith("\\") or not bool(os.path.splitext(remote_path)[1])
        if remote_path == "":
            is_dir = True

        return StorageURI(
            raw=raw,
            uri_type="remote",
            remote_name=remote_name,
            path=remote_path,
            is_directory=is_dir,
        )

    # 5. Local path
    expanded = os.path.expanduser(raw)
    normalized = os.path.normpath(expanded)
    if raw.endswith("/") or raw.endswith("\\"):
        normalized += "/"

    is_dir = raw.endswith("/") or raw.endswith("\\")
    if os.path.exists(normalized) and os.path.isdir(normalized):
        is_dir = True
    elif not is_dir:
        # If no extension and not an existing file, treat as directory by default if trailing slash
        _, ext = os.path.splitext(normalized)
        if not ext and not os.path.isfile(normalized):
            is_dir = raw.endswith("/")

    return StorageURI(
        raw=raw,
        uri_type="local",
        remote_name=None,
        path=normalized,
        is_directory=is_dir,
    )


def resolve_target(src: StorageURI, dest: StorageURI) -> StorageURI:
    """
    If src is a single file and dest is a directory, resolve the target to
    dest/src.name. Otherwise, return dest as-is.
    """
    if src.is_directory:
        return dest

    # src is a file
    file_name = src.name
    if not file_name:
        return dest

    if dest.uri_type == "remote":
        if dest.is_directory or dest.path.endswith("/") or not dest.path or not os.path.splitext(dest.path)[1]:
            clean_dest = dest.path.rstrip("/")
            new_path = f"{clean_dest}/{file_name}" if clean_dest else file_name
            return StorageURI(
                raw=f"{dest.remote_name}:{new_path}",
                uri_type="remote",
                remote_name=dest.remote_name,
                path=new_path,
                is_directory=False,
            )
    elif dest.uri_type == "local":
        if dest.is_directory or os.path.isdir(dest.path) or dest.raw.endswith("/"):
            clean_dest = dest.path.rstrip("/")
            new_path = os.path.join(clean_dest, file_name)
            return StorageURI(
                raw=new_path,
                uri_type="local",
                remote_name=None,
                path=new_path,
                is_directory=False,
            )

    return dest
