# Backups

Known-working snapshots of workflows and templates. **NEVER edit files in this folder.**

## Naming Convention

```
{version}-{label}_{date}.json
```

- `v8.0-master_2026-03-08.json` — original v8.0 before any tweaks
- `v8-Kling-loopfix_2026-03-08.json` — after adding loop/duration fix

## How to Use

1. **Before making changes:** Copy the current working file here with today's date
2. **If something breaks:** Copy the most recent backup back to the active folder
3. **Never delete backups** unless disk space is an issue

## Current Backups

| File | Description |
|---|---|
| `workflows/v6.0.2-master_2026-03-08.json` | Legacy v6 workflow (reference only) |
| `workflows/v7.2-master_2026-03-08.json` | v7.2 production workflow (Ken Burns) |
| `workflows/v8.0-master_2026-03-08.json` | v8.0 original (before loop fix) |
| `templates/v8-Kling-master_2026-03-08.json` | v8 template original (no loop) |
| `templates/v8-Kling-loopfix_2026-03-08.json` | v8 template with loop: -1, duration: -2 |
