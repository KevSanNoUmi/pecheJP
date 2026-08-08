# Carnet Pêche JP — v3

Base de connaissance pêche Japon (scraping blogs/sites spécialisés + transcriptions
vidéos + sessions terrain), consultable en PWA installable. Outil de décision, pas
juste de consultation : conditions du moment → config sourcée.

## Nouveautés v3

- **Pipeline multi-espèces** : les 10 espèces du voyage (Hirame, Suzuki, Hamachi,
  Aori-Ika, Kurodai, Madai, Tachiuo, Saba, Aji, Mebaru). Un seul texte peut nourrir
  plusieurs fiches. Textes japonais BRUTS acceptés (pas besoin de traduire avant).
- **Score de concordance corrigé** : une source distincte confirme dès 2 tags
  partagés sur la même espèce (+0.15/source, plafonné +0.45).
- **Vocabulaire contrôlé sur les 4 dimensions du QCM** (maree, moment_jour,
  couleur_eau, pression_atmo) — imposé au LLM, vérifié à l'insertion (tag hors
  vocab = rejeté avec message).
- **Marée harmonique offline** (M2+S2+K1+O1) par port : état montante/descendante/
  étale calculé en direct, prochaines PM/BM, courbe 14h. Pré-remplit le QCM quand
  un port est activé ("Pêcher ici" sur un pad d'étape).
  ⚠️ Les constantes amp/phase dans PORTS (index.html) sont des placeholders
  plausibles : REMPLACE-les par les profils exacts de carnetjp26 (même modèle).
- **Briefings de session** : `pipeline.py brief` croise chaque étape × espèces
  ciblées × observations validées et génère un plan de session via Claude, chaque
  affirmation citant ses observations [#id]. Embarqué dans data.json, lisible
  offline sur le pad de l'étape.
- **Log terrain** : formulaire sur chaque page espèce (leurre, résultat, notes ;
  conditions reprises du dernier QCM). Stocké en localStorage, export JSON depuis
  l'accueil, réimporté via `pipeline.py import-log` comme source "terrain"
  poids 1.0 — tes prises font monter les scores par concordance.
- **Vue "Les sources divergent"** : paires d'observations aux conditions communes
  (≥2 tags) mais recommandations différentes, affichées côte à côte avec sources.

## Workflow complet

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 pipeline.py init

# Enrichissement (texte JP brut ok)
python3 pipeline.py add-source
python3 pipeline.py extract <source_id> <fichier.txt>
python3 pipeline.py review && python3 pipeline.py validate <id>

# Curation
python3 pipeline.py add-lure / add-combo / link-combo <lure_id> <combo_id>
python3 pipeline.py add-stop        # inclut la clé du port de marée

# Retour terrain (après export depuis la PWA)
python3 pipeline.py import-log sessions-terrain.json

# Briefs + publication
python3 pipeline.py brief            # API Claude, cite les obs [#id]
python3 pipeline.py export           # data.json à la racine
git add data.json && git commit -m "maj" && git push
```

## Vocabulaire contrôlé (ne pas dériver)

maree: montante/descendante/étale · moment_jour: aube/jour/crépuscule/nuit ·
couleur_eau: claire/trouble/verte · pression_atmo: basse/moyenne/haute
(pression : auto Open-Meteo <1013 basse, 1013–1020 moyenne, >1020 haute)

## Mise en ligne (première fois)

git init → push → Settings/Pages (main, /root) → tel : Partager → écran d'accueil.
