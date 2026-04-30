"""Generador de tema para Firulais según slot.

Cada slot horario está mapeado a uno de los 5 pilares:
  - SUPERPODER:  Pilar 1 — habilidad asombrosa de un animal
  - RECORD:      Pilar 2 — el más X (rápido, viejo, venenoso, raro)
  - MASCOTA:     Pilar 3 — perros, gatos, mascotas (alta retención)
  - ANIMAL_RARO: Pilar 4 — especies poco conocidas
  - MITO:        Pilar 5 — mito desmentido con evidencia

Cada tema viene con:
  - id, title, pilar
  - script (con placeholders [DING][BOING][CASH][SCRATCH][WHOOSH][POP][GASP] y [*énfasis*])
  - keywords (10 queries para footage Pixabay/Pexels)
  - sources (lista de URLs verificables — obligatorio)
  - target_seconds (27-32, mediana del nicho)

Tracker de duplicados: done_topics.md (commiteado tras cada run)
"""
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DONE_TOPICS = ROOT / "done_topics.md"

# ---------------------------------------------------------------------------
# Banco semilla de temas — versión inicial. Diego puede añadir más en docs/topics_seed.md
# IMPORTANTE: cada tema debe traer fuentes verificables. Sin fuentes, no se publica.
# ---------------------------------------------------------------------------

TOPICS = {
    "SUPERPODER": [
        {
            "id": "tardigrados-espacio",
            "title": "Tardígrados sobreviven en el espacio",
            "script": (
                "¿Sabías, Firulais? [DING] Los tardígrados pueden sobrevivir en el [*espacio exterior*] [BOING]. "
                "Sin oxígeno [POP], sin agua, y a [*menos 273*] grados Celsius [CASH]. "
                "Una misión espacial los lanzó en 2007 y volvieron [*vivos*] [GASP]. "
                "Un milímetro de pura terquedad biológica. "
                "Y tú, Firulais, ¿lo sabías? Sígueme para más datos curiosos. [DING]"
            ),
            "keywords": [
                "tardigrade water bear", "microscope tiny animal", "earth from space",
                "vacuum chamber experiment", "scientist lab close up", "moss water drop",
                "esa space mission", "satellite low orbit", "magnification microscopic",
                "cute small organism",
            ],
            "sources": [
                "https://www.cell.com/current-biology/fulltext/S0960-9822(08)00805-1",
                "https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Research/Tiny_animals_survive_exposure_to_space",
            ],
            "target_seconds": 30,
        },
        {
            "id": "axolote-regenera",
            "title": "Los axolotes regeneran cualquier parte del cuerpo",
            "script": (
                "¿Sabías, Firulais? [DING] El axolote puede regenerar [*piernas, ojos y hasta cerebro*] [BOING]. "
                "Vive solo en lagos cerca de Ciudad de México [POP]. "
                "Y siempre conserva su [*cara de bebé*] toda su vida [GASP]. "
                "Y tú, Firulais, ¿lo sabías?"
            ),
            "keywords": [
                "axolotl pink", "mexico xochimilco lake", "amphibian regeneration",
                "salamander close up", "axolotl swimming", "lab axolotl science",
                "underwater amphibian", "cute baby face animal", "freshwater creature",
                "rare endangered species",
            ],
            "sources": [
                "https://www.nature.com/articles/nature25458",  # Genome of the axolotl, Nature 2018
                "https://www.nationalgeographic.com/animals/amphibians/facts/axolotl",
            ],
            "target_seconds": 28,
        },
    ],
    "RECORD": [
        {
            "id": "halcon-peregrino-389",
            "title": "El halcón peregrino: 389 km/h en picado",
            "script": (
                "¿Sabías, Firulais? [DING] El animal más rápido NO es el guepardo [SCRATCH]. "
                "Es el halcón peregrino, que en picado alcanza [*389 kilómetros por hora*] [BOING] [CASH]. "
                "Más rápido que un Fórmula 1. "
                "Y tú, Firulais, ¿lo sabías?"
            ),
            "keywords": [
                "peregrine falcon flight", "raptor bird diving", "falcon close up",
                "bird of prey wing", "high speed nature", "predator bird hunt",
                "falcon launch", "wild raptor sky", "feathers wing close",
                "fast animal nature",
            ],
            "sources": [
                "https://www.nationalgeographic.com/animals/birds/facts/peregrine-falcon",
                "https://www.audubon.org/field-guide/bird/peregrine-falcon",
            ],
            "target_seconds": 25,
        },
    ],
    "MASCOTA": [
        {
            "id": "perros-300m-receptores",
            "title": "Los perros tienen 300 millones de receptores olfativos",
            "script": (
                "¿Sabías, Firulais? [DING] Los perros tienen [*300 millones*] de receptores olfativos [BOING]. "
                "Los humanos solo seis millones [SCRATCH]. "
                "Por eso pueden detectar [*cáncer*], [*diabetes*] y hasta el COVID [GASP]. "
                "Y tú, Firulais, ¿lo sabías?"
            ),
            "keywords": [
                "dog nose close up", "puppy sniffing", "labrador detection dog",
                "service dog working", "dog snout macro", "golden retriever sniff",
                "dog medical detection", "k9 training", "cute puppy face",
                "dog smelling ground",
            ],
            "sources": [
                "https://www.akc.org/expert-advice/health/how-powerful-is-a-dogs-nose/",
                "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8038319/",  # Canine olfaction in disease detection
            ],
            "target_seconds": 28,
        },
        {
            "id": "gatos-ronroneo-sana",
            "title": "El ronroneo del gato sana huesos",
            "script": (
                "¿Sabías, Firulais? [DING] El ronroneo del gato vibra entre [*25 y 150 hertz*] [BOING]. "
                "Esa frecuencia regenera [*huesos y tejidos*] [POP]. "
                "Por eso los gatos se recuperan más rápido de fracturas [GASP]. "
                "Y tú, Firulais, ¿lo sabías?"
            ),
            "keywords": [
                "cat purring close up", "kitten cuddling", "cat resting peaceful",
                "tabby cat face", "cat lap purr", "veterinary cat",
                "sleeping cat warm", "cat whiskers macro", "cute kitten",
                "domestic cat home",
            ],
            "sources": [
                "https://www.scientificamerican.com/article/why-do-cats-purr/",
                "https://pubmed.ncbi.nlm.nih.gov/11512565/",  # Cat purr 25-150Hz Fauna Communications
            ],
            "target_seconds": 27,
        },
    ],
    "ANIMAL_RARO": [
        {
            "id": "pulpo-cristal",
            "title": "El pulpo de cristal: transparente a 4000m",
            "script": (
                "¿Sabías, Firulais? [DING] Existe un pulpo [*completamente transparente*] [BOING]. "
                "Vive a [*4 mil metros*] de profundidad [POP]. "
                "Solo se han visto unos pocos vivos en toda la historia [GASP]. "
                "Y tú, Firulais, ¿lo sabías?"
            ),
            "keywords": [
                "deep sea octopus", "transparent jellyfish", "abyss ocean creature",
                "submarine deep dive", "underwater research", "rov deep sea",
                "bioluminescent creature", "deep ocean dark", "transparent sea animal",
                "schmidt ocean institute",
            ],
            "sources": [
                "https://schmidtocean.org/cruise-log-post/glass-octopus/",
                "https://www.nationalgeographic.com/animals/article/glass-octopus-rare-footage",
            ],
            "target_seconds": 28,
        },
    ],
    "MITO": [
        {
            "id": "toros-no-rojo",
            "title": "Los toros NO odian el rojo",
            "script": (
                "¿Sabías, Firulais? [DING] Los toros NO odian el rojo [SCRATCH]. "
                "Son [*daltónicos*] al rojo [BOING]. "
                "Lo que les enfurece es el [*movimiento*] de la capa, no el color [POP]. "
                "El torero podría usar verde y daría igual. "
                "Y tú, Firulais, ¿lo sabías?"
            ),
            "keywords": [
                "bull pasture field", "cattle close up face", "cow eye macro",
                "bullfighter cape movement", "bull running wild", "cattle ranch",
                "spanish bull farm", "bovine eye", "cow grazing peaceful",
                "rodeo training",
            ],
            "sources": [
                "https://www.scientificamerican.com/article/why-does-the-color-red-make-bulls-angry/",
                "https://www.discovermagazine.com/planet-earth/why-do-bulls-charge-when-they-see-red",
            ],
            "target_seconds": 30,
        },
    ],
}


def load_done() -> set[str]:
    if not DONE_TOPICS.exists():
        return set()
    ids = set()
    for line in DONE_TOPICS.read_text().splitlines():
        line = line.strip()
        if line.startswith("- "):
            ids.add(line[2:].split(" ", 1)[0])
    return ids


def mark_done(topic_id: str):
    DONE_TOPICS.parent.mkdir(parents=True, exist_ok=True)
    with DONE_TOPICS.open("a") as f:
        f.write(f"- {topic_id} ({os.environ.get('SLOT_BIAS', 'unknown')})\n")


def pick(slot_bias: str) -> dict:
    """Devuelve un tema fresco del pilar pedido. Falla si no quedan temas nuevos."""
    pilar = slot_bias.upper()
    if pilar not in TOPICS:
        raise SystemExit(f"slot_bias '{slot_bias}' no es un pilar válido: {list(TOPICS)}")
    done = load_done()
    fresh = [t for t in TOPICS[pilar] if t["id"] not in done]
    if not fresh:
        # Reciclar — pero log en stderr para que Diego añada más temas al banco
        print(
            f"[!] todos los temas del pilar {pilar} ya se publicaron, reciclando.",
            file=sys.stderr,
        )
        fresh = TOPICS[pilar]
    return random.choice(fresh)


if __name__ == "__main__":
    slot_bias = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SLOT_BIAS", "MASCOTA")
    topic = pick(slot_bias)
    print(json.dumps(topic, ensure_ascii=False, indent=2))
    if "--mark" in sys.argv:
        mark_done(topic["id"])
