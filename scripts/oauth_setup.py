"""Setup OAuth de un solo uso para el canal "¿Sabías, Firulais?".

Este script SOLO se corre en el Mac de Diego. NO va al runner. Su único objetivo
es generar el `refresh_token` de YouTube Data API para la cuenta nueva del canal
(`rosiquediego.arji@gmail.com`), y dejarlo listo para registrar como Secrets en
GitHub.

Pasos previos (manuales, se documentan en SETUP_DIEGO.md):
  1. Crear OAuth Client ID tipo "Desktop app" en Google Cloud Console (proyecto
     `sabias-firulais-auto`).
  2. Bajar el JSON y guardarlo como `scripts/credentials.json`.
  3. Habilitar "YouTube Data API v3".
  4. Añadir `rosiquediego.arji@gmail.com` como Test User en el OAuth consent screen.

Una vez hecho lo anterior:
    python3 scripts/oauth_setup.py

Imprime tres valores. Pégalos como Secrets del repo `sabias-firulais-auto`:
    YT_CLIENT_ID
    YT_CLIENT_SECRET
    YT_REFRESH_TOKEN

Scopes solicitados:
    youtube  → permite subir videos, crear/editar playlists y añadir items.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

CREDENTIALS_FILE = Path(__file__).resolve().parent / "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/youtube"]
EXPECTED_ACCOUNT = "rosiquediego.arji@gmail.com"


def _abort(msg: str, code: int = 1) -> None:
    print(f"\n[abort] {msg}\n", file=sys.stderr)
    sys.exit(code)


def _load_client_info() -> dict:
    if not CREDENTIALS_FILE.exists():
        _abort(
            f"Falta {CREDENTIALS_FILE}. Descarga el client_id JSON de Google Cloud Console "
            f"(APIs & Services → Credentials → tu OAuth client Desktop → Download JSON) "
            f"y guárdalo con ese nombre exacto."
        )
    raw = json.loads(CREDENTIALS_FILE.read_text())
    return raw.get("installed") or raw.get("web") or {}


def main() -> None:
    client_info = _load_client_info()

    print("=" * 64)
    print(" Firulais · OAuth setup (una sola vez)")
    print("=" * 64)
    print(f" Cuenta esperada: {EXPECTED_ACCOUNT}")
    print(f" Scopes:          {SCOPES}")
    print()
    print(" Se va a abrir tu navegador. Asegúrate de loguear con esa cuenta.")
    print(" Si Google avisa 'app no verificada', click 'Avanzado' → 'Continuar (sin seguridad)'.")
    print("=" * 64, "\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    print("\n" + "=" * 64)
    print(" ✓ OAuth completado. Pega estos valores en los Secrets del repo:")
    print("=" * 64)
    print(f" YT_CLIENT_ID     = {client_info.get('client_id', '(no en JSON)')}")
    print(f" YT_CLIENT_SECRET = {client_info.get('client_secret', '(no en JSON)')}")
    print(f" YT_REFRESH_TOKEN = {creds.refresh_token}")
    print("=" * 64)
    print()
    print(" También guarda este JSON completo como Secret YT_TOKEN_JSON")
    print(" (lo usa setup_playlists.py):")
    print()
    payload = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
