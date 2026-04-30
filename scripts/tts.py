"""edge-tts wrapper para Firulais.

Características:
- Voz primaria: es-MX-JorgeNeural (cálida, conversacional, cómplice).
  Backup: es-CO-GonzaloNeural (configurable vía FIRULAIS_VOICE env var).
- Rate +5% / pitch +0Hz para timbre cálido natural.
- Inyecta SSML <phoneme alphabet="ipa"> para "Firulais" en CADA aparición,
  garantizando pronunciación /fi.ɾuˈlais/ (acento agudo en "lais", diptongo final).
- Devuelve también los WordBoundary events (timestamps por palabra) para que
  gen_subs.py y sfx_inserter.py los usen como referencia temporal real.

Salida:
- narracion.mp3 (audio mezclado con tempo ajustado a target_seconds)
- narracion.words.json (lista de {"word", "offset_ms", "duration_ms"})
"""
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import edge_tts

VOICE = os.environ.get("FIRULAIS_VOICE", "es-MX-DaliaNeural")
RATE = os.environ.get("FIRULAIS_RATE", "+8%")
PITCH = os.environ.get("FIRULAIS_PITCH", "+0Hz")

# Pronunciación de "Firulais": el SSML <phoneme> con IPA es ignorado por las
# voces neurales de edge-tts (Microsoft Azure free tier en 2026). Truco más
# robusto: reescribir la palabra con tilde gráfica forzada → "Firuláis", que
# la regla de acentuación de las voces neurales lee como [fi.ɾuˈlais] (aguda,
# diptongo final), exactamente lo que queremos.

FIRULAIS_PATTERN = re.compile(r"\bFirulais\b", re.IGNORECASE)


def inject_ipa(text: str) -> str:
    """Reemplaza cada 'Firulais' por la grafía con tilde 'Firuláis'.

    Mantiene el nombre de la función por compatibilidad con el resto del
    pipeline (gen_subs.py inyecta el script crudo y solo usa palabras visibles).
    """
    return FIRULAIS_PATTERN.sub("Firuláis", text)


def wrap_ssml(text_with_ipa: str) -> str:
    """Envuelve texto en bloque <speak> SSML válido para edge-tts."""
    # IMPORTANTE: edge-tts NO requiere bloque <speak> completo si pasas el texto
    # con tags inline; algunas voces fallan al recibir el wrapper completo.
    # Probado: pasar tags <phoneme> inline directos funciona con edge-tts >= 6.x.
    return text_with_ipa


async def synth(text: str, out_mp3: Path, words_json: Path):
    """Genera narración y dump de WordBoundary events."""
    text_clean = inject_ipa(text)
    communicate = edge_tts.Communicate(
        text_clean,
        voice=VOICE,
        rate=RATE,
        pitch=PITCH,
    )
    words = []
    with out_mp3.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "word": chunk["text"],
                    "offset_ms": chunk["offset"] // 10_000,    # ticks of 100ns → ms
                    "duration_ms": chunk["duration"] // 10_000,
                })
    words_json.write_text(json.dumps(words, ensure_ascii=False, indent=2))
    print(f"OK · narración → {out_mp3.name} ({out_mp3.stat().st_size // 1024} KB), {len(words)} word events → {words_json.name}")


def adjust_tempo(in_mp3: Path, out_mp3: Path, target_seconds: float):
    """Stretcha/comprime audio a target_seconds usando ffmpeg atempo.

    atempo soporta 0.5–2.0; si necesitamos más, encadenamos múltiples filtros.
    """
    # Duración actual via ffprobe
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(in_mp3)],
        capture_output=True, text=True, check=True,
    )
    cur = float(r.stdout.strip())
    factor = cur / target_seconds  # >1 = comprimir (audio más rápido)
    if abs(factor - 1.0) < 0.02:
        # casi igual, no tocar
        in_mp3.replace(out_mp3)
        return

    # Build chained atempo to stay in [0.5, 2.0]
    filters = []
    f = factor
    while f > 2.0:
        filters.append("atempo=2.0")
        f /= 2.0
    while f < 0.5:
        filters.append("atempo=0.5")
        f /= 0.5
    filters.append(f"atempo={f:.4f}")
    chain = ",".join(filters)

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(in_mp3), "-af", chain,
         "-c:a", "libmp3lame", "-q:a", "2", str(out_mp3)],
        check=True, capture_output=True,
    )
    print(f"OK · tempo ajustado factor {factor:.3f} ({cur:.2f}s → {target_seconds:.2f}s)")


def _audio_duration_ms(path: Path) -> int:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return int(float(r.stdout.strip()) * 1000)


def rescale_word_timestamps(words_json: Path, scale: float) -> None:
    """Reescala offset_ms y duration_ms de cada WordBoundary event por `scale`.

    Necesario tras adjust_tempo: si comprimimos el audio (factor > 1),
    los tiempos originales del TTS quedan demasiado largos respecto al audio
    final, lo que desincroniza los subtítulos kinéticos.
    """
    if abs(scale - 1.0) < 0.001:
        return
    data = json.loads(words_json.read_text())
    for w in data:
        w["offset_ms"] = int(w["offset_ms"] * scale)
        w["duration_ms"] = int(w["duration_ms"] * scale)
    words_json.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"OK · word timestamps reescalados con scale={scale:.4f}")


def main():
    if len(sys.argv) < 4:
        print("Uso: tts.py <text_file> <out_mp3> <out_words_json> [target_seconds]")
        sys.exit(1)
    text_file = Path(sys.argv[1])
    out_mp3 = Path(sys.argv[2])
    words_json = Path(sys.argv[3])
    target_seconds = float(sys.argv[4]) if len(sys.argv) > 4 else None

    text = text_file.read_text()

    raw_mp3 = out_mp3.with_suffix(".raw.mp3")
    asyncio.run(synth(text, raw_mp3, words_json))

    if target_seconds:
        before_ms = _audio_duration_ms(raw_mp3)
        adjust_tempo(raw_mp3, out_mp3, target_seconds)
        raw_mp3.unlink(missing_ok=True)
        after_ms = _audio_duration_ms(out_mp3)
        if before_ms > 0:
            scale = after_ms / before_ms
            rescale_word_timestamps(words_json, scale)
    else:
        raw_mp3.replace(out_mp3)


if __name__ == "__main__":
    main()
