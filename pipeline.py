"""
Pipeline base de connaissance pêche Japon — v2.
Usage :
    export ANTHROPIC_API_KEY=sk-ant-...
    python pipeline.py init                                 # crée/migre la base (schema_v2.sql)
    python pipeline.py add-source                            # ajoute une source interactive
    python pipeline.py extract <source_id> <fichier.txt>     # extrait + insère les observations
    python pipeline.py review                                 # liste les observations à valider
    python pipeline.py validate <observation_id>               # marque une observation comme validée
    python pipeline.py add-lure                                # ajoute un leurre au top 10 d'une espèce
    python pipeline.py add-combo                                # ajoute un combo canne
    python pipeline.py link-combo <lure_id> <combo_id>          # rattache un leurre à un combo
    python pipeline.py export                                    # génère data.json pour la PWA
"""

import sqlite3
import json
import sys
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "peche_jp.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema_v2.sql")

SPECIES_ID_HIRAME = 1  # espèce test, cf. schema_v2.sql

EXTRACTION_PROMPT = """Tu extrais des observations de pêche factuelles depuis un texte japonais traduit ou une transcription vidéo, sur l'espèce hirame (ヒラメ), pour la période novembre / 10 premiers jours de décembre, pêche du bord uniquement.

Règles strictes :
- Une observation = un fait vérifiable et actionnable (comportement, spot, marée, leurre, moment de journée, condition d'eau)
- Paraphrase fidèle, jamais de citation mot pour mot du texte source
- N'invente rien : si l'info n'est pas dans le texte, ne crée pas d'observation ni de champ de recommandation
- Plusieurs observations distinctes par texte si le texte couvre plusieurs faits
- Ignore tout ce qui ne concerne pas hirame, la pêche du bord, ou la fenêtre nov./10 déc. (sauf comportement général du hirame toute saison, à taguer "saison:general")
- Si le texte donne une recommandation concrète (leurre à utiliser, couleur, animation, bas de ligne) pour des conditions données, remplis les champs recommended_* correspondants. Sinon laisse-les vides.
- Vocabulaire contrôlé obligatoire pour ces deux dimensions (pour que le QCM de l'app puisse matcher) :
  - couleur_eau : uniquement "claire", "trouble" ou "verte"
  - pression_atmo : uniquement "basse", "moyenne" ou "haute"

Sortie JSON stricte, un array d'objets, RIEN d'autre (pas de préambule, pas de ```json) :
[
  {{
    "raw_text": "paraphrase courte et factuelle",
    "recommended_lure": "nom du leurre conseillé, ou vide",
    "recommended_color": "couleur conseillée, ou vide",
    "recommended_animation": "animation conseillée, ou vide",
    "recommended_leader": "bas de ligne conseillé, ou vide",
    "tags": {{
      "saison": "...",
      "maree": "...",
      "moment_jour": "...",
      "spot_type": "...",
      "leurre": "...",
      "comportement": "...",
      "profondeur": "...",
      "temperature_eau": "...",
      "couleur_eau": "...",
      "pression_atmo": "..."
    }}
  }}
]

Ne remplis que les clés de tags pour lesquelles le texte donne une info explicite. Omets les autres clés (ne mets pas null). Idem pour les champs recommended_* : omets-les s'il n'y a rien d'explicite.

Texte source :
{texte}
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"Base initialisée : {DB_PATH}")


def add_source():
    print("Type de source : marque / blog / video")
    type_ = input("type: ").strip()
    weight_map = {"marque": 1.0, "blog": 0.7, "video": 0.7}
    weight = weight_map.get(type_, 0.4)
    label = input("label (nom du site/chaîne/auteur): ").strip()
    url = input("url (optionnel, vide si transcription collée): ").strip() or None
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO sources (url, type, label, weight) VALUES (?, ?, ?, ?)",
        (url, type_, label, weight),
    )
    conn.commit()
    print(f"Source créée, id = {cur.lastrowid}, poids = {weight}")
    conn.close()


def add_lure():
    conn = get_conn()
    name = input("nom du leurre: ").strip()
    type_ = input("type (jerkbait/vibration/popper/jig/metal...): ").strip()
    rank = input("rang dans le top 10 (1 = priorité max): ").strip()
    cur = conn.execute(
        "INSERT INTO lures (species_id, name, type, rank) VALUES (?, ?, ?, ?)",
        (SPECIES_ID_HIRAME, name, type_, int(rank) if rank else 99),
    )
    conn.commit()
    print(f"Leurre créé, id = {cur.lastrowid}")

    n = conn.execute(
        "SELECT COUNT(*) FROM lures WHERE species_id = ?", (SPECIES_ID_HIRAME,)
    ).fetchone()[0]
    if n > 10:
        print(f"⚠️  {n} leurres pour cette espèce — dépasse le max de 10, pense à en retirer un.")
    conn.close()


def add_combo():
    conn = get_conn()
    name = input("nom du combo (ex: SP82MH): ").strip()
    desc = input("description (ex: gros hirame / grosses conditions): ").strip()
    cur = conn.execute(
        "INSERT INTO combos (name, description) VALUES (?, ?)", (name, desc)
    )
    conn.commit()
    print(f"Combo créé, id = {cur.lastrowid}")
    conn.close()


def link_combo(lure_id, combo_id):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO lure_combo (lure_id, combo_id) VALUES (?, ?)",
        (lure_id, combo_id),
    )
    conn.commit()
    conn.close()
    print(f"Leurre {lure_id} rattaché au combo {combo_id}")


def get_or_create_tag(conn, dimension, value):
    dim_row = conn.execute(
        "SELECT id FROM tag_dimensions WHERE name = ?", (dimension,)
    ).fetchone()
    if not dim_row:
        raise ValueError(f"Dimension inconnue : {dimension}")
    dim_id = dim_row[0]
    tag_row = conn.execute(
        "SELECT id FROM tags WHERE dimension_id = ? AND value = ?", (dim_id, value)
    ).fetchone()
    if tag_row:
        return tag_row[0]
    cur = conn.execute(
        "INSERT INTO tags (dimension_id, value) VALUES (?, ?)", (dim_id, value)
    )
    return cur.lastrowid


def call_claude(texte):
    try:
        import anthropic
    except ImportError:
        sys.exit("Installe le SDK : pip install anthropic --break-system-packages")

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(texte=texte)}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[4:] if raw.startswith("json") else raw
    return json.loads(raw)


def compute_confidence(conn, species_id, source_weight, tags):
    if not tags:
        return source_weight
    conditions = []
    params = [species_id]
    for dim, val in tags.items():
        conditions.append(
            "EXISTS (SELECT 1 FROM observation_tags ot JOIN tags t ON t.id = ot.tag_id "
            "JOIN tag_dimensions td ON td.id = t.dimension_id "
            "WHERE ot.observation_id = o.id AND td.name = ? AND t.value = ?)"
        )
        params.extend([dim, val])
    query = f"""
        SELECT COUNT(DISTINCT o.source_id) FROM observations o
        WHERE o.species_id = ? AND ({" AND ".join(conditions)})
    """
    n_matching_sources = conn.execute(query, params).fetchone()[0]
    bonus = min(0.15 * n_matching_sources, 0.45)
    return min(source_weight + bonus, 1.0)


def extract(source_id, filepath):
    with open(filepath, encoding="utf-8") as f:
        texte = f.read()

    conn = get_conn()
    source_row = conn.execute(
        "SELECT weight FROM sources WHERE id = ?", (source_id,)
    ).fetchone()
    if not source_row:
        sys.exit(f"Source id {source_id} introuvable. Lance 'add-source' d'abord.")
    source_weight = source_row[0]

    observations = call_claude(texte)
    print(f"{len(observations)} observation(s) extraite(s).")

    for obs in observations:
        tags = obs.get("tags", {})
        score = compute_confidence(conn, SPECIES_ID_HIRAME, source_weight, tags)
        needs_review = 1 if score < 0.5 else 0

        cur = conn.execute(
            """INSERT INTO observations
               (species_id, source_id, raw_text, confidence_score, needs_review,
                recommended_lure, recommended_color, recommended_animation, recommended_leader)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                SPECIES_ID_HIRAME, source_id, obs["raw_text"], score, needs_review,
                obs.get("recommended_lure") or None,
                obs.get("recommended_color") or None,
                obs.get("recommended_animation") or None,
                obs.get("recommended_leader") or None,
            ),
        )
        obs_id = cur.lastrowid

        for dim, val in tags.items():
            tag_id = get_or_create_tag(conn, dim, val)
            conn.execute(
                "INSERT OR IGNORE INTO observation_tags (observation_id, tag_id) VALUES (?, ?)",
                (obs_id, tag_id),
            )

        flag = "⚠️ À VÉRIFIER" if needs_review else "✓"
        reco = " [reco]" if obs.get("recommended_lure") else ""
        print(f"  [{flag}]{reco} score={score:.2f} — {obs['raw_text'][:70]}")

    conn.commit()
    conn.close()


def review():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, raw_text, confidence_score FROM observations WHERE needs_review = 1 "
        "ORDER BY confidence_score ASC"
    ).fetchall()
    if not rows:
        print("Rien à vérifier.")
    for r in rows:
        print(f"[{r[0]}] score={r[2]:.2f} — {r[1]}")
    conn.close()


def validate(obs_id):
    conn = get_conn()
    conn.execute("UPDATE observations SET needs_review = 0 WHERE id = ?", (obs_id,))
    conn.commit()
    conn.close()
    print(f"Observation {obs_id} validée.")


def export_json():
    conn = get_conn()
    conn.row_factory = sqlite3.Row

    species_rows = conn.execute("SELECT * FROM species").fetchall()
    species_out = [dict(s) for s in species_rows]

    observations = conn.execute(
        """SELECT o.*, s.name_fr as species, src.label as source_label, src.type as source_type
           FROM observations o
           JOIN species s ON s.id = o.species_id
           JOIN sources src ON src.id = o.source_id
           WHERE o.needs_review = 0
           ORDER BY o.id"""
    ).fetchall()

    obs_out = []
    for o in observations:
        tags_rows = conn.execute(
            """SELECT td.name as dim, t.value FROM observation_tags ot
               JOIN tags t ON t.id = ot.tag_id
               JOIN tag_dimensions td ON td.id = t.dimension_id
               WHERE ot.observation_id = ?""",
            (o["id"],),
        ).fetchall()
        tags = {t["dim"]: t["value"] for t in tags_rows}
        entry = {
            "id": o["id"],
            "species_id": o["species_id"],
            "species": o["species"],
            "text": o["raw_text"],
            "confidence": round(o["confidence_score"], 2),
            "source": o["source_label"],
            "source_type": o["source_type"],
            "tags": tags,
        }
        reco = {}
        for field in ("recommended_lure", "recommended_color", "recommended_animation", "recommended_leader"):
            if o[field]:
                reco[field.replace("recommended_", "")] = o[field]
        if reco:
            entry["recommendation"] = reco
        obs_out.append(entry)

    lures_rows = conn.execute("SELECT * FROM lures ORDER BY species_id, rank").fetchall()
    lures_out = []
    for l in lures_rows:
        combo_names = [
            r["name"] for r in conn.execute(
                """SELECT c.name FROM lure_combo lc JOIN combos c ON c.id = lc.combo_id
                   WHERE lc.lure_id = ?""",
                (l["id"],),
            ).fetchall()
        ]
        lures_out.append({
            "id": l["id"], "species_id": l["species_id"], "name": l["name"],
            "type": l["type"], "rank": l["rank"], "combos": combo_names,
        })

    combos_rows = conn.execute("SELECT * FROM combos").fetchall()
    combos_out = [dict(c) for c in combos_rows]

    result = {
        "species": species_out,
        "observations": obs_out,
        "lures": lures_out,
        "combos": combos_out,
    }

    out_path = os.path.join(os.path.dirname(__file__), "data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    conn.close()
    print(f"{len(obs_out)} observation(s), {len(lures_out)} leurre(s), {len(combos_out)} combo(s) → {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "init":
        init_db()
    elif cmd == "add-source":
        add_source()
    elif cmd == "add-lure":
        add_lure()
    elif cmd == "add-combo":
        add_combo()
    elif cmd == "link-combo":
        link_combo(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "extract":
        extract(int(sys.argv[2]), sys.argv[3])
    elif cmd == "review":
        review()
    elif cmd == "validate":
        validate(int(sys.argv[2]))
    elif cmd == "export":
        export_json()
    else:
        print(__doc__)
