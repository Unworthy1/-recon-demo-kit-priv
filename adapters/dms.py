"""Document-management adapters (INTAKE §D).

Reference: PaperlessDMS (the bundled demo DMS), FilesystemDMS.
Stubs: LaserficheDMS, SharePointDMS — implement per your INTAKE.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import urllib.request

from .base import DMSAdapter, StoredDocument, register


@register("dms", "paperless")
class PaperlessDMS(DMSAdapter):
    """READY. Paperless-ngx — the bundled demo DMS. post_document is async: it returns a task
    UUID; poll /api/tasks/ for the resulting document id. Deep link is /documents/{id}/details."""
    name = "dms:paperless"

    def __init__(self, base_url: str, token: str, public_url: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.public_url = (public_url or base_url).rstrip("/")

    def _req(self, path, data=None, method="GET"):
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, method=method)
        req.add_header("Authorization", f"Token {self.token}")
        return urllib.request.urlopen(req, timeout=30)

    def ingest(self, content: bytes, filename: str, metadata: dict) -> StoredDocument:
        # IMPLEMENT (per your system): multipart POST to /api/documents/post_document/, then poll
        # /api/tasks/?task_id=<uuid> until related_document is set. Reference flow only.
        raise NotImplementedError("Wire PaperlessDMS.ingest (multipart post + task poll).")

    def url_for(self, doc_id: str) -> str:
        return f"{self.public_url}/documents/{doc_id}/details"


@register("dms", "filesystem")
class FilesystemDMS(DMSAdapter):
    """READY. No DMS — store documents on a share and link by file path/URL (INTAKE §D filesystem)."""
    name = "dms:filesystem"

    def __init__(self, root: str, url_base: str = ""):
        self.root, self.url_base = Path(root), url_base.rstrip("/")

    def ingest(self, content: bytes, filename: str, metadata: dict) -> StoredDocument:
        self.root.mkdir(parents=True, exist_ok=True)
        dest = self.root / filename
        dest.write_bytes(content)
        return StoredDocument(doc_id=filename, title=filename, url=self.url_for(filename))

    def url_for(self, doc_id: str) -> str:
        return f"{self.url_base}/{doc_id}" if self.url_base else str(self.root / doc_id)


@register("dms", "laserfiche")
class LaserficheDMS(DMSAdapter):
    """STUB — Laserfiche repository API (INTAKE §D). Implement ingest() via the Laserfiche
    Repository API (import + set metadata fields), and url_for() as the WebLink/WebClient
    doc URL pattern from your INTAKE. OAuth service-app auth from the secret store."""
    name = "dms:laserfiche"

    def __init__(self, base_url: str, repo_id: str, auth: dict, url_pattern: str):
        self.base_url, self.repo_id, self.auth, self.url_pattern = base_url, repo_id, auth, url_pattern

    def ingest(self, content: bytes, filename: str, metadata: dict) -> StoredDocument:
        raise NotImplementedError("Implement LaserficheDMS.ingest via the Repository API.")

    def url_for(self, doc_id: str) -> str:
        return self.url_pattern.format(id=doc_id)


@register("dms", "sharepoint")
class SharePointDMS(DMSAdapter):
    """STUB — SharePoint/OneDrive via Microsoft Graph (INTAKE §D). Implement ingest() as a
    Graph drive upload + column metadata; url_for() returns the webUrl. App-reg auth."""
    name = "dms:sharepoint"

    def __init__(self, site_id: str, drive_id: str, auth: dict):
        self.site_id, self.drive_id, self.auth = site_id, drive_id, auth

    def ingest(self, content: bytes, filename: str, metadata: dict) -> StoredDocument:
        raise NotImplementedError("Implement SharePointDMS.ingest via Microsoft Graph.")

    def url_for(self, doc_id: str) -> str:
        raise NotImplementedError("Return the Graph webUrl for the item.")
