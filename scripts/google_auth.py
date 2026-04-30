"""Construcción de credenciales Google a partir de variables de entorno.

Firulais usa la cuenta `rosiquediego.arji@gmail.com` (separada de cualquier otra
cuenta del usuario). Solo necesitamos el scope de YouTube — el email del flujo
de aprobación lo manda Resend, no Gmail.

Si en el futuro se quisiera leer respuestas "APROBAR" desde Gmail con OAuth,
basta con añadir los scopes en oauth_setup.py y ampliar este helper.

Variables esperadas en el environment:
    YT_CLIENT_ID          (de Google Cloud OAuth client ID)
    YT_CLIENT_SECRET
    YT_REFRESH_TOKEN      (generado una vez con oauth_setup.py)
"""
from __future__ import annotations

import os
from functools import lru_cache

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

YT_TOKEN_URI = "https://oauth2.googleapis.com/token"
YT_SCOPES = ("https://www.googleapis.com/auth/youtube",)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Falta env var {name} (necesaria para Google OAuth)")
    return value


@lru_cache(maxsize=1)
def credentials() -> Credentials:
    """Devuelve credentials cacheadas para esta ejecución."""
    return Credentials(
        token=None,
        refresh_token=_required_env("YT_REFRESH_TOKEN"),
        client_id=_required_env("YT_CLIENT_ID"),
        client_secret=_required_env("YT_CLIENT_SECRET"),
        token_uri=YT_TOKEN_URI,
        scopes=list(YT_SCOPES),
    )


def youtube_client():
    """Cliente listo de YouTube Data API v3."""
    return build("youtube", "v3", credentials=credentials(), cache_discovery=False)
