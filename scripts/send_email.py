"""Envío de emails de aprobación vía Resend (cuenta nueva del canal).

Cada short renderizado dispara un email a `rosiquediego.arji@gmail.com` con:
- asunto que identifica el slot/pilar y el título del tema
- botón con link al .mp4 público en R2
- guion completo + fuentes verificables al pie
- instrucciones para responder "APROBAR"

Resend Free Plan (3000 emails/mes) cubre con sobra los 5 slots/día × 30 días
= 150 emails/mes.

Vars de entorno:
    RESEND_API_KEY    secret del repo
    RECIPIENT_EMAIL   email destino (default: rosiquediego.arji@gmail.com)
    SENDER_EMAIL      sender (default: onboarding@resend.dev hasta verificar
                      dominio propio)
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Iterable

import requests

log = logging.getLogger("firulais.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"

DEFAULT_RECIPIENT = "rosiquediego.arji@gmail.com"
DEFAULT_SENDER = "onboarding@resend.dev"
SENDER_LABEL = "Firulais Auto"

# Paleta del canal (informe Fase 1):
PALETTE = {
    "cream": "#fff5e1",
    "orange": "#ff7a3d",
    "leaf": "#56b870",
    "accent_red": "#ff3344",
    "ink": "#1f1f1f",
    "muted": "#6e6e6e",
}

HTML_SHELL = """
<div style="font-family: ui-sans-serif, -apple-system, system-ui, sans-serif;
            max-width: 620px; margin: 0 auto; line-height: 1.55;
            color: {ink}; background: {cream}; padding: 28px; border-radius: 14px;">
  <div style="font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
              color: {muted};">¿Sabías, Firulais? · {slot}</div>
  <h2 style="margin: 6px 0 18px; font-size: 22px; color: {ink};">{title}</h2>

  <a href="{video_url}"
     style="display: inline-block; background: {orange}; color: {cream};
            padding: 14px 28px; text-decoration: none; border-radius: 999px;
            font-weight: 700; box-shadow: 0 6px 18px rgba(255,122,61,.25);">
     ▶ Ver el short
  </a>

  <p style="margin-top: 14px; font-size: 13px; color: {muted};">
     Link directo (por si el botón no funciona):
     <a href="{video_url}" style="color: {orange};">{video_url}</a>
  </p>

  <hr style="border: 0; border-top: 1px dashed {leaf}; margin: 26px 0;">

  <div style="font-size: 14px; white-space: pre-wrap;">{body}</div>

  <hr style="border: 0; border-top: 1px solid #00000010; margin: 26px 0;">

  <p style="font-size: 13px; color: {muted};">
     Para publicar este short, responde a este correo con la palabra
     <strong style="color: {accent_red};">APROBAR</strong> (mayúsculas o minúsculas).<br>
     Si quieres pedir cambios, descríbelos y vuelvo a renderizar.
  </p>

  <p style="font-size: 11px; color: {muted}; margin-top: 22px;">
     Pipeline automatizado de "¿Sabías, Firulais?" · GitHub Actions · {slot}
  </p>
</div>
"""


def _render_html(slot: str, title: str, body: str, video_url: str) -> str:
    return HTML_SHELL.format(slot=slot, title=title, body=body, video_url=video_url, **PALETTE)


def _resolve_recipient() -> str:
    return os.environ.get("RECIPIENT_EMAIL") or DEFAULT_RECIPIENT


def _resolve_sender() -> str:
    return os.environ.get("SENDER_EMAIL") or DEFAULT_SENDER


def send(*, subject: str, body_md: str, video_url: str, slot: str, topic: str,
         attachments: Iterable[Path] = ()) -> str:
    """Manda el email. Devuelve el message-id de Resend.

    El parámetro `attachments` está reservado para futuro (p.ej. mandar el .mp4
    como adjunto si la cuota de Resend lo permite). Hoy no se usa para mantener
    los emails ligeros.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise EnvironmentError("RESEND_API_KEY no está configurada")

    recipient = _resolve_recipient()
    sender = _resolve_sender()
    html = _render_html(slot=slot, title=topic, body=body_md, video_url=video_url)

    payload = {
        "from": f"{SENDER_LABEL} <{sender}>",
        "to": [recipient],
        "subject": subject,
        "html": html,
        "tags": [
            {"name": "channel", "value": "sabias-firulais"},
            {"name": "slot", "value": slot.lower()},
        ],
    }
    resp = requests.post(
        RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    message_id = resp.json().get("id", "?")
    log.info("[email] enviado a %s · message-id=%s", recipient, message_id)
    print(f"OK · email a {recipient} · id={message_id}")
    return message_id


def _cli(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(argv) < 6:
        print("Uso: send_email.py <subject> <body_file> <video_url> <slot> <topic>",
              file=sys.stderr)
        return 2
    subject = argv[1]
    body = Path(argv[2]).read_text()
    video_url = argv[3]
    slot = argv[4]
    topic = argv[5]
    send(subject=subject, body_md=body, video_url=video_url, slot=slot, topic=topic)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
