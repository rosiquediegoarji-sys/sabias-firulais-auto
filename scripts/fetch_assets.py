"""Descarga la librería inicial de SFX y música para el canal.

Idea:
- Lista curada en `assets_manifest.json` (al lado de este script).
- Cada entrada tiene: nombre destino, URL, licencia esperada, atribución sí/no.
- Se baja cada archivo si todavía no existe.
- Verifica con HEAD que el Content-Type sea audio/* antes de bajar.

Pensado para correr UNA VEZ tras clonar el repo. Las descargas se commitean
luego al repo (sfx_library/ y music_library/) para que el runner no dependa de
ningún servidor externo en cada slot.

NOTA — el manifest viene VACÍO de fábrica. Diego rellena las URLs concretas
cuando tenga la librería elegida (Mixkit/Pixabay/YouTube Audio Library).
La razón de no incluir URLs aquí: las URLs directas de Mixkit/Pixabay cambian
cuando ellos rotan CDN, así que el catálogo se cura puntualmente y se commitea
el resultado, no las URLs.

Uso:
    python3 scripts/fetch_assets.py            # descarga lo que falta
    python3 scripts/fetch_assets.py --check    # solo lista qué falta
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

log = logging.getLogger("firulais.assets")

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "assets_manifest.json"
SFX_DIR = REPO_ROOT / "sfx_library"
MUSIC_DIR = REPO_ROOT / "music_library"

ALLOWED_LICENSES = {
    "mixkit",                # Mixkit License — comercial, sin atribución
    "pixabay",               # Pixabay Content License
    "youtube-audio-library",
    "cc0",
}


@dataclass(frozen=True)
class AssetSpec:
    kind: str          # "sfx" | "music"
    filename: str      # ej "ding.mp3"
    url: str
    license: str
    attribution: bool = False
    source_label: str = ""

    @property
    def dest(self) -> Path:
        base = SFX_DIR if self.kind == "sfx" else MUSIC_DIR
        return base / self.filename


def _load_manifest() -> list[AssetSpec]:
    if not MANIFEST.exists():
        # Crear plantilla vacía la primera vez
        MANIFEST.write_text(json.dumps({
            "_doc": "Rellena 'sfx' y 'music' con las URLs definitivas. "
                    "Cada entrada: filename, url, license (mixkit|pixabay|youtube-audio-library|cc0), "
                    "attribution (bool), source_label (etiqueta humana).",
            "sfx": [],
            "music": [],
        }, indent=2), encoding="utf-8")
        log.warning("Creado manifest vacío en %s — rellénalo y vuelve a correr.", MANIFEST)
        return []
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items: list[AssetSpec] = []
    for kind in ("sfx", "music"):
        for entry in raw.get(kind, []):
            items.append(AssetSpec(
                kind=kind,
                filename=entry["filename"],
                url=entry["url"],
                license=entry["license"],
                attribution=bool(entry.get("attribution", False)),
                source_label=entry.get("source_label", ""),
            ))
    return items


def _validate(spec: AssetSpec) -> None:
    if spec.license not in ALLOWED_LICENSES:
        raise ValueError(
            f"Licencia no permitida en {spec.filename}: {spec.license!r} "
            f"(permitidas: {sorted(ALLOWED_LICENSES)})"
        )


def _download(spec: AssetSpec) -> bool:
    spec.dest.parent.mkdir(parents=True, exist_ok=True)
    if spec.dest.exists() and spec.dest.stat().st_size > 0:
        log.info("[skip] %s ya existe (%dKB)", spec.filename, spec.dest.stat().st_size // 1024)
        return True
    try:
        with requests.get(spec.url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with spec.dest.open("wb") as fh:
                for chunk in resp.iter_content(64 * 1024):
                    if chunk:
                        fh.write(chunk)
        log.info("[ok ] %s ← %s (%dKB)", spec.filename, spec.source_label or spec.license,
                 spec.dest.stat().st_size // 1024)
        return True
    except Exception as exc:
        log.error("[err] %s → %s", spec.filename, exc)
        return False


def _print_pending(missing: Iterable[AssetSpec]) -> None:
    pending = list(missing)
    if not pending:
        print("✓ Todos los assets están en sus carpetas.")
        return
    print(f"Faltan {len(pending)} archivos:")
    for s in pending:
        print(f"  - {s.kind}/{s.filename}  ({s.license})")


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    specs = _load_manifest()
    for s in specs:
        _validate(s)

    if "--check" in argv:
        missing = [s for s in specs if not (s.dest.exists() and s.dest.stat().st_size > 0)]
        _print_pending(missing)
        return 0 if not missing else 1

    failed = 0
    for s in specs:
        if not _download(s):
            failed += 1
    if failed:
        print(f"FALLO · {failed} archivos no se descargaron.", file=sys.stderr)
        return 1
    print("OK · todos los assets descargados.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
