"""data/raw/manifest.csv: URL, fecha de descarga y sha256 de cada documento descargado."""

import csv
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

FIELDS = ["file", "url", "retrieved_at", "sha256", "bytes", "content_type"]


class ManifestError(RuntimeError):
    """Un documento falta, no está registrado o no coincide con su sha256."""


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(manifest_path: Path) -> dict[str, dict]:
    if not manifest_path.exists():
        return {}
    with manifest_path.open(newline="", encoding="utf-8") as f:
        return {row["file"]: row for row in csv.DictReader(f)}


def upsert(manifest_path: Path, entries: list[ManifestEntry]) -> None:
    """Añade las entradas al manifiesto. Una entrada del mismo archivo sustituye a la anterior."""
    rows = read(manifest_path)
    for entry in entries:
        rows[entry.file] = asdict(entry)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[file] for file in sorted(rows))


def verify(raw_dir: Path, file: str, manifest_path: Path) -> dict:
    """Comprueba que el archivo existe, está en el manifiesto y conserva su sha256."""
    path = raw_dir / file
    if not path.exists():
        raise ManifestError(f"falta data/raw/{file}")
    entry = read(manifest_path).get(file)
    if entry is None:
        raise ManifestError(f"data/raw/{file} no está registrado en el manifiesto")
    actual = sha256_file(path)
    if actual != entry["sha256"]:
        raise ManifestError(
            f"data/raw/{file} ha cambiado: su sha256 es {actual} y el manifiesto dice "
            f"{entry['sha256']}"
        )
    return entry
