"""Pixabay Videos API client — primary footage source for Firulais.

Análogo a pexels.py. Si Pixabay rate-limita o no devuelve resultados verticales,
el caller debe hacer fallback a pexels.search_and_download(query, dest).

Docs: https://pixabay.com/api/docs/#api_videos
"""
import os
import sys
import time
from pathlib import Path

import requests

API_KEY = os.environ["PIXABAY_API_KEY"]
BASE = "https://pixabay.com/api/videos/"


def search_first(query: str) -> dict | None:
    """Devuelve el primer video Pixabay vertical (height >= width)."""
    params = {
        "key": API_KEY,
        "q": query,
        "per_page": 8,           # algunos resultados pueden no ser verticales
        "order": "popular",
        "safesearch": "true",    # canal familiar
        "video_type": "film",    # no animaciones, solo footage real
    }
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    for hit in data.get("hits", []):
        # Pixabay no expone orientation directa, hay que mirar dimensiones
        # de cualquiera de los renders (large/medium/small)
        videos = hit.get("videos", {})
        large = videos.get("large", {}) or videos.get("medium", {})
        w = large.get("width", 0)
        h = large.get("height", 0)
        if h > 0 and h >= w:
            return hit
    return None


def best_video_file(hit: dict) -> str:
    """Devuelve URL del render más cercano a 1920px tall sin pasarse a 4K."""
    videos = hit.get("videos", {})
    # Pixabay devuelve: large (1920 alto típico), medium, small, tiny
    candidates = []
    for size_name in ("large", "medium", "small"):
        v = videos.get(size_name)
        if v and v.get("url"):
            candidates.append((v.get("height", 0), v["url"]))
    # Preferir el de altura >= 1920 más bajo posible; si no hay, el más alto disponible
    candidates.sort(key=lambda c: (c[0] < 1920, c[0]))
    return candidates[0][1] if candidates else ""


def download(url: str, dest: Path):
    """Descarga el .mp4 a dest."""
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)


def search_and_download(query: str, dest: Path, retries: int = 2) -> bool:
    """Pipeline completo: search → first vertical → download. True si éxito."""
    for attempt in range(retries + 1):
        try:
            hit = search_first(query)
            if not hit:
                print(f"  [pixabay !] no vertical match for '{query}'", file=sys.stderr)
                return False
            url = best_video_file(hit)
            if not url:
                return False
            download(url, dest)
            print(f"  [pixabay ✓] {query} → {dest.name} ({dest.stat().st_size // 1024}KB)")
            return True
        except requests.HTTPError as e:
            if e.response.status_code in (429, 503):
                wait = 2 ** attempt
                print(f"  [pixabay !] rate-limited, retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  [pixabay ×] HTTP error {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"  [pixabay ×] {e}", file=sys.stderr)
            return False
    return False


if __name__ == "__main__":
    # CLI test
    q = sys.argv[1] if len(sys.argv) > 1 else "puppy golden retriever"
    dest = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/pixabay_test.mp4")
    ok = search_and_download(q, dest)
    sys.exit(0 if ok else 1)
