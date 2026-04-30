"""Genera fragmento de filter_complex de ffmpeg para superponer círculos rojos
animados (fade-in/fade-out) sobre el video.

Entrada:
- circles_marks_json: lista de {"timestamp_ms", "duration_ms", "anchor_word", "size"}
                      (producida por gen_subs.py)

Salida:
- imprime por stdout las flags `-i assets/circle_red_X.png` extra que hay que añadir al ffmpeg
- imprime por stdout el fragmento de filter_complex que cuelga del último video stream label

Uso:
    Llamado desde render.sh con un nombre de stream de entrada (ej "[v_color]") y devuelve
    el nombre del stream de salida (ej "[v_with_circles]").

Estrategia técnica:
- Cada PNG asset (small/medium/large) se carga UNA vez como input adicional
- Para cada mark se crea un sub-stream con scale (mantener ratio), fade in/out y overlay enabled solo en el rango temporal
- Posición default: el centro horizontal del cuadrante donde "típicamente" aparece el animal en
  los clips Pexels/Pixabay (top-center 35% W, 40% H). En la versión 2 se podrá pasar X,Y por mark.
"""
import json
import sys
from pathlib import Path

ASSETS_DIR_DEFAULT = Path(__file__).parent.parent / "assets"

SIZE_TO_FILE = {
    "small":  "circle_red_small.png",
    "medium": "circle_red_medium.png",
    "large":  "circle_red_large.png",
}

# Posiciones (X expresado en fracción del ancho, Y en fracción del alto, anchor center)
# Default: tres anchors rotativos para evitar que el círculo siempre aparezca en el mismo sitio
ROTATION_ANCHORS = [
    (0.50, 0.40),
    (0.40, 0.55),
    (0.60, 0.45),
]


def build_overlay_filter(input_video_label: str,
                          first_extra_input_idx: int,
                          marks: list[dict],
                          assets_dir: Path = ASSETS_DIR_DEFAULT) -> tuple[list[str], str, str]:
    """
    Devuelve:
        - lista de paths a los PNGs que hay que añadir como -i extras (en orden de uso)
        - fragmento de filter_complex
        - label del stream de video de salida (ej "[v_circles]")

    `input_video_label` viene del pipeline anterior (ej "[v_color]").
    `first_extra_input_idx` es el primer índice de input ffmpeg disponible (después de los ya en uso).
    """
    if not marks:
        return [], "", input_video_label  # passthrough

    # Cargar cada tamaño de PNG una sola vez como input
    sizes_used = sorted(set(m.get("size", "medium") for m in marks))
    extra_inputs = [str(assets_dir / SIZE_TO_FILE[s]) for s in sizes_used]
    size_to_input_idx = {s: first_extra_input_idx + i for i, s in enumerate(sizes_used)}

    parts = []
    current_v_label = input_video_label

    for i, mark in enumerate(marks):
        size = mark.get("size", "medium")
        ts_s = mark["timestamp_ms"] / 1000.0
        dur_s = max(0.6, mark.get("duration_ms", 800) / 1000.0)
        anchor_x, anchor_y = ROTATION_ANCHORS[i % len(ROTATION_ANCHORS)]

        in_idx = size_to_input_idx[size]
        prepared_label = f"[circ{i}]"
        # Escalar al tamaño "natural" del PNG (no escalar — ya viene del tamaño correcto)
        # Aplicar fade-in 0.15s, fade-out 0.25s
        parts.append(
            f"[{in_idx}:v]format=rgba,"
            f"fade=t=in:st={ts_s:.3f}:d=0.15:alpha=1,"
            f"fade=t=out:st={(ts_s + dur_s - 0.25):.3f}:d=0.25:alpha=1"
            f"{prepared_label}"
        )

        next_v_label = f"[v_c{i}]"
        # overlay anchored to (anchor_x*W - w/2), enabled solo durante el rango
        parts.append(
            f"{current_v_label}{prepared_label}"
            f"overlay=x='W*{anchor_x}-w/2':y='H*{anchor_y}-h/2':"
            f"enable='between(t,{ts_s:.3f},{ts_s + dur_s:.3f})'"
            f"{next_v_label}"
        )
        current_v_label = next_v_label

    return extra_inputs, "; ".join(parts), current_v_label


def main():
    """CLI: lee circles.json, imprime JSON con extra_inputs y filter para que render.sh consuma."""
    if len(sys.argv) < 2:
        print("Uso: red_circle_overlay.py <circles_marks.json> [input_video_label] [first_extra_input_idx]")
        sys.exit(1)
    marks = json.loads(Path(sys.argv[1]).read_text())
    in_label = sys.argv[2] if len(sys.argv) > 2 else "[v_in]"
    first_idx = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    extras, filter_str, out_label = build_overlay_filter(in_label, first_idx, marks)
    out = {
        "extra_inputs": extras,
        "filter_complex_fragment": filter_str,
        "output_video_label": out_label,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
