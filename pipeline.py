"""
Pipeline base de connaissance pêche Japon — v3.
Usage :
    export ANTHROPIC_API_KEY=sk-ant-...
    python pipeline.py init                                # crée/migre la base (schema.sql)
    python pipeline.py add-source                           # ajoute une source
    python pipeline.py extract <source_id> <fichier.txt>    # extraction multi-espèces (texte JP brut accepté)
    python pipeline.py review                                # observations à valider
    python pipeline.py validate <observation_id>              # valide une observation
    python pipeline.py add-lure                                # leurre (top 10 par espèce)
    python pipeline.py add-combo                                # combo canne
    python pipeline.py link-combo <lure_id> <combo_id>
    python pipeline.py add-stop                                  # étape du voyage (+ port de marée)
    python pipeline.py brief                                      # génère les briefs de session (API Claude)
    python pipeline.py import-log <sessions.json>                  # importe un log terrain exporté depuis la PWA
    python pipeline.py export                                       # génère data.json
"""

import sqlite3
import json
import sys
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "peche_jp.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

# Vocabulaire contrôlé — DOIT rester identique aux options du QCM côté app
VOCAB = {
    "maree": ["montante", "descendante", "étale"],
    "moment_jour": ["aube", "jour", "crépuscule", "nuit"],
    "couleur_eau": ["claire", "trouble", "verte"],
    "pression_atmo": ["basse", "moyenne", "haute"],
}

EXTRACTION_PROMPT = """Tu extrais des observations de pêche factuelles depuis un texte japonais (brut, non traduit — tu lis le japonais directement) ou une transcription vidéo. Contexte : pêche du bord au Japon, période novembre / 10 premiers jours de décembre.

Espèces reconnues (utilise EXACTEMENT ces noms dans le champ "species") :
hirame (ヒラメ), suzuki (スズキ/シーバス), hamachi (ハマチ/ブリ/イナダ/ワラサ), aori-ika (アオリイカ), kurodai (クロダイ/チヌ), madai (マダイ), tachiuo (タチウオ), saba (サバ), aji (アジ), mebaru (メバル)

Règles strictes :
- Une observation = un fait vérifiable et actionnable, rattaché à UNE espèce
- Un même texte peut produire des observations pour plusieurs espèces différentes
- Paraphrase fidèle en français, jamais de citation mot pour mot du texte source
- N'invente rien : si l'info n'est pas dans le texte, ne crée ni observation ni champ de recommandation
- Ignore ce qui ne concerne pas la pêche du bord ou une espèce de la liste
- Comportement général toute saison → tag "saison": "general"
- Si le texte donne une recommandation concrète (leurre, couleur, animation, bas de ligne) pour des conditions données, remplis les champs recommended_*. Sinon omets-les.
- Conserve les termes techniques japonais intraduisibles entre parenthèses dans la paraphrase (ex: "courant de retour (離岸流)", "veine de courant (ヨレ)", "rupture de fond (ブレイク)")

Vocabulaire contrôlé OBLIGATOIRE pour ces 4 dimensions (le QCM de l'app matche dessus) :
- maree : uniquement "montante", "descendante" ou "étale"
- moment_jour : uniquement "aube", "jour", "crépuscule" ou "nuit"
- couleur_eau : uniquement "claire", "trouble" ou "verte"
- pression_atmo : uniquement "basse", "moyenne" ou "haute"
Si le texte dit "marée haute" ou "満潮", interprète selon le contexte (montée → "montante", renverse → "étale"). Si ambigu, omets le tag plutôt que d'inventer.

Sortie JSON stricte, un array d'objets, RIEN d'autre (pas de préambule, pas de ```json) :
[
  {{
    "species": "hirame",
    "raw_text": "paraphrase courte et factuelle",
    "recommended_lure": "…",
    "recommended_color": "…",
    "recommended_animation": "…",
    "recommended_leader": "…",
    "tags": {{
      "saison": "…", "maree": "…", "moment_jour": "…", "spot_type": "…",
      "leurre": "…", "comportement": "…", "profondeur": "…",
      "temperature_eau": "…", "couleur_eau": "…", "pression_atmo": "…"
    }}
  }}
]

Ne remplis que les clés pour lesquelles le texte donne une info explicite. Omets les autres (pas de null).

Texte source :
{texte}
"""

BRIEF_PROMPT = """Tu es un guide de pêche technique. Rédige un briefing de session concis (8-12 lignes max) pour cette étape, en te basant EXCLUSIVEMENT sur les observations fournies ci-dessous. Chaque affirmation doit citer ses observations sources entre crochets [#id].

Règles :
- N'affirme RIEN qui ne soit pas dans les observations. S'il manque une info (ex: aucune donnée marée pour une espèce), dis-le explicitement.
- Structure : par espèce ciblée. Pour chaque espèce : fenêtre horaire/marée, type de spot à chercher, leurre + animation + couleur si disponibles, bas de ligne si disponible.
- Ton direct, technique, pas de remplissage. Français, termes japonais techniques conservés.
- Si deux observations divergent, mentionne les deux options avec leurs sources.

Étape : {city} ({dates})
Espèces ciblées : {species}

Observations validées disponibles :
{observations}
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


def species_map(conn):
    """slug -> id. Le slug est le name_fr en minuscules; les aliases matchent aussi."""
    m = {}
    for sid, name_fr, aliases in conn.execute("SELECT id, name_fr, aliases FROM species"):
        m[name_fr.strip().lower()] = sid
        for a in (aliases or "").split(","):
            a = a.strip().lower()
            if a:
                m[a] = sid
    return m


def add_source():
    print("Type de source : marque / blog / video / terrain")
    type_ = input("type: ").strip()
    weight_map = {"marque": 1.0, "blog": 0.7, "video": 0.7, "terrain": 1.0}
    weight = weight_map.get(type_, 0.4)
    label = input("label (nom du site/chaîne/auteur): ").strip()
    url = input("url (optionnel): ").strip() or None
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
    smap = {r[1]: r[0] for r in conn.execute("SELECT id, name_fr FROM species")}
    print("Espèces :", ", ".join(f"{v}={k}" for k, v in smap.items()))
    sp_id = int(input("id espèce: ").strip())
    name = input("nom du leurre: ").strip()
    type_ = input("type (jerkbait/vibration/popper/jig/metal/egi...): ").strip()
    rank = input("rang dans le top 10 (1 = priorité max): ").strip()
    cur = conn.execute(
        "INSERT INTO lures (species_id, name, type, rank) VALUES (?, ?, ?, ?)",
        (sp_id, name, type_, int(rank) if rank else 99),
    )
    conn.commit()
    print(f"Leurre créé, id = {cur.lastrowid}")
    n = conn.execute("SELECT COUNT(*) FROM lures WHERE species_id = ?", (sp_id,)).fetchone()[0]
    if n > 10:
        print(f"⚠️  {n} leurres pour cette espèce — dépasse le max de 10.")
    conn.close()


def add_combo():
    conn = get_conn()
    name = input("nom du combo (ex: SP82MH): ").strip()
    desc = input("description (ex: gros hirame / grosses conditions): ").strip()
    cur = conn.execute("INSERT INTO combos (name, description) VALUES (?, ?)", (name, desc))
    conn.commit()
    print(f"Combo créé, id = {cur.lastrowid}")
    conn.close()


def add_stop():
    conn = get_conn()
    city = input("ville / spot (ex: Numazu / Izu): ").strip()
    dates = input("dates (ex: 29-30 nov): ").strip()
    species = input("espèces ciblées, séparées par des virgules: ").strip()
    port = input("clé du port de marée (fukuoka/itoshima/kobe/irago/numazu/kashima, vide si aucun): ").strip() or None
    cur = conn.execute(
        "INSERT INTO trip_stops (city, dates, target_species, port) VALUES (?, ?, ?, ?)",
        (city, dates, species, port),
    )
    conn.commit()
    print(f"Étape créée, id = {cur.lastrowid}")
    conn.close()


def link_combo(lure_id, combo_id):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO lure_combo (lure_id, combo_id) VALUES (?, ?)", (lure_id, combo_id))
    conn.commit()
    conn.close()
    print(f"Leurre {lure_id} rattaché au combo {combo_id}")


def get_or_create_tag(conn, dimension, value):
    dim_row = conn.execute("SELECT id FROM tag_dimensions WHERE name = ?", (dimension,)).fetchone()
    if not dim_row:
        raise ValueError(f"Dimension inconnue : {dimension}")
    dim_id = dim_row[0]
    value = value.strip().lower()
    if dimension in VOCAB and value not in VOCAB[dimension]:
        raise ValueError(f"Valeur '{value}' hors vocabulaire pour {dimension} (attendu: {VOCAB[dimension]})")
    row = conn.execute("SELECT id FROM tags WHERE dimension_id = ? AND value = ?", (dim_id, value)).fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO tags (dimension_id, value) VALUES (?, ?)", (dim_id, value))
    return cur.lastrowid


def call_claude(prompt, max_tokens=4000):
    try:
        import anthropic
    except ImportError:
        sys.exit("Installe le SDK : pip install anthropic --break-system-packages")
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def parse_json_response(raw):
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[4:] if raw.startswith("json") else raw
    return json.loads(raw)


def compute_confidence(conn, species_id, source_id, source_weight, tags):
    """Concordance : une source distincte confirme si elle a une observation
    sur la même espèce partageant AU MOINS 2 tags avec la nouvelle observation."""
    if len(tags) < 2:
        return min(source_weight, 1.0)

    tag_conditions = []
    params = []
    for dim, val in tags.items():
        tag_conditions.append("(td.name = ? AND t.value = ?)")
        params.extend([dim, val.strip().lower()])

    query = f"""
        SELECT o.source_id, COUNT(*) as shared
        FROM observations o
        JOIN observation_tags ot ON ot.observation_id = o.id
        JOIN tags t ON t.id = ot.tag_id
        JOIN tag_dimensions td ON td.id = t.dimension_id
        WHERE o.species_id = ? AND o.source_id != ?
          AND ({" OR ".join(tag_conditions)})
        GROUP BY o.id
        HAVING shared >= 2
    """
    rows = conn.execute(query, [species_id, source_id] + params).fetchall()
    concordant_sources = len({r[0] for r in rows})
    bonus = min(0.15 * concordant_sources, 0.45)
    return min(source_weight + bonus, 1.0)


def insert_observation(conn, species_id, source_id, source_weight, obs):
    tags = {k: v for k, v in obs.get("tags", {}).items() if v}
    score = compute_confidence(conn, species_id, source_id, source_weight, tags)
    needs_review = 1 if score < 0.5 else 0
    cur = conn.execute(
        """INSERT INTO observations
           (species_id, source_id, raw_text, confidence_score, needs_review,
            recommended_lure, recommended_color, recommended_animation, recommended_leader)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (species_id, source_id, obs["raw_text"], score, needs_review,
         obs.get("recommended_lure") or None, obs.get("recommended_color") or None,
         obs.get("recommended_animation") or None, obs.get("recommended_leader") or None),
    )
    obs_id = cur.lastrowid
    skipped = []
    for dim, val in tags.items():
        try:
            tag_id = get_or_create_tag(conn, dim, val)
        except ValueError as e:
            skipped.append(str(e))
            continue
        conn.execute("INSERT OR IGNORE INTO observation_tags (observation_id, tag_id) VALUES (?, ?)", (obs_id, tag_id))
    return obs_id, score, needs_review, skipped


def extract(source_id, filepath):
    with open(filepath, encoding="utf-8") as f:
        texte = f.read()

    conn = get_conn()
    src = conn.execute("SELECT weight FROM sources WHERE id = ?", (source_id,)).fetchone()
    if not src:
        sys.exit(f"Source id {source_id} introuvable. Lance 'add-source' d'abord.")
    source_weight = src[0]
    smap = species_map(conn)

    observations = parse_json_response(call_claude(EXTRACTION_PROMPT.format(texte=texte)))
    print(f"{len(observations)} observation(s) extraite(s).")

    for obs in observations:
        sp_key = (obs.get("species") or "").strip().lower()
        species_id = smap.get(sp_key)
        if not species_id:
            print(f"  [IGNORÉ] espèce inconnue '{sp_key}' — {obs.get('raw_text','')[:60]}")
            continue
        obs_id, score, needs_review, skipped = insert_observation(conn, species_id, source_id, source_weight, obs)
        flag = "⚠️ À VÉRIFIER" if needs_review else "✓"
        reco = " [reco]" if obs.get("recommended_lure") else ""
        print(f"  [{flag}]{reco} #{obs_id} {sp_key} score={score:.2f} — {obs['raw_text'][:60]}")
        for s in skipped:
            print(f"      tag ignoré: {s}")

    conn.commit()
    conn.close()


def import_log(filepath):
    """Importe un log de sessions terrain exporté depuis la PWA.
    Format attendu : [{"date","species","conditions":{dim:val},"lure","result","notes"}]"""
    with open(filepath, encoding="utf-8") as f:
        sessions = json.load(f)

    conn = get_conn()
    smap = species_map(conn)

    src = conn.execute("SELECT id FROM sources WHERE type='terrain' AND label='Sessions terrain (PWA)'").fetchone()
    if src:
        source_id = src[0]
    else:
        cur = conn.execute(
            "INSERT INTO sources (url, type, label, weight) VALUES (NULL, 'terrain', 'Sessions terrain (PWA)', 1.0)")
        source_id = cur.lastrowid

    imported = 0
    for s in sessions:
        sp_key = (s.get("species") or "").strip().lower()
        species_id = smap.get(sp_key)
        if not species_id:
            print(f"  [IGNORÉ] espèce inconnue '{sp_key}'")
            continue
        result = s.get("result", "rien")
        lure = s.get("lure", "")
        conds = s.get("conditions", {})
        if result == "rien":
            txt = f"Session sans touche ({s.get('date','?')}) au {lure} — conditions notées, à recouper"
        else:
            txt = f"Prise confirmée ({result}, {s.get('date','?')}) au {lure}"
            if s.get("notes"):
                txt += f" — {s['notes']}"
        obs = {"raw_text": txt, "recommended_lure": lure if result != "rien" else None, "tags": conds}
        obs_id, score, needs_review, skipped = insert_observation(conn, species_id, source_id, 1.0, obs)
        imported += 1
        print(f"  ✓ #{obs_id} {sp_key} score={score:.2f} — {txt[:70]}")

    conn.commit()
    conn.close()
    print(f"{imported} session(s) importée(s) comme observations terrain.")


def brief():
    """Génère un briefing de session par étape, à partir des observations validées."""
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    smap = species_map(conn)
    stops = conn.execute("SELECT * FROM trip_stops ORDER BY id").fetchall()
    if not stops:
        sys.exit("Aucune étape — lance add-stop d'abord.")

    for stop in stops:
        target = [x.strip() for x in (stop["target_species"] or "").split(",") if x.strip()]
        sp_ids = [smap.get(t.lower()) for t in target]
        sp_ids = [x for x in sp_ids if x]
        if not sp_ids:
            print(f"[{stop['city']}] aucune espèce reconnue, brief sauté.")
            continue

        placeholders = ",".join("?" * len(sp_ids))
        obs = conn.execute(
            f"""SELECT o.id, s.name_fr, o.raw_text, o.confidence_score,
                       o.recommended_lure, o.recommended_color, o.recommended_animation, o.recommended_leader,
                       src.label
                FROM observations o
                JOIN species s ON s.id = o.species_id
                JOIN sources src ON src.id = o.source_id
                WHERE o.needs_review = 0 AND o.species_id IN ({placeholders})
                ORDER BY o.species_id, o.confidence_score DESC""",
            sp_ids,
        ).fetchall()

        if not obs:
            print(f"[{stop['city']}] aucune observation validée pour {target}, brief sauté.")
            continue

        obs_txt = "\n".join(
            f"[#{o['id']}] ({o['name_fr']}, conf {o['confidence_score']:.2f}, src: {o['label']}) {o['raw_text']}"
            + (f" | reco: {o['recommended_lure'] or ''} {o['recommended_color'] or ''} {o['recommended_animation'] or ''} {o['recommended_leader'] or ''}".rstrip()
               if o['recommended_lure'] else "")
            for o in obs
        )
        text = call_claude(BRIEF_PROMPT.format(
            city=stop["city"], dates=stop["dates"], species=", ".join(target), observations=obs_txt
        ), max_tokens=1500)

        conn.execute(
            "INSERT INTO trip_briefs (stop_id, text) VALUES (?, ?) "
            "ON CONFLICT(stop_id) DO UPDATE SET text=excluded.text, generated_at=datetime('now')",
            (stop["id"], text),
        )
        conn.commit()
        print(f"[{stop['city']}] brief généré ({len(obs)} obs).")

    conn.close()


def review():
    conn = get_conn()
    rows = conn.execute(
        """SELECT o.id, s.name_fr, o.raw_text, o.confidence_score
           FROM observations o JOIN species s ON s.id = o.species_id
           WHERE o.needs_review = 1 ORDER BY o.confidence_score ASC"""
    ).fetchall()
    if not rows:
        print("Rien à vérifier.")
    for r in rows:
        print(f"[{r[0]}] {r[1]} score={r[3]:.2f} — {r[2]}")
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

    species_out = [dict(s) for s in conn.execute("SELECT id, name_jp, name_fr, name_latin FROM species")]

    obs_out = []
    for o in conn.execute(
        """SELECT o.*, s.name_fr as species, src.label as source_label, src.type as source_type
           FROM observations o JOIN species s ON s.id = o.species_id
           JOIN sources src ON src.id = o.source_id
           WHERE o.needs_review = 0 ORDER BY o.id"""
    ).fetchall():
        tags = {t["dim"]: t["value"] for t in conn.execute(
            """SELECT td.name as dim, t.value FROM observation_tags ot
               JOIN tags t ON t.id = ot.tag_id JOIN tag_dimensions td ON td.id = t.dimension_id
               WHERE ot.observation_id = ?""", (o["id"],))}
        entry = {
            "id": o["id"], "species_id": o["species_id"], "species": o["species"],
            "text": o["raw_text"], "confidence": round(o["confidence_score"], 2),
            "source": o["source_label"], "source_type": o["source_type"], "tags": tags,
        }
        reco = {f.replace("recommended_", ""): o[f]
                for f in ("recommended_lure", "recommended_color", "recommended_animation", "recommended_leader")
                if o[f]}
        if reco:
            entry["recommendation"] = reco
        obs_out.append(entry)

    lures_out = []
    for l in conn.execute("SELECT * FROM lures ORDER BY species_id, rank"):
        combo_names = [r["name"] for r in conn.execute(
            "SELECT c.name FROM lure_combo lc JOIN combos c ON c.id = lc.combo_id WHERE lc.lure_id = ?", (l["id"],))]
        lures_out.append({"id": l["id"], "species_id": l["species_id"], "name": l["name"],
                          "type": l["type"], "rank": l["rank"], "combos": combo_names})

    combos_out = [dict(c) for c in conn.execute("SELECT * FROM combos")]

    briefs = {b["stop_id"]: b["text"] for b in conn.execute("SELECT * FROM trip_briefs")}
    stops_out = []
    for s in conn.execute("SELECT * FROM trip_stops ORDER BY id"):
        stops_out.append({
            "id": s["id"], "city": s["city"], "dates": s["dates"], "port": s["port"],
            "target_species": [x.strip() for x in (s["target_species"] or "").split(",") if x.strip()],
            "brief": briefs.get(s["id"]),
        })

    result = {"species": species_out, "observations": obs_out, "lures": lures_out,
              "combos": combos_out, "trip_stops": stops_out}

    out_path = os.path.join(os.path.dirname(__file__), "data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    conn.close()
    print(f"{len(obs_out)} obs, {len(lures_out)} leurres, {len(combos_out)} combos, "
          f"{len(stops_out)} étapes ({sum(1 for s in stops_out if s['brief'])} briefées) → {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    dispatch = {
        "init": init_db, "add-source": add_source, "add-lure": add_lure,
        "add-combo": add_combo, "add-stop": add_stop, "review": review,
        "brief": brief, "export": export_json,
    }
    if cmd in dispatch:
        dispatch[cmd]()
    elif cmd == "extract":
        extract(int(sys.argv[2]), sys.argv[3])
    elif cmd == "validate":
        validate(int(sys.argv[2]))
    elif cmd == "link-combo":
        link_combo(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "import-log":
        import_log(sys.argv[2])
    else:
        print(__doc__)
