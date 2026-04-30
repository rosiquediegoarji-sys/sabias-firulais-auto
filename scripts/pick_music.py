#!/usr/bin/env python3
"""Selector de música cálida/juguetona para cada short de Firulais.

Estrategia:
- Lista los .mp3 dentro de `music_library/`.
- Lee `music_used.log` (un archivo de tracker que se commitea cada run) para
  saber cuándo se usó cada track la última vez.
- Asigna a cada track una "frescura" = días desde su último uso.
- Devuelve, ponderado, uno entre los más frescos (top-K) para evitar que dos
  shots consecutivos suenen iguales.
- Registra el uso en el log.

Salida estándar (stdout): ruta absoluta del .mp3 elegido.
"""
from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIBRARY = REPO_ROOT / "music_library"
DEFAULT_LOG = REPO_ROOT / "music_used.log"

TOP_K_FRESH = 3        # entre cuántos tracks "más frescos" elegimos al azar
NEVER_USED_BIAS = 1e9  # un track nunca usado vale lo más posible


def _load_last_used(log_path: Path) -> dict[str, datetime]:
    if not log_path.exists():
        return {}
    last: dict[str, datetime] = {}
    for raw in log_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Formato: "ISO8601<tab>basename"
        try:
            iso, name = line.split("\t", 1)
            ts = datetime.fromisoformat(iso)
            previous = last.get(name)
            if previous is None or ts > previous:
                last[name] = ts
        except (ValueError, IndexError):
            continue
    return last


def _freshness(track: Path, last_used: dict[str, datetime], now: datetime) -> float:
    seen = last_used.get(track.name)
    if seen is None:
        return NEVER_USED_BIAS
    return (now - seen).total_seconds() / 3600.0  # horas desde el último uso


def _pick(tracks: Iterable[Path], last_used: dict[str, datetime]) -> Path:
    now = datetime.now(timezone.utc)
    ranked = sorted(tracks, key=lambda t: _freshness(t, last_used, now), reverse=True)
    if not ranked:
        raise FileNotFoundError("music_library está vacío")
    pool = ranked[: max(1, TOP_K_FRESH)]
    return random.choice(pool)


def _record_use(track: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp}\t{track.name}\n")


def select_track(library: Path = DEFAULT_LIBRARY,
                 usage_log: Path = DEFAULT_LOG) -> Path:
    library = Path(os.environ.get("MUSIC_DIR", library))
    tracks = sorted(library.glob("*.mp3"))
    chosen = _pick(tracks, _load_last_used(usage_log))
    _record_use(chosen, usage_log)
    return chosen.resolve()


def main(argv: list[str]) -> int:
    library = Path(argv[1]) if len(argv) > 1 else DEFAULT_LIBRARY
    usage = Path(argv[2]) if len(argv) > 2 else DEFAULT_LOG
    try:
        track = select_track(library, usage)
    except FileNotFoundError as exc:
        # Library vacío: emitir cadena vacía (no es un error fatal — el
        # pipeline cae al fallback de silencio). Mantener exit code 0
        # para no romper subprocess.check_output del orquestador.
        print(f"[pick_music] library vacío ({exc}); el pipeline usará silencio.",
              file=sys.stderr)
        print()
        return 0
    print(track)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
