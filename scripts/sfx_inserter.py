"""Mezcla narración + música de fondo + SFX puntuales por tags, con ducking.

Entrada:
- narration: ruta a narracion.mp3 (de tts.py, ya con tempo ajustado)
- music: ruta al track de música de fondo (pick_music.py)
- sfx_marks_json: lista de {"tag", "timestamp_ms"} (de gen_subs.py)
- sfx_dir: carpeta sfx_library/ con los archivos por tag

Salida:
- audio_mixed.m4a: track AAC listo para multiplexar con el video

Filosofía del mix:
- Narración a 1.0 (full)
- Música a 0.18 (volumen base)
- Cada SFX a 0.55 con fade-in 50ms / fade-out 100ms
- Ducking: la música baja con sidechaincompress cuando suena CUALQUIER SFX o la narración
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# Mapeo tag → archivo del library (los archivos viven commiteados en sfx_library/)
SFX_FILES = {
    "DING":     "ding.mp3",
    "BOING":    "boing.mp3",
    "CASH":     "cash_register.mp3",
    "SCRATCH":  "record_scratch.mp3",
    "WHOOSH":   "whoosh.mp3",
    "POP":      "pop.mp3",
    "GASP":     "gasp.mp3",
    "APPLAUSE": "applause.mp3",
}


def build_filter_complex(num_sfx: int, sfx_marks: list[dict], music_volume: float = 0.10) -> str:
    """Construye el filter_complex con N SFX inputs.

    Inputs por orden:
        0: narración
        1: música
        2..(N+1): SFX (uno por mark)

    Estructura:
        [1] volume → music_v
        Por cada SFX i:
            [i+2] adelay=Tms|Tms, volume=0.55, afade=t=in:st=0:d=0.05, afade=t=out:st=...:d=0.10 → sfx_i
        amix de todos los sfx → all_sfx (si hay >= 1)
        sidechaincompress music_v with all_sfx (ducking 8:1) → music_ducked
        amix [0:a][music_ducked][all_sfx] → out
    """
    parts = []
    # Música base con apad para asegurar que cubre toda la duración del mix.
    # Antes la música se "cortaba a la mitad" porque el sidechaincompress sacaba
    # samples solo mientras existiera la sidechain (voz/SFX), y como esos suelen
    # terminar antes que la pista de música, la cola de la canción se perdía.
    # `apad=whole_dur=999` extiende la música con silencio si fuera más corta;
    # luego el `-shortest` del mux final recorta al min(audio, video).
    parts.append(f"[1:a]volume={music_volume},apad=whole_dur=120[music_base]")

    sfx_streams = []
    for idx, mark in enumerate(sfx_marks):
        ts_ms = max(0, int(mark["timestamp_ms"]))
        in_idx = idx + 2  # input N°
        sfx_streams.append(f"[sfx{idx}]")
        parts.append(
            f"[{in_idx}:a]adelay={ts_ms}|{ts_ms},"
            f"volume=0.55,"
            f"afade=t=in:st={ts_ms/1000:.3f}:d=0.05,"
            f"afade=t=out:st={(ts_ms/1000 + 0.6):.3f}:d=0.1"
            f"[sfx{idx}]"
        )

    if sfx_streams:
        # Mezcla todos los SFX en una sola pista, y la duplica con asplit
        # porque la usamos dos veces (sidechain + amix final), y ffmpeg solo
        # permite consumir cada label UNA vez.
        parts.append(
            f"{''.join(sfx_streams)}amix=inputs={len(sfx_streams)}:dropout_transition=0:normalize=0,"
            f"asplit=2[all_sfx_duck][all_sfx_mix]"
        )
        # Ducking: la música baja cuando entra cualquier SFX o la narración
        # Encadenamos dos sidechain compressions: una usando la narración, otra usando los SFX
        parts.append(
            "[music_base][0:a]sidechaincompress=threshold=0.04:ratio=8:attack=20:release=300[music_d1]"
        )
        parts.append(
            "[music_d1][all_sfx_duck]sidechaincompress=threshold=0.04:ratio=8:attack=20:release=300[music_ducked]"
        )
        # Mezcla final: narración + música ducked + SFX
        parts.append(
            "[0:a][music_ducked][all_sfx_mix]amix=inputs=3:dropout_transition=0:normalize=0[out]"
        )
    else:
        # Sin SFX: solo narración + música ducked por la voz
        parts.append(
            "[music_base][0:a]sidechaincompress=threshold=0.04:ratio=8:attack=20:release=300[music_ducked]"
        )
        parts.append("[0:a][music_ducked]amix=inputs=2:dropout_transition=0:normalize=0[out]")

    return "; ".join(parts)


def mix(narration: Path, music: Path, sfx_marks: list[dict], sfx_dir: Path, output: Path):
    """Ejecuta ffmpeg con el filter_complex generado."""
    inputs = ["-i", str(narration), "-i", str(music)]
    for mark in sfx_marks:
        tag = mark["tag"]
        sfx_file = SFX_FILES.get(tag)
        if not sfx_file:
            print(f"[!] tag desconocido: {tag} — saltando", file=sys.stderr)
            continue
        sfx_path = sfx_dir / sfx_file
        if not sfx_path.exists():
            print(f"[!] SFX no encontrado: {sfx_path} — saltando", file=sys.stderr)
            continue
        inputs.extend(["-i", str(sfx_path)])

    # Filtrar marks a las que tengan SFX file existente
    valid_marks = [m for m in sfx_marks if (sfx_dir / SFX_FILES.get(m["tag"], "")).exists()]
    fc = build_filter_complex(len(valid_marks), valid_marks)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", fc,
        "-map", "[out]",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        str(output),
    ]
    print(f"[ffmpeg] {' '.join(cmd[:6])}... ({len(valid_marks)} SFX)")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDERR:", r.stderr[-2000:], file=sys.stderr)
        raise SystemExit(f"ffmpeg falló (exit {r.returncode})")
    print(f"OK · audio mezclado → {output.name}")


def main():
    if len(sys.argv) < 5:
        print("Uso: sfx_inserter.py <narration.mp3> <music.mp3> <sfx_marks.json> <output.m4a> [sfx_library_dir]")
        sys.exit(1)
    narration = Path(sys.argv[1])
    music = Path(sys.argv[2])
    marks_json = Path(sys.argv[3])
    output = Path(sys.argv[4])
    sfx_dir = Path(sys.argv[5]) if len(sys.argv) > 5 else Path(__file__).parent.parent / "sfx_library"

    marks = json.loads(marks_json.read_text())
    mix(narration, music, marks, sfx_dir, output)


if __name__ == "__main__":
    main()
