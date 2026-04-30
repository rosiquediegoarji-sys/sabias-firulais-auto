"""Generador de subtítulos kinetic palabra-por-palabra para Firulais.

Entrada:
- script_with_tags: string del guion plano CON tags inline
    Tags soportados:
        [DING] [BOING] [CASH] [SCRATCH] [WHOOSH] [POP] [GASP] [APPLAUSE]   → SFX (extraídos)
        [*palabra*]                                                        → ÉNFASIS (color amarillo o rojo)
- words_json:        lista de WordBoundary events de edge-tts (offset_ms, duration_ms, word)

Salida:
- archivo .ass kinetic palabra-a-palabra
- (paralelo) archivo .sfx.json con [(timestamp_ms, tag_name)] para sfx_inserter.py
- (paralelo) archivo .circles.json con [(timestamp_ms, "small"|"medium"|"large", anchor_word)]
              para red_circle_overlay.py — uno por cada palabra con [*énfasis*]

Estilo:
- Default: Noto Sans Bold 52pt, blanco, contorno negro 3px, MarginV 560
- Enf:     Noto Sans Bold 64pt, escala 130%, mismo contorno (color override en línea para amarillo o rojo)
- Fade:    80ms entrada / 150ms salida
- Encoding ASS BGR para colores: amarillo &H00FFFF&, rojo &H0000FF&
"""
import json
import re
import sys
from pathlib import Path

SFX_TAGS = {"DING", "BOING", "CASH", "SCRATCH", "WHOOSH", "POP", "GASP", "APPLAUSE"}
TAG_RE = re.compile(r"\[([A-Z_]+)\]|\[\*(.+?)\*\]")

# Colores BGR para libass
COLOR_WHITE = r"&H00FFFFFF&"
COLOR_YELLOW = r"&H0000FFFF&"   # amarillo
COLOR_RED = r"&H000000FF&"      # rojo (en BGR es 0000FF)

ASS_HEADER = """[Script Info]
Title: ¿Sabías, Firulais?
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans Bold,84,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,5,2,2,60,60,560,1
Style: Enf,Noto Sans Bold,108,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,6,3,2,60,60,540,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def parse_script(script: str):
    """Recorre el guion linealizado y extrae:

    - tokens visibles (palabras a renderizar como subtítulo), con flag is_emphasis
    - sfx_marks: lista de (sfx_name, anchor_word_index)
        anchor_word_index = índice del token visible inmediatamente anterior al tag.
        Si el SFX está al principio absoluto, anchor=0.

    Devuelve: (tokens, sfx_marks)
        tokens: list[dict{"text": str, "emphasis": bool, "color": "yellow"|"red"|None}]
        sfx_marks: list[dict{"tag": str, "anchor_word_idx": int}]
    """
    tokens = []
    sfx_marks = []
    cursor = 0
    while cursor < len(script):
        m = TAG_RE.search(script, cursor)
        if not m:
            tail = script[cursor:].strip()
            if tail:
                for w in tail.split():
                    tokens.append({"text": w, "emphasis": False, "color": None})
            break
        # Texto plano antes del tag
        head = script[cursor:m.start()].strip()
        if head:
            for w in head.split():
                tokens.append({"text": w, "emphasis": False, "color": None})
        # Procesar el tag
        sfx_name = m.group(1)
        emph_text = m.group(2)
        if sfx_name and sfx_name in SFX_TAGS:
            sfx_marks.append({"tag": sfx_name, "anchor_word_idx": max(0, len(tokens) - 1)})
        elif emph_text:
            # palabras múltiples dentro del énfasis se renderizan en orden
            for i, w in enumerate(emph_text.split()):
                # primera palabra del énfasis va en color rojo, las demás en amarillo
                # (regla simple y consistente; tunable)
                color = "red" if i == 0 else "yellow"
                tokens.append({"text": w, "emphasis": True, "color": color})
        cursor = m.end()
    return tokens, sfx_marks


def align_tokens_to_words(tokens, words_json):
    """Mapea tokens parseados a los WordBoundary events de edge-tts.

    edge-tts cuenta CADA palabra del texto enviado, incluyendo aquellas dentro
    de tags <phoneme> (ej "Firulais"). El número de tokens del parse_script y
    el número de words_json deberían coincidir 1:1 si el script estaba bien.

    Si hay desalineación, hacemos fallback: distribuimos los tokens uniformemente
    en la duración total y avisamos por stderr.
    """
    if len(tokens) == len(words_json):
        for tok, wb in zip(tokens, words_json):
            tok["start_ms"] = wb["offset_ms"]
            tok["end_ms"] = wb["offset_ms"] + wb["duration_ms"]
        return tokens
    # Fallback: distribución uniforme
    print(
        f"[!] desalineación tokens={len(tokens)} vs words={len(words_json)}, "
        f"fallback a distribución uniforme",
        file=sys.stderr,
    )
    if not words_json:
        for i, tok in enumerate(tokens):
            tok["start_ms"] = i * 350
            tok["end_ms"] = (i + 1) * 350
        return tokens
    total = words_json[-1]["offset_ms"] + words_json[-1]["duration_ms"]
    step = total / max(len(tokens), 1)
    for i, tok in enumerate(tokens):
        tok["start_ms"] = int(i * step)
        tok["end_ms"] = int((i + 1) * step)
    return tokens


def fmt_ts(ms: int) -> str:
    """Formato ASS h:mm:ss.cs (centiseconds)."""
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    cs = (ms % 1000) // 10
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(tokens, output_path: Path):
    """Genera el archivo .ass kinéticamente animado.

    Cada palabra hace un "pop": al aparecer escala de 70% al 110% en 100ms y
    luego se asienta al 100% en 80ms, simulando el efecto bouncy típico de
    TikTok captions. Las palabras enfatizadas además rebotan más fuerte (140%).
    """
    lines = [ASS_HEADER]
    for tok in tokens:
        start = fmt_ts(tok["start_ms"])
        end = fmt_ts(tok["end_ms"])
        style = "Enf" if tok["emphasis"] else "Default"

        # Color override
        color_tag = ""
        if tok["color"] == "red":
            color_tag = r"\c" + COLOR_RED
        elif tok["color"] == "yellow":
            color_tag = r"\c" + COLOR_YELLOW

        # Animación pop: aparece pequeño, crece pasado, vuelve al normal
        # Default: 70% → 110% en 100ms, luego 110% → 100% en 80ms
        # Enf:     70% → 140% en 120ms, luego 140% → 115% en 80ms (más bouncy)
        if tok["emphasis"]:
            anim = (
                r"\fscx70\fscy70"
                r"\t(0,120,\fscx140\fscy140)"
                r"\t(120,200,\fscx115\fscy115)"
            )
        else:
            anim = (
                r"\fscx70\fscy70"
                r"\t(0,100,\fscx110\fscy110)"
                r"\t(100,180,\fscx100\fscy100)"
            )

        # Fade salida 120ms
        fade = r"\fad(0,120)"
        # Border de cada palabra: redondeado-bouncy (no es perfecto en libass pero ayuda)
        # blur 1 da ese halo suave de TikTok
        blur = r"\blur1"

        tags = "".join([anim, fade, blur, color_tag])
        text = f"{{{tags}}}{tok['text']}"
        lines.append(
            f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}"
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_sfx_marks_with_timestamps(sfx_marks, tokens):
    """Convierte (tag, anchor_word_idx) → (tag, timestamp_ms) usando los tokens alineados."""
    out = []
    for m in sfx_marks:
        idx = m["anchor_word_idx"]
        if 0 <= idx < len(tokens):
            ts = tokens[idx].get("end_ms", 0)
        else:
            ts = 0
        out.append({"tag": m["tag"], "timestamp_ms": ts})
    return out


def build_circles_marks(tokens):
    """Una marca de círculo por cada token con énfasis tipo 'red' (la primera palabra
    del énfasis). El módulo red_circle_overlay.py decidirá tamaño y posición.
    """
    out = []
    for i, tok in enumerate(tokens):
        if tok.get("emphasis") and tok.get("color") == "red":
            out.append({
                "timestamp_ms": tok.get("start_ms", 0),
                "duration_ms": max(800, tok.get("end_ms", 0) - tok.get("start_ms", 0) + 600),
                "anchor_word": tok["text"],
                "size": "medium",
            })
    return out


def main():
    if len(sys.argv) < 4:
        print("Uso: gen_subs.py <script_text_file> <words_json> <out_ass> [out_sfx_json] [out_circles_json]")
        sys.exit(1)
    script_path = Path(sys.argv[1])
    words_json_path = Path(sys.argv[2])
    out_ass = Path(sys.argv[3])
    out_sfx_json = Path(sys.argv[4]) if len(sys.argv) > 4 else out_ass.with_suffix(".sfx.json")
    out_circles_json = Path(sys.argv[5]) if len(sys.argv) > 5 else out_ass.with_suffix(".circles.json")

    script = script_path.read_text()
    words_json = json.loads(words_json_path.read_text())

    tokens, sfx_marks = parse_script(script)
    align_tokens_to_words(tokens, words_json)
    build_ass(tokens, out_ass)

    sfx_with_ts = build_sfx_marks_with_timestamps(sfx_marks, tokens)
    out_sfx_json.write_text(json.dumps(sfx_with_ts, ensure_ascii=False, indent=2))

    circles = build_circles_marks(tokens)
    out_circles_json.write_text(json.dumps(circles, ensure_ascii=False, indent=2))

    print(
        f"OK · {len(tokens)} subs → {out_ass.name} · "
        f"{len(sfx_with_ts)} SFX → {out_sfx_json.name} · "
        f"{len(circles)} círculos → {out_circles_json.name}"
    )


if __name__ == "__main__":
    main()
