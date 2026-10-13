# ORBIO website

Static site, built and published by GitHub Actions to GitHub Pages. No Render, no server.
Every push to `main`, and every dataset update, rebuilds the site from the data.

## Layout

    site/                     the site source (what you edit for design and copy)
      index.html              Project · Technology · Team, one file
      assets/                 mascot.webp, flowchart.png
      experiment/             the interactive virtual experiment (iframed into the Technology page)
        js/data-loader.js     loads experiment/data/*.json, then starts app.js
    (no data/ here)           the dataset is read from the private repo named in DATA_REPO,
                              laid out as run_metadata.json + outputs/omics/<folder>/gravity_contrast.csv
    scripts/build_site.py     turns site/ + data/ into _site/
    .github/workflows/pages.yml

The experiment page no longer carries its data inline. The build writes
`experiment/data/omics.json`, `run_metadata.json` and `build_info.json`, and the page loads them.

**What gets published.** The build publishes only the fields the page displays (see
`PUBLIC_METADATA` in `scripts/build_site.py`): field grid size, maximum agents, O₂/glucose
diffusivities and thresholds, the starting-agent range, the pipeline reference growth per
condition, and the omics programme numbers. GPU and training set-up, sensitivity tables,
internal file paths and module names stay in the private dataset. Build logs, which are public
on a public repo, do not print paths either. If the page starts showing a new field, add it to
`PUBLIC_METADATA`, otherwise it shows "Not available".

Note that `site/experiment/js/scenario-model.js` (the in-browser reduced model and its
parameters) is part of the public page, as any JavaScript on a website is.

## Turning it on (once)

1. Push this folder to a GitHub repository (branch `main`).
2. Repository **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Push, or run the workflow by hand under **Actions → Build and deploy site → Run workflow**.
   The site appears at `https://<user-or-org>.github.io/<repo>/`.
4. Turn off the old Render service once the Pages URL works.

## Updating the data

**Data in this repo**: this repo is public, so the dataset is deliberately not kept here.
Do not commit `data/` unless everything in it may be public.

**Data in another repo** (e.g. swiss-main): in this repo set
**Settings → Secrets and variables → Actions → Variables**

    DATA_REPO   your-org/swiss-main
    DATA_PATH   data                  (folder inside that repo; default "data")

If that repo is private, also add a secret `DATA_REPO_TOKEN` (fine-grained token, read-only
contents on the data repo). The build then always uses the data repo's latest commit, and
`build_info.json` records which commit it used.

To rebuild automatically when the data repo changes, add this step to a workflow in the
data repo (needs a token with `contents: write` on the website repo, stored as `SITE_DISPATCH_TOKEN`):

```yaml
- run: |
    curl -sS -X POST \
      -H "Authorization: Bearer ${{ secrets.SITE_DISPATCH_TOKEN }}" \
      -H "Accept: application/vnd.github+json" \
      https://api.github.com/repos/<owner>/<website-repo>/dispatches \
      -d '{"event_type":"dataset-updated","client_payload":{"ref":"${{ github.sha }}"}}'
```

## Adding a new omics dataset

Drop the new `outputs/omics/<folder>/gravity_contrast.csv` in place (columns `layer, program,
delta, sd, n_pairs`; only `layer = combined` rows are used) and tell the build which condition
it is in `outputs/omics/manifest.json`:

```json
{
  "cardiac_iss": {
    "tissue": "cardiac",
    "gravity": "flight_ug",
    "detail": "ISS cardiac organoids, paired (n=6); combined score."
  }
}
```

Tissues: `generic, neural, cardiac, crc_tumor_organoid, cancer_cellline_spheroid`.
Gravities: `ground_1g, flight_ug, flight_1g_ctrl, sim_ug_rpm, sim_ug_clinostat`.
`flight_v2` and `crc` are known without a manifest. Unknown folders are skipped with a warning;
malformed rows stop the build so a broken dataset never goes live.

## Run it locally

    python scripts/build_site.py --data path/to/orbio/data --out _site
    python -m http.server 8080 -d _site

Open http://127.0.0.1:8080/ (VS Code over Remote-SSH: Ports panel → 8080 → globe icon).

## Still to do

Site copy has not been verified by the team yet.
`rebuild.py` (re-skinning a fresh swiss-main drop) is not part of this repo; its output now goes in `site/`.
