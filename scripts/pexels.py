"""Cliente Pexels Videos API para Firulais (footage de respaldo).

Pixabay es la fuente primaria del canal; Pexels actúa de fallback cuando
Pixabay rate-limita o no devuelve resultados verticales relevantes.

API key: secret PEXELS_API_KEY (creada con la cuenta nueva del canal).
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger("firulais.pexels")

ENDPOINT = "https://api.pexels.com/videos/search"
DEFAULT_PER_PAGE = 6
RETRY_BACKOFF_SEC = (1, 3, 7)   # tres reintentos exponenciales suaves


@dataclass(frozen=True)
class VideoFile:
    url: str
    width: int
    height: int

    @property
    def is_vertical(self) -> bool:
        return self.height >= self.width

    @property
    def matches_target(self) -> bool:
        return 1920 <= self.height <= 3840


class PexelsClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ["PEXELS_API_KEY"]

    def _headers(self) -> dict:
        return {"Authorization": self.api_key}

    def query(self, term: str, per_page: int = DEFAULT_PER_PAGE) -> list[dict]:
        resp = requests.get(
            ENDPOINT,
            headers=self._headers(),
            params={"query": term, "orientation": "portrait", "per_page": per_page},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("videos", [])

    @staticmethod
    def pick_best_file(video: dict) -> Optional[VideoFile]:
        candidates: list[VideoFile] = []
        for f in video.get("video_files", []):
            if f.get("file_type") != "video/mp4":
                continue
            vf = VideoFile(
                url=f.get("link", ""),
                width=int(f.get("width") or 0),
                height=int(f.get("height") or 0),
            )
            if vf.url and vf.is_vertical:
                candidates.append(vf)
        if not candidates:
            return None
        targeted = [c for c in candidates if c.matches_target]
        if targeted:
            return min(targeted, key=lambda c: c.height)
        return max(candidates, key=lambda c: c.height)

    def fetch_to(self, term: str, dest: Path) -> bool:
        last_error: Optional[BaseException] = None
        for attempt, wait in enumerate((0,) + RETRY_BACKOFF_SEC):
            if wait:
                import time
                time.sleep(wait)
            try:
                videos = self.query(term)
                for v in videos:
                    file = self.pick_best_file(v)
                    if file:
                        _stream_download(file.url, dest)
                        log.info("[pexels] %s → %s (%dKB)", term, dest.name, dest.stat().st_size // 1024)
                        return True
                log.warning("[pexels] sin match vertical para '%s'", term)
                return False
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    log.warning("[pexels] 429 (intento %d), esperando…", attempt)
                    last_error = exc
                    continue
                log.error("[pexels] HTTP %s", exc)
                return False
            except Exception as exc:
                last_error = exc
                log.error("[pexels] %s", exc)
                return False
        if last_error:
            log.error("[pexels] reintentos agotados: %s", last_error)
        return False


def _stream_download(url: str, dest: Path, chunk: int = 256 * 1024) -> None:
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for piece in resp.iter_content(chunk_size=chunk):
                if piece:
                    fh.write(piece)


def search_and_download(query: str, dest: Path) -> bool:
    """API que pipeline.py espera. Internamente delega al PexelsClient."""
    return PexelsClient().fetch_to(query, dest)


def _cli(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    term = argv[1] if len(argv) > 1 else "puppy"
    dest = Path(argv[2] if len(argv) > 2 else "/tmp/firulais_pexels.mp4")
    return 0 if search_and_download(term, dest) else 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
