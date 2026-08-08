-- Schéma base de connaissance pêche Japon
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

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    species_id INTEGER NOT NULL REFERENCES species(id),
    source_id INTEGER NOT NULL REFERENCES sources(id),
    raw_text TEXT NOT NULL,
    confidence_score REAL DEFAULT 0,
    needs_review INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS observation_tags (
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (observation_id, tag_id)
);

-- Seed des dimensions de tags
INSERT OR IGNORE INTO tag_dimensions (name) VALUES
    ('saison'), ('maree'), ('moment_jour'), ('spot_type'),
    ('leurre'), ('comportement'), ('profondeur'), ('temperature_eau');

-- Seed espèce test
INSERT OR IGNORE INTO species (id, name_jp, name_fr, name_latin)
    VALUES (1, 'ヒラメ', 'Hirame (limande japonaise)', 'Paralichthys olivaceus');
