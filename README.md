# ¿Sabías, Firulais? · pipeline automático

Canal de YouTube Shorts en español sobre datos curiosos de animales, con render 100 % en GitHub Actions y disciplina de aprobación por email antes de publicar.

> **Reglas duras del proyecto** (no se rompen):
> - Cuenta Google única: `rosiquediego.arji@gmail.com`.
> - Toda la infraestructura (cuenta GitHub, API keys, R2, Resend, Cloudflare) es exclusiva del canal.
> - Nada se publica sin email de aprobación con respuesta `APROBAR`.
> - Cero gasto: solo free tier.

---

## ¿Qué hace este repo?

Cada slot horario (5 al día) lanza un workflow que:

1. Selecciona un tema fresco según el pilar del slot.
2. Sintetiza la narración con `edge-tts` (`es-MX-JorgeNeural`) e inyecta SSML IPA para pronunciar bien "Firulais".
3. Descarga 10 clips verticales (Pixabay primario, Pexels backup).
4. Pickea un track de música cálida del library local.
5. Genera subtítulos kinetic palabra-por-palabra (Noto Sans Bold 52 pt) con palabras clave en rojo/amarillo.
6. Mezcla audio con SFX por tags (`[DING]`, `[BOING]`, `[CASH]`, `[SCRATCH]`, `[WHOOSH]`, `[POP]`, `[GASP]`, `[APPLAUSE]`) y ducking automático de la música cuando suena cualquier SFX o la voz.
7. Quema los subs sobre el video y dibuja círculos rojos animados sobre la palabra clave de cada énfasis.
8. Sube el `.mp4` a Cloudflare R2 con URL pública.
9. Envía un email a `rosiquediego.arji@gmail.com` con botón `▶ Ver el short`, guion completo, fuentes verificables y el botón mental de **`APROBAR`**.
10. Marca el tema como `done_topics.md` para no repetirlo.

Tú revisas el video. Si te gusta, respondes `APROBAR` al correo y subes manualmente a YouTube/TikTok/IG/FB. Si no, escribes los cambios y se vuelve a renderizar.

---

## Identidad del canal

- **Nombre**: ¿Sabías, Firulais?
- **Catchphrase obligatoria**: cada video abre con "¿Sabías, Firulais?" en los primeros 0.7 s.
- **Cierre**: "Y tú, Firulais, ¿lo sabías? Sígueme para más datos curiosos."
- **Duración**: 27-32 s.
- **Paleta**: crema (`#fff5e1`) + naranja (`#ff7a3d`) + verde hoja (`#56b870`) + acento rojo (`#ff3344`).
- **Voz**: `es-MX-JorgeNeural` con SSML `<phoneme alphabet="ipa" ph="fi.ɾuˈlais">Firulais</phoneme>`.
- **Subtítulos**: Noto Sans Bold 52 pt, kinetic palabra-por-palabra, palabras clave en rojo o amarillo.

---

## Los 5 pilares (1 por slot)

| Slot CDMX | Cron UTC | Pilar | Idea | Notas |
|---|---|---|---|---|
| 10:00 | `0 16 * * *` | **MASCOTA** | Datos sobre perros, gatos, mascotas | Slot familiar, máxima retención |
| 12:00 | `0 18 * * *` | **RECORD** | "El más X" del reino animal | Hook fuerte de mediodía |
| 14:00 | `0 20 * * *` | **ANIMAL_RARO** | Especies que casi nadie conoce | Curiosidad pura |
| 16:00 | `0 22 * * *` | **SUPERPODER** | Habilidad asombrosa de un animal | Datos científicos verificables |
| 18:00 | `0 0 * * *`  | **MITO** | Mitos animales desmentidos | Genera engagement de comments |

---

## Estructura del repo

```
sabias-firulais-auto/
├── .github/workflows/
│   ├── _template.yml         # plantilla, no corre
│   ├── slot-10am.yml         # MASCOTA
│   ├── slot-12pm.yml         # RECORD
│   ├── slot-2pm.yml          # ANIMAL_RARO
│   ├── slot-4pm.yml          # SUPERPODER
│   └── slot-6pm.yml          # MITO
├── scripts/
│   ├── pipeline.py           # orquestador master
│   ├── tts.py                # edge-tts wrapper + SSML IPA "Firulais"
│   ├── pixabay.py            # footage primario
│   ├── pexels.py             # footage backup
│   ├── pick_music.py         # selección por frescura ponderada
│   ├── gen_subs.py           # ASS kinetic palabra-por-palabra
│   ├── sfx_inserter.py       # mix audio con tags + ducking
│   ├── red_circle_overlay.py # PNG overlays animados
│   ├── generate_topic.py     # banco semilla de los 5 pilares
│   ├── setup_playlists.py    # crea playlists + classify por título
│   ├── upload_r2.py          # storage Cloudflare R2
│   ├── send_email.py         # Resend email aprobación
│   ├── google_auth.py        # OAuth helpers
│   └── oauth_setup.py        # one-time refresh token generator
├── sfx_library/              # SFX commiteados (8 tags)
├── music_library/            # tracks instrumentales commiteados
├── assets/
│   ├── circle_red_small.png
│   ├── circle_red_medium.png
│   └── circle_red_large.png
├── done_topics.md            # tracker (commiteado tras cada run)
├── music_used.log            # tracker (commiteado tras cada run)
├── .gitignore
└── README.md (este archivo)
```

---

## Setup inicial

Lee `~/Documents/Claude/Projects/SABIAS FIRULAIS/SETUP_DIEGO.md` (no está en este repo a propósito; es la guía operativa privada). Hace falta crear, por ese orden:

1. Gmail `rosiquediego.arji@gmail.com`
2. Cuenta GitHub nueva
3. Canal YouTube `@sabiasfirulais`
4. Google Cloud Console + OAuth Client ID Desktop
5. API key Pexels
6. API key Pixabay
7. API key Resend
8. Cloudflare R2 + bucket `sabias-firulais-shorts`
9. (Opcional) handles TikTok/IG/FB con el mismo nombre

Y registrar como **Repository Secrets**:

```
PEXELS_API_KEY
PIXABAY_API_KEY
RESEND_API_KEY
RECIPIENT_EMAIL          rosiquediego.arji@gmail.com
SENDER_EMAIL             onboarding@resend.dev   (default; cambiar al verificar dominio)
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET                sabias-firulais-shorts
R2_PUBLIC_DOMAIN         pub-xxxxxxxx.r2.dev
YT_CLIENT_ID
YT_CLIENT_SECRET
YT_REFRESH_TOKEN
YT_CHANNEL_ID
YT_TOKEN_JSON            (JSON completo de oauth_setup.py, para setup_playlists.py)
```

Y como **Repository Variables** (opcionales, override de defaults en `tts.py`):

```
FIRULAIS_VOICE           es-MX-JorgeNeural
FIRULAIS_RATE            +5%
FIRULAIS_PITCH           +0Hz
```

---

## Coste

| Servicio | Free tier | Uso esperado | Coste |
|---|---|---|---|
| GitHub Actions (repo público) | ilimitado | ~2.000 min/mes | $0 |
| Pexels API | 200 req/h | ~50 req/día | $0 |
| Pixabay API | 100 req/min | ~50 req/día | $0 |
| edge-tts | sin tope práctico | ~30 min audio/día | $0 |
| Resend | 3.000 emails/mes | 150/mes | $0 |
| Cloudflare R2 | 10 GB / 1M req/mes | ~5 GB/mes | $0 |

**Total: $0/mes** mientras se mantenga free tier.

---

## Cómo correr local (modo prueba)

```bash
cd sabias-firulais-auto
python3 -m venv .venv && source .venv/bin/activate
pip install requests boto3 edge-tts google-auth google-auth-oauthlib google-api-python-client
brew install ffmpeg imagemagick    # macOS
brew tap homebrew/cask-fonts && brew install --cask font-noto-sans

# Variables mínimas para probar TTS aislado
export FIRULAIS_VOICE=es-MX-JorgeNeural
export PIXABAY_API_KEY=...    # opcional para esta prueba
export PEXELS_API_KEY=...

python3 scripts/pipeline.py MASCOTA
```

Sin `R2_*` ni `RESEND_API_KEY` el pipeline corre igual y deja el `.mp4` en `export/`. Es el flujo recomendado para el primer short de prueba.

---

## Reglas de contenido (no negociables)

1. **Una fuente verificable por dato**. Sin paper, libro o medio reconocido, el tema no se publica.
2. **Animales en sufrimiento, peleas, caza explícita o sangre = NO**. Audiencia familiar.
3. **No marcar como "Made for Kids"**. Posicionado como General Audience 13+ con voz adulta y framing de divulgación.
4. **Nada de cartoon infantil, voz cantarina, emojis pastel ni tags `#kids`/`#niños`**.
5. **Hook obligatorio "¿Sabías, Firulais?"** en el primer segundo. Sin excepciones.

---

## Estado del proyecto

- ✅ Fase 1 — Investigación: `INVESTIGACION_FASE_1.md`
- 🔄 Fase 2 — Setup: en curso (este repo + SETUP_DIEGO.md)
- ⏳ Fase 2.5 — Render de prueba (1-4 iteraciones hasta look & feel correcto)
- ⏳ Fase 3 — Operación (5 slots/día, email approval, publicación manual)

Más detalle del estado actual en `docs/PROGRESO_FASE_2.md`.
