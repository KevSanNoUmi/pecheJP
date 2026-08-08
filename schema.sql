-- Schéma base de connaissance pêche Japon — v2
-- Une observation = un fait unique, lié à une source, jamais fusionné avec d'autres

CREATE TABLE IF NOT EXISTS species (
    id INTEGER PRIMARY KEY,
    name_jp TEXT NOT NULL,
    name_fr TEXT NOT NULL,
    name_latin TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    url TEXT,
    type TEXT NOT NULL CHECK(type IN ('marque','blog','video')),
    label TEXT NOT NULL,
    weight REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tag_dimensions (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    dimension_id INTEGER NOT NULL REFERENCES tag_dimensions(id),
    value TEXT NOT NULL,
    UNIQUE(dimension_id, value)
);

-- Une observation peut être un simple fait de comportement (recommended_* = NULL)
-- ou une observation-recommandation (couleur/animation/bas de ligne conseillés
-- pour des conditions données, tracés vers une source comme toute observation).
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    species_id INTEGER NOT NULL REFERENCES species(id),
    source_id INTEGER NOT NULL REFERENCES sources(id),
    raw_text TEXT NOT NULL,
    confidence_score REAL DEFAULT 0,
    needs_review INTEGER DEFAULT 1,
    recommended_lure TEXT,       -- nom du leurre conseillé (texte libre, rapproché des lures.name à l'affichage)
    recommended_color TEXT,
    recommended_animation TEXT,
    recommended_leader TEXT,     -- bas de ligne
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS observation_tags (
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (observation_id, tag_id)
);

-- Leurres curés manuellement, max 10 par espèce (pas de contrainte SQL, à respecter en saisie)
CREATE TABLE IF NOT EXISTS lures (
    id INTEGER PRIMARY KEY,
    species_id INTEGER NOT NULL REFERENCES species(id),
    name TEXT NOT NULL,
    type TEXT,                   -- jerkbait / vibration / popper / jig / metal...
    rank INTEGER DEFAULT 99      -- position dans le top 10, 1 = priorité max
);

CREATE TABLE IF NOT EXISTS combos (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,   -- ex: "SP82MH"
    description TEXT             -- ex: "gros hirame / grosses conditions"
);

CREATE TABLE IF NOT EXISTS lure_combo (
    lure_id INTEGER NOT NULL REFERENCES lures(id),
    combo_id INTEGER NOT NULL REFERENCES combos(id),
    PRIMARY KEY (lure_id, combo_id)
);

-- Seed des dimensions de tags (v2 : + couleur_eau, pression_atmo pour le QCM)
INSERT OR IGNORE INTO tag_dimensions (name) VALUES
    ('saison'), ('maree'), ('moment_jour'), ('spot_type'),
    ('leurre'), ('comportement'), ('profondeur'), ('temperature_eau'),
    ('couleur_eau'), ('pression_atmo');

-- Seed espèce test
INSERT OR IGNORE INTO species (id, name_jp, name_fr, name_latin)
    VALUES (1, 'ヒラメ', 'Hirame (limande japonaise)', 'Paralichthys olivaceus');
