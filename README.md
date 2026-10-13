# PDNA Housing V5 MULTIMODULE — SVG

A separate test dashboard for the Housing V5 Kobo project. It does not modify Housing V4 or the existing Summary project.

## Deployment

1. Create a new GitHub repository, e.g. `pdna-housing-v5-dashboard`.
2. Upload `app.py`, `requirements.txt`, and `README.md` to the repository root.
3. Deploy `app.py` from Streamlit Community Cloud.
4. In **App settings → Secrets**, add:

```toml
KOBO_SERVER = "https://kf.kobotoolbox.org"
KOBO_ASSET_UID = "aZJD8nNAfmc576q6HgK3VJ"
KOBO_API_TOKEN = "YOUR_PRIVATE_KOBO_API_TOKEN"
```

Never put your actual API token in GitHub or send it in screenshots.

## Data rules

- Each parent submission is counted once for total damage, losses and impact.
- Reads `summary_damage`, `summary_losses`, `summary_impact` when present, with fallback to `direct_damage`, `total_losses`, `total_impact` for historical records.
- Repeat module rows are shown separately and **never added a second time** to totals.
- Different Kobo versions may expose different field names or repeat paths. Validate with the live API after deployment.
- The export used for initial review contained 11 parent assessments and 3 module rows, but live counts can change.
- Kobo data cache lasts up to five minutes; use the Refresh button to clear it.
