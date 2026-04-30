"""Crea/actualiza las 5 playlists oficiales de Firulais y mapea videos a ellas.

Características:
- Las 5 playlists son los 5 pilares (SUPERPODER, RECORD, MASCOTA, ANIMAL_RARO, MITO).
- Patterns regex específicos del nicho animal para clasificar videos por título.
- Idempotente: si ya existe la playlist con ese título, la reusa.

Uso:
    python setup_playlists.py            # crea las playlists si faltan, escribe playlist_ids.json
    python setup_playlists.py --classify TITLE DESCRIPTION  # devuelve slug del pilar al que pertenece
"""
import json
import os
import re
import sys
from pathlib import Path

# Lazy import para no requerir google-api-python-client en --classify
def _yt_service():
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    token_data = json.loads(os.environ["YT_TOKEN_JSON"])
    creds = Credentials.from_authorized_user_info(token_data)
    return build("youtube", "v3", credentials=creds)


PLAYLISTS = [
    {
        "slug": "SUPERPODER",
        "title": "Superpoderes animales · ¿Sabías, Firulais?",
        "description": "Habilidades asombrosas de animales reales. Cada video citado y verificado.",
        "patterns": [
            r"superpoder", r"asombros[oa]", r"sobrevive", r"resist[ae]", r"regenera",
            r"increíble", r"poder oculto",
        ],
    },
    {
        "slug": "RECORD",
        "title": "Récords del reino animal · ¿Sabías, Firulais?",
        "description": "El más rápido, el más viejo, el más raro. Datos extremos verificados.",
        "patterns": [
            r"r[eé]cord", r"el m[áa]s r[áa]pido", r"el m[áa]s grande", r"el m[áa]s peque[ñn]o",
            r"el m[áa]s viejo", r"el m[áa]s venenoso", r"el m[áa]s fuerte", r"l[íi]der",
        ],
    },
    {
        "slug": "MASCOTA",
        "title": "Mascotas curiosas · ¿Sabías, Firulais?",
        "description": "Datos sobre perros, gatos y otras mascotas que probablemente no conocías.",
        "patterns": [
            r"perr[oa]s?", r"gat[oa]s?", r"mascota", r"canino", r"felino",
            r"cachorr[oa]", r"gatit[oa]", r"due[ñn]o",
        ],
    },
    {
        "slug": "ANIMAL_RARO",
        "title": "Animales raros y desconocidos · ¿Sabías, Firulais?",
        "description": "Especies que casi nadie conoce. Naturaleza en sus rincones más extraños.",
        "patterns": [
            r"rar[oa]", r"desconocid[oa]", r"extra[ñn][oa]", r"oculto",
            r"profundo", r"abismal", r"transparente", r"fantasma",
        ],
    },
    {
        "slug": "MITO",
        "title": "Mitos animales desmentidos · ¿Sabías, Firulais?",
        "description": "Cosas que creías ciertas sobre los animales y la ciencia desmiente.",
        "patterns": [
            r"mito", r"NO\b", r"falso", r"desmienta?[ne]?", r"creencia",
            r"realidad", r"daltónic[oa]",
        ],
    },
]


def classify(title: str, description: str = "") -> str | None:
    """Devuelve el slug del primer pilar cuyo regex matchea el título o descripción."""
    text = f"{title}\n{description}".lower()
    for p in PLAYLISTS:
        for pat in p["patterns"]:
            if re.search(pat, text, re.IGNORECASE):
                return p["slug"]
    return None


def ensure_playlist(yt, p: dict) -> str:
    """Crea la playlist si no existe (match por título exacto). Devuelve playlist_id."""
    # Buscar entre las playlists del canal
    req = yt.playlists().list(part="id,snippet", mine=True, maxResults=50)
    while req:
        resp = req.execute()
        for item in resp.get("items", []):
            if item["snippet"]["title"] == p["title"]:
                return item["id"]
        req = yt.playlists().list_next(req, resp)
    # No existe → crear
    body = {
        "snippet": {
            "title": p["title"],
            "description": p["description"],
            "defaultLanguage": "es",
        },
        "status": {"privacyStatus": "public"},
    }
    resp = yt.playlists().insert(part="snippet,status", body=body).execute()
    print(f"[+] creada playlist {p['slug']}: {resp['id']}")
    return resp["id"]


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--classify":
        title = sys.argv[2] if len(sys.argv) > 2 else ""
        desc = sys.argv[3] if len(sys.argv) > 3 else ""
        slug = classify(title, desc)
        print(slug or "")
        return

    yt = _yt_service()
    out = {}
    for p in PLAYLISTS:
        out[p["slug"]] = ensure_playlist(yt, p)
    out_path = Path(__file__).parent / "playlist_ids.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"OK · playlist_ids.json actualizado: {out_path}")


if __name__ == "__main__":
    main()
