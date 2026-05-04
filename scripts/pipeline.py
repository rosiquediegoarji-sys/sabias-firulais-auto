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
    # NO pasamos target_seconds — dejamos que la voz dure lo que dure
    # naturalmente. Estirar/comprimir audio rompe WordBoundary events y
    # genera artefactos audibles ("voz pegada"/lenta). Ajustamos el video
    # al audio en el paso de render.
    run([
        sys.executable, str(SCRIPTS / "tts.py"),
        str(spoken_file), str(narration_mp3), str(words_json),
    ])

    # Leer la duración real del audio resultante y reajustar target_seconds
    import subprocess as _sp
    _r = _sp.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(narration_mp3)],
        capture_output=True, text=True, check=True,
    )
    actual_audio_seconds = float(_r.stdout.strip())
    # Damos 0.5s extra al final para que la última palabra respire
    target_seconds = actual_audio_seconds + 0.5
    print(f"[duración] audio narración = {actual_audio_seconds:.2f}s; video objetivo = {target_seconds:.2f}s")

    # --- 3. Footage (Pixabay primario, Pexels backup) ---
    step("3/9  Descargar footage")
    clips_dir = WORK / "clips"
    clips_dir.mkdir(exist_ok=True)

    # Estrategia: mezclar keywords del topic + 3 cute genéricos para asegurar
    # que SIEMPRE haya cachorros/cositas tiernas en el video. El feedback
    # del canal pide "animales chistosos / cachorritos haciendo cosas".
    CUTE_FALLBACKS = [
        "puppy playing",
        "cute kitten",
        "funny animal",
        "baby animal",
        "dog jumping happy",
        "kitten paws",
    ]
    import random
    fallbacks = random.sample(CUTE_FALLBACKS, 3)
    topic_keywords = topic.get("keywords", [])[:7]
    # Intercalamos: cute, topic, cute, topic, ... para variar el ritmo visual
    keywords = []
    for i in range(max(len(topic_keywords), len(fallbacks))):
        if i < len(fallbacks):
            keywords.append(fallbacks[i])
        if i < len(topic_keywords):
            keywords.append(topic_keywords[i])

    sys.path.insert(0, str(SCRIPTS))
    import pixabay
    import pexels
    downloaded = 0
    for i, kw in enumerate(keywords, 1):
        dest = clips_dir / f"clip_{i:02d}.mp4"
        ok = pixabay.search_and_download(kw, dest) if os.environ.get("PIXABAY_API_KEY") else False
        if not ok and os.environ.get("PEXELS_API_KEY"):
            ok = pexels.search_and_download(kw, dest)
        if ok:
            downloaded += 1
        else:
            print(f"  [!] sin footage para '{kw}', se reusará otro clip más adelante")
    print(f"[footage] {downloaded}/{len(keywords)} clips descargados")

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

    # --- 7. Render video v1: multi-clip concat + map audio explícito ---
    step("7/9  Render video v1 (multi-clip concat + audio mixed)")
    clips = sorted(clips_dir.glob("clip_*.mp4"))
    if not clips:
        raise SystemExit("Sin clips de footage — abortando render. Verifica las API keys.")

    # Tomar máximo 8 clips, recortar cada uno a una porción del target_seconds
    n_clips = min(8, len(clips))
    clip_seconds = target_seconds / n_clips
    print(f"[render] {n_clips} clips × {clip_seconds:.2f}s = {target_seconds:.2f}s")

    # Paso 7a — recortar cada clip a 1080×1920 30fps SIN audio, todos misma duración
    trimmed_dir = WORK / "trimmed"
    trimmed_dir.mkdir(exist_ok=True)
    trimmed_files = []
    for i, c in enumerate(clips[:n_clips]):
        out = trimmed_dir / f"trim_{i:02d}.mp4"
        run([
            "ffmpeg", "-y",
            "-stream_loop", "-1",   # loop si el clip es < clip_seconds
            "-i", str(c),
            "-t", f"{clip_seconds:.3f}",
            "-vf", (
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,fps=30,"
                # zoom-in suave del 100% al 108% durante el clip, da movimiento sutil
                "zoompan=z='min(zoom+0.0008,1.08)':d=1:s=1080x1920:fps=30"
            ),
            "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            str(out),
        ])
        trimmed_files.append(out)

    # Paso 7b — concatenar los clips (concat demuxer)
    concat_list = WORK / "concat.txt"
    concat_list.write_text("\n".join(f"file '{f}'" for f in trimmed_files))
    concat_video = WORK / "concat.mp4"
    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "copy",
        str(concat_video),
    ])

    # Paso 7c — quemar subtítulos + multiplexar con audio mixed (¡con -map explícito!)
    final_mp4 = EXPORT / f"firulais_{name_safe}.mp4"
    run([
        "ffmpeg", "-y",
        "-i", str(concat_video),
        "-i", str(audio_mixed),
        "-vf", f"ass={ass_file}",
        "-map", "0:v:0",   # video del concat
        "-map", "1:a:0",   # audio del mix (NO el del clip — bug previo)
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
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
