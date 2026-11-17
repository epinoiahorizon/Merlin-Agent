# catalog-data

Committed snapshots of the Capabilities catalogs the desktop app fetches
(`skills.json`, `plugins.json`, plus their sidecars).

## Why these are committed

The build generates them into `website/static/api/`, which is gitignored, and the
docs deployment never published that directory — so `https://withmerlin.online/docs/api/*.json`
returns 404 and the Capabilities tab has no source. Committing the snapshot gives the
app a reachable origin today:

```
https://raw.githubusercontent.com/epinoiahorizon/Merlin-Agent/main/catalog-data/<kind>.json
```

`apps/desktop/src/app/capabilities/catalog/catalog-data.ts` lists that URL first and keeps
the site URLs behind it, so moving to a proper `/docs/api/` later needs no code change.

## Regenerating

```bash
py website/scripts/extract-plugins.py
py website/scripts/extract-skills.py
cp website/static/api/{skills,plugins,skills-meta,plugins-meta,plugin-catalog}.json catalog-data/
```

The `py` launcher is the interpreter that carries `ruamel.yaml` on Windows; `prebuild.mjs`
resolves it automatically.

These files are generated — do not hand-edit them. Regenerate and commit the diff.
