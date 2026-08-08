-- Schéma base de connaissance pêche Japon — v3
-- Multi-espèces, briefs de session, sources terrain

CREATE TABLE IF NOT EXISTS species (
    id INTEGER PRIMARY KEY,
    name_jp TEXT NOT NULL,
    name_fr TEXT NOT NULL,
    name_latin TEXT,
    aliases TEXT              -- autres noms possibles, séparés par virgules (pour le matching extraction)
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    url TEXT,
    type TEXT NOT NULL CHECK(type IN ('marque','blog','video','terrain')),
    label TEXT NOT NULL,
    weight REAL NOT NULL      -- marque 1.0 / blog 0.7 / video 0.7 / terrain 1.0 / inconnu 0.4
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
    recommended_lure TEXT,
    recommended_color TEXT,
    recommended_animation TEXT,
    recommended_leader TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS observation_tags (
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (observation_id, tag_id)
);

CREATE TABLE IF NOT EXISTS lures (
    id INTEGER PRIMARY KEY,
    species_id INTEGER NOT NULL REFERENCES species(id),
    name TEXT NOT NULL,
    type TEXT,
    rank INTEGER DEFAULT 99
);

CREATE TABLE IF NOT EXISTS combos (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS lure_combo (
    lure_id INTEGER NOT NULL REFERENCES lures(id),
    combo_id INTEGER NOT NULL REFERENCES combos(id),
    PRIMARY KEY (lure_id, combo_id)
);

CREATE TABLE IF NOT EXISTS trip_stops (
    id INTEGER PRIMARY KEY,
    city TEXT NOT NULL,
    dates TEXT NOT NULL,
    target_species TEXT,       -- texte libre, séparé par virgules
    port TEXT                  -- clé du profil de marée dans PORTS (côté app), ex: "numazu"
);

CREATE TABLE IF NOT EXISTS trip_briefs (
    stop_id INTEGER PRIMARY KEY REFERENCES trip_stops(id),
    text TEXT NOT NULL,
    generated_at TEXT DEFAULT (datetime('now'))
);

-- Dimensions de tags
INSERT OR IGNORE INTO tag_dimensions (name) VALUES
    ('saison'), ('maree'), ('moment_jour'), ('spot_type'),
    ('leurre'), ('comportement'), ('profondeur'), ('temperature_eau'),
    ('couleur_eau'), ('pression_atmo');

-- Les 10 espèces ciblées du voyage
INSERT OR IGNORE INTO species (id, name_jp, name_fr, name_latin, aliases) VALUES
    (1,  'ヒラメ',   'Hirame',   'Paralichthys olivaceus', 'hirame,limande japonaise,flatfish,flounder'),
    (2,  'スズキ',   'Suzuki',   'Lateolabrax japonicus',  'suzuki,seabass,シーバス,bar japonais,fukko,seigo'),
    (3,  'ハマチ',   'Hamachi',  'Seriola quinqueradiata', 'hamachi,buri,ブリ,inada,warasa,yellowtail,sériole'),
    (4,  'アオリイカ','Aori-Ika', 'Sepioteuthis lessoniana','aori,aori-ika,アオリ,calamar,eging,squid'),
    (5,  'クロダイ', 'Kurodai',  'Acanthopagrus schlegelii','kurodai,chinu,チヌ,dorade noire,black seabream'),
    (6,  'マダイ',   'Madai',    'Pagrus major',           'madai,tai,真鯛,dorade royale japonaise,red seabream'),
    (7,  'タチウオ', 'Tachiuo',  'Trichiurus lepturus',    'tachiuo,太刀魚,sabre,hairtail,poisson sabre'),
    (8,  'サバ',     'Saba',     'Scomber japonicus',      'saba,maquereau,mackerel'),
    (9,  'アジ',     'Aji',      'Trachurus japonicus',    'aji,chinchard,ajing,horse mackerel'),
    (10, 'メバル',   'Mebaru',   'Sebastes inermis',       'mebaru,rockfish,mebaring,sébaste');
