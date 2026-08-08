# Carnet Pêche JP

Base de connaissance pêche Japon (scraping blogs/sites spécialisés + transcriptions
vidéos), consultable en PWA installable sur téléphone.

## Structure

- `index.html`, `manifest.json`, `sw.js`, `data.json`, `icon-*.png`, `apple-touch-icon.png`
  → l'app (PWA, hébergée sur GitHub Pages)
- `pipeline.py`, `schema.sql`
  → pipeline local d'extraction (texte/transcription → SQLite → data.json)
- `peche_jp.db`
  → base de travail locale, **jamais versionnée** (voir `.gitignore`)

## Accueil — 3 sections

1. **Où je pêche** — pads par ville/étape du voyage (dates + espèces ciblées, tap pour déplier)
2. **Espèces** — pads par espèce → page dédiée (comportement, où/quand, top leurres, QCM)
3. **Combos** — pads par combo canne → tap pour voir quels leurres/espèces s'y rattachent

## QCM — vocabulaire contrôlé

Pour que le QCM de la page espèce puisse matcher les recommandations aux
conditions du moment, deux dimensions utilisent un vocabulaire fixe (imposé au
LLM dans le prompt d'extraction) :
- `couleur_eau` : claire / trouble / verte
- `pression_atmo` : basse / moyenne / haute (bucket auto : <1013 basse, 1013–1020
  moyenne, >1020 haute — relevé via Open-Meteo, gratuit et sans clé, géolocalisé
  côté navigateur ; secours manuel si hors réseau)

## Workflow d'enrichissement

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# Sources et observations
python3 pipeline.py add-source
python3 pipeline.py extract <source_id> <fichier.txt>
python3 pipeline.py review
python3 pipeline.py validate <observation_id>

# Leurres et combos (curation manuelle, max 10 leurres/espèce)
python3 pipeline.py add-lure
python3 pipeline.py add-combo
python3 pipeline.py link-combo <lure_id> <combo_id>

# Étapes du voyage (section "Où je pêche" de l'accueil)
python3 pipeline.py add-stop

# Export + mise à jour de l'app
python3 pipeline.py export        # régénère data.json directement à la racine
git add data.json
git commit -m "Ajout observations — <source>"
git push
```

## Mise en ligne (première fois)

1. Crée le repo sur GitHub (public, sans README auto-généré)
2. `python3 pipeline.py init` pour créer `peche_jp.db` en local
3. `git init && git add . && git commit -m "Init carnet pêche JP"`
4. `git remote add origin <url-du-repo> && git push -u origin main`
5. Settings → Pages → Source: branche `main`, dossier `/root`
6. Sur le tel : ouvrir l'URL → Partager → "Sur l'écran d'accueil"
