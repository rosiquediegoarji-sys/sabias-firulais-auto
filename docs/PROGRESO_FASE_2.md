# Fase 2 · Progreso

Última actualización: 29-abr-2026.

---

## Hecho ✅

### Estructura del repo
- Carpeta `sabias-firulais-auto/` creada con jerarquía completa
- `.gitignore` que protege `credentials.json`, `token.json`, `work/`, `export/` y secretos
- `README.md` del repo
- Este `PROGRESO_FASE_2.md`

### Scripts (todos escritos desde cero, 0 referencias a otros canales)
- `pipeline.py` — orquestador master (9 pasos)
- `tts.py` — edge-tts + SSML IPA `fi.ɾuˈlais`
- `pixabay.py` — footage primario
- `pexels.py` — footage backup
- `pick_music.py` — selección por frescura ponderada top-K
- `gen_subs.py` — ASS kinetic palabra-por-palabra + extracción de SFX/circles marks
- `sfx_inserter.py` — mix audio con tags `[DING][BOING][CASH][SCRATCH][WHOOSH][POP][GASP][APPLAUSE]` y ducking
- `red_circle_overlay.py` — fragmento de filter_complex para overlays animados
- `generate_topic.py` — banco semilla con 7 temas iniciales (5 pilares cubiertos)
- `setup_playlists.py` — crea las 5 playlists oficiales y clasifica por título
- `upload_r2.py` — Cloudflare R2 con dataclass + slug epoch+sha1
- `send_email.py` — Resend con plantilla HTML Firulais (paleta crema/naranja/verde)
- `google_auth.py` — credentials cacheadas, scope solo YouTube
- `oauth_setup.py` — generador one-time de refresh token
- `fetch_assets.py` — descarga inicial de SFX/música a las carpetas library

### Workflows GitHub Actions
- `_template.yml` (referencia)
- `slot-10am.yml` MASCOTA (cron `0 16 * * *`)
- `slot-12pm.yml` RECORD (cron `0 18 * * *`)
- `slot-2pm.yml` ANIMAL_RARO (cron `0 20 * * *`)
- `slot-4pm.yml` SUPERPODER (cron `0 22 * * *`)
- `slot-6pm.yml` MITO (cron `0 0 * * *`)

### Assets generados
- `assets/circle_red_small.png`
- `assets/circle_red_medium.png`
- `assets/circle_red_large.png`
- `assets_manifest.json` (plantilla, URLs por rellenar al curar la librería)

---

## Pendiente ⏳

### Diego — depende de cuentas (en paralelo, según `SETUP_DIEGO.md`)
- [ ] Crear/confirmar Gmail `rosiquediego.arji@gmail.com`
- [ ] Cuenta GitHub nueva enlazada al Gmail
- [ ] Repo `sabias-firulais-auto` en GitHub (público para minutos ilimitados)
- [ ] Canal YouTube `@sabiasfirulais` con la cuenta nueva
- [ ] Google Cloud Console → proyecto `sabias-firulais-auto` + OAuth Desktop ID
- [ ] API key Pexels nueva
- [ ] API key Pixabay nueva
- [ ] API key Resend nueva
- [ ] Cuenta Cloudflare nueva + R2 bucket `sabias-firulais-shorts`
- [ ] Handles TikTok/IG/FB
- [ ] Pasarme las API keys + el JSON OAuth para configurar Secrets

### Mío — código pendiente (sin bloqueo de cuentas)
- [ ] **`render.sh` v1**: render multi-clip con concat, color grading cálido (sin sepia), zoom-in/out por clip, integración del overlay de círculos rojos y multiplexado con audio mezclado. Hoy `pipeline.py` hace v0 minimal de un solo clip (suficiente para validar look & feel del primer short).
- [ ] **Topics seed expansion**: el banco actual de `generate_topic.py` tiene 7 temas; para sostener 5 slots/día sin reciclar en 3 días necesito ~30-40 temas (6-8 por pilar). Tarea sencilla pero verbosa; la hago cuando me digas o cuando se acerque la primera ventana operativa.
- [ ] **Logo + intro animada Firulais (0,7 s)**: pre-render como `assets/intro_firulais.mp4` para concatenar al inicio de cada short. Necesita decisión visual contigo.
- [ ] **Workflow extra de upload a YouTube**: hoy el flow es "render → email → APROBAR → tú subes manualmente". Si más adelante queremos auto-upload (manteniendo gate de aprobación), añado `youtube-upload.yml` que se dispare por respuesta `APROBAR` parseada de Gmail. **No urgente.**
- [ ] **`fetch_assets.py` con URLs reales**: hoy `assets_manifest.json` es plantilla. Necesito 30-45 min de curaduría manual en Mixkit + Pixabay para llenar las URLs definitivas, descargar y commitear.

### Pendiente conjunto (Diego + yo)
- [ ] Primer render de prueba en local (suficiente con 2-3 keys: PIXABAY o PEXELS + nada más)
- [ ] Iterar 2-4 rondas de "look & feel" antes de tocar GitHub Actions
- [ ] Configurar Secrets en el repo cuando tengas todas las keys
- [ ] Push del repo, primer run manual de un slot
- [ ] Validar que el email llega bien a `rosiquediego.arji@gmail.com`

---

## Bloqueantes

Ninguno por ahora. Tú estás libre para crear cuentas mientras yo trabajo en lo de mi lista.

---

## Costes corriendo Fase 2 hasta ahora

$0. Todo lo escrito hasta el momento es código y configuración local.
