# Carnet Pêche JP

Base de connaissance pêche Japon, construite à partir de scraping de blogs/sites
japonais spécialisés et de transcriptions de vidéos, consultable en PWA installable
sur téléphone.

## Structure

- `index.html`, `manifest.json`, `sw.js`, `data.json`, `icon-*.png`, `apple-touch-icon.png`
  → l'app (PWA, hébergée sur GitHub Pages)
- `pipeline.py`, `schema.sql`
  → le pipeline local d'extraction (texte/transcription → SQLite → JSON)
- `peche_jp.db`
  → base de travail locale, **jamais versionnée** (voir `.gitignore`)

## Workflow d'enrichissement

```bash
# 1. Première fois seulement
python3 pipeline.py init
python3 pipeline.py add-source

# 2. À chaque nouvelle source (texte scrapé ou transcription collée)
export ANTHROPIC_API_KEY=sk-ant-...
python3 pipeline.py extract <source_id> <fichier.txt>
python3 pipeline.py review
python3 pipeline.py validate <observation_id>   # pour chaque obs à valider
python3 pipeline.py export                        # génère peche_jp_export.json

# 3. Mise à jour de l'app
cp peche_jp_export.json data.json
git add data.json
git commit -m "Ajout observations — <source>"
git push
```

GitHub Pages redéploie automatiquement. Le service worker force le rechargement
réseau de `data.json` à chaque ouverture, donc le tel a toujours la dernière version.

## Mise en ligne (première fois)

1. Crée le repo sur GitHub (public, sans README auto-généré)
2. `git init && git add . && git commit -m "Init carnet pêche JP"`
3. `git remote add origin <url-du-repo> && git push -u origin main`
4. Settings → Pages → Source: branche `main`, dossier `/root`
5. Sur le tel : ouvrir l'URL → Partager → "Sur l'écran d'accueil"
