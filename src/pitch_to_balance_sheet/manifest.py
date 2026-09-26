"""data/raw/manifest.csv: URL, fecha de descarga y sha256 de cada documento descargado."""

import csv
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

FIELDS = ["file", "url", "retrieved_at", "sha256", "bytes", "content_type"]


@dataclass(frozen=True)
class ManifestEntry:
    file: str  # ruta relativa a data/raw/
    url: str
    retrieved_at: str  # ISO 8601 en UTC
    sha256: str
    bytes: int
    content_type: str


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def upsert(manifest_path: Path, entries: list[ManifestEntry]) -> None:
    """Añade las entradas al manifiesto. Una entrada del mismo archivo sustituye a la anterior."""
    rows: dict[str, dict] = {}
    if manifest_path.exists():
        with manifest_path.open(newline="", encoding="utf-8") as f:
            rows = {row["file"]: row for row in csv.DictReader(f)}
    for entry in entries:
        rows[entry.file] = asdict(entry)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[file] for file in sorted(rows))
