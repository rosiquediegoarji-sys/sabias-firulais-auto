"""Orquestador master del pipeline Firulais.

Flujo:
  1. Pick topic según SLOT_BIAS
  2. TTS narración + WordBoundary events
  3. Buscar 10 clips Pixabay (fallback Pexels) según keywords del topic
  4. Pick música del library
  5. Generar .ass kinetic + .sfx.json + .circles.json
  6. Mezclar audio: narración + música + SFX (con ducking)
  7. Render video: clips → concat → color grading → overlay círculos rojos → quemar subs → multiplex con audio
  8. Subir .mp4 a R2
  9. Mandar email a RECIPIENT_EMAIL con link
 10. Marcar topic como done_topics.md

NOTA: Esta es la v0 de pipeline.py — esqueleto que llama a los módulos correctos.
La parte de render.sh (paso 7) está pendiente de la versión final con concat de
N clips + cinematic effects. La v0 hace un render simplificado de un solo clip
+ audio, suficiente para validar el "look & feel" del primer short de prueba.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"
SFX_DIR = ROOT / "sfx_library"
MUSIC_DIR = ROOT / "music_library"
ASSETS = ROOT / "assets"
WORK = ROOT / "work"
EXPORT = ROOT / "export"

# ---------------------------------------------------------------------------

def step(msg: str):
    print(f"\n=== {msg} ===", flush=True)


def run(cmd: list[str], **kw):
    print(f"$ {' '.join(str(c) for c in cmd)}", flush=True)
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        raise SystemExit(f"FALLO: {' '.join(str(c) for c in cmd)} (exit {r.returncode})")
    return r


def main():
    slot_bias = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SLOT_BIAS", "MASCOTA")
    WORK.mkdir(parents=True, exist_ok=True)
    EXPORT.mkdir(parents=True, exist_ok=True)

    # --- 1. Topic ---
    step(f"1/9  Generar topic ({slot_bias})")
    out = subprocess.check_output(
        [sys.executable, str(SCRIPTS / "generate_topic.py"), slot_bias],
        text=True,
    )
    topic = json.loads(out)
    print(json.dumps(topic, ensure_ascii=False, indent=2))
    name_safe = topic["id"].replace("/", "_")
    target_seconds = float(topic.get("target_seconds", 30))

    # --- 2. TTS ---
    step("2/9  TTS narración")
    text_file = WORK / "script.txt"
    # IMPORTANTE: el tts.py necesita el TEXTO PARA HABLAR (sin tags [DING] ni [*énfasis*]).
    # Pero el guion del topic SÍ tiene tags. Hay que limpiarlos antes de pasarlos a TTS,
    # PERO conservar la versión con tags para gen_subs.py.
    full_script = topic["script"]
    text_file.write_text(full_script)
    # Generar versión "spoken" (sin tags [...] ni asteriscos)
    import re
    spoken = re.sub(r"\[(?:[A-Z_]+|\*[^\]]+\*)\]", "", full_script)
    spoken = re.sub(r"\s+", " ", spoken).strip()
    spoken_file = WORK / "spoken.txt"
    spoken_file.write_text(spoken)

    narration_mp3 = WORK / "narracion.mp3"
    words_json = WORK / "narracion.words.json"
    run([
        sys.executable, str(SCRIPTS / "tts.py"),
        str(spoken_file), str(narration_mp3), str(words_json),
        f"{target_seconds:.2f}",
    ])

    # --- 3. Footage (Pixabay primario, Pexels backup) ---
    step("3/9  Descargar footage")
    # Estrategia simple v0: 10 clips, uno por keyword (con fallback)
    clips_dir = WORK / "clips"
    clips_dir.mkdir(exist_ok=True)
    keywords = topic.get("keywords", [])[:10]
    # Lazy imports para que pipeline.py corra sin las APIs configuradas en pruebas locales
    sys.path.insert(0, str(SCRIPTS))
    import pixabay
    import pexels
    for i, kw in enumerate(keywords, 1):
        dest = clips_dir / f"clip_{i:02d}.mp4"
        ok = pixabay.search_and_download(kw, dest) if os.environ.get("PIXABAY_API_KEY") else False
        if not ok and os.environ.get("PEXELS_API_KEY"):
            ok = pexels.search_and_download(kw, dest)
        if not ok:
            print(f"  [!] sin footage para '{kw}', se reusará otro clip más adelante")

    # --- 4. Pick music ---
    step("4/9  Pick música")
    music_pick = subprocess.check_output(
        [sys.executable, str(SCRIPTS / "pick_music.py")],
        text=True, env={**os.environ, "MUSIC_DIR": str(MUSIC_DIR)},
    ).strip()
    music_path = Path(music_pick) if music_pick else None
    if not music_path or not music_path.exists():
        print("[!] sin música disponible — generando silencio para mezclar")
        music_path = WORK / "silence.mp3"
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=cl=stereo:r=44100",
             "-t", f"{target_seconds + 1:.2f}", "-c:a", "libmp3lame", "-q:a", "2",
             str(music_path)], check=False)

    # --- 5. Generar subs + sfx_marks + circles_marks ---
    step("5/9  Generar subtítulos kinetic + marks")
    ass_file = WORK / "subtitulos.ass"
    sfx_marks_json = WORK / "sfx_marks.json"
    circles_json = WORK / "circles.json"
    run([
        sys.executable, str(SCRIPTS / "gen_subs.py"),
        str(text_file), str(words_json), str(ass_file),
        str(sfx_marks_json), str(circles_json),
    ])

    # --- 6. Mix audio ---
    step("6/9  Mix audio (narración + música + SFX con ducking)")
    audio_mixed = WORK / "audio_mixed.m4a"
    run([
        sys.executable, str(SCRIPTS / "sfx_inserter.py"),
        str(narration_mp3), str(music_path), str(sfx_marks_json),
        str(audio_mixed), str(SFX_DIR),
    ])

    # --- 7. Render video (v0 simplificado) ---
    step("7/9  Render video (v0 — 1 clip + subs + audio)")
    # v0 muy minimal: tomar el primer clip, recortarlo a target_seconds, quemar subs, multiplexar con audio.
    # La versión final hará concat de los 10 clips con cinematic effects.
    clips = sorted(clips_dir.glob("clip_*.mp4"))
    if not clips:
        raise SystemExit("Sin clips de footage — abortando render. Verifica las API keys.")
    base_clip = clips[0]
    final_mp4 = EXPORT / f"firulais_{name_safe}.mp4"
    run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(base_clip),
        "-i", str(audio_mixed),
        "-vf", (
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,fps=30,"
            f"ass={ass_file}"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        "-shortest",
        "-t", f"{target_seconds:.2f}",
        str(final_mp4),
    ])
    print(f"[OK] render → {final_mp4}")

    # --- 8. Upload R2 ---
    step("8/9  Upload R2")
    if all(os.environ.get(k) for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")):
        from upload_r2 import upload
        public_url = upload(final_mp4, key=f"{int(time.time())}_{final_mp4.name}")
        print(f"[OK] R2 URL: {public_url}")
    else:
        print("[!] R2 secrets ausentes — skipping upload (modo local).")
        public_url = f"file://{final_mp4}"

    # --- 9. Email ---
    step("9/9  Email a RECIPIENT_EMAIL")
    if os.environ.get("RESEND_API_KEY"):
        from send_email import send
        body_md = topic["script"] + "\n\nFuentes:\n" + "\n".join(f"- {s}" for s in topic.get("sources", []))
        send(
            subject=f"[FIRULAIS] {slot_bias} · {topic['title']}",
            body_md=body_md,
            video_url=public_url,
            slot=slot_bias,
            topic=topic["title"],
        )
    else:
        print("[!] RESEND_API_KEY ausente — skipping email (modo local).")

    # --- Tracker ---
    subprocess.run(
        [sys.executable, str(SCRIPTS / "generate_topic.py"), slot_bias, "--mark"],
        check=False,
    )
    print("\n=== PIPELINE COMPLETADO ===")


if __name__ == "__main__":
    main()
