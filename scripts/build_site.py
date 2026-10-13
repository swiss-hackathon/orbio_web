"""Build the ORBIO static site from a dataset folder.

    python scripts/build_site.py --data data --out _site

Reads
    <data>/run_metadata.json
    <data>/outputs/omics/<folder>/gravity_contrast.csv   (every folder found)
    <data>/outputs/omics/manifest.json                   (optional; maps folders to tissue/gravity)

Writes a copy of site/ to <out>, plus (filtered to what the page displays; see PUBLIC_METADATA)
    <out>/experiment/data/omics.json
    <out>/experiment/data/run_metadata.json
    <out>/experiment/data/build_info.json

Fails loudly on malformed data so a bad dataset never reaches the live site.
"""
import argparse
import csv
import datetime as dt
import json
import os
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

TISSUES = {"generic", "neural", "cardiac", "crc_tumor_organoid", "cancer_cellline_spheroid"}
GRAVITIES = {"ground_1g", "flight_ug", "flight_1g_ctrl", "sim_ug_rpm", "sim_ug_clinostat"}
PROGRAMS = {"proliferation", "apoptosis", "anti_apoptosis", "hypoxia", "glycolysis",
            "adhesion", "oxphos", "apoptosis_balance"}

# Folders the current pipeline already produces. A manifest.json overrides or extends these.
DEFAULT_MANIFEST = {
    "flight_v2": {
        "tissue": "neural", "gravity": "flight_ug",
        "detail": "Paired biological units (n=4 pairs); combined transcriptome score.",
    },
    "crc": {
        "tissue": "crc_tumor_organoid", "gravity": "sim_ug_clinostat",
        "detail": "Clinostat organoid contrast (n=4 per arm); combined score.",
    },
}


def fail(message):
    print(f"::error::{message}", file=sys.stderr)
    sys.exit(1)


def read_contrast(path):
    label = f"omics folder '{path.parent.name}'"
    programs = {}
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("layer", "combined") != "combined":
                continue
            name = row["program"].strip()
            if name not in PROGRAMS:
                print(f"::warning::{label}: unknown programme '{name}' skipped")
                continue
            try:
                programs[name] = {
                    "delta": float(row["delta"]),
                    "sd": float(row["sd"]),
                    "n": int(float(row.get("n_pairs") or row.get("n_ug") or row.get("n") or 0)),
                }
            except (KeyError, ValueError) as error:
                fail(f"{label}: bad row for '{name}': {error}")
    return programs


def build_omics(data_dir):
    omics_root = data_dir / "outputs" / "omics"
    manifest = dict(DEFAULT_MANIFEST)
    manifest_path = omics_root / "manifest.json"
    if manifest_path.exists():
        manifest.update(json.loads(manifest_path.read_text(encoding="utf-8")))

    out = {}
    for csv_path in sorted(omics_root.glob("*/gravity_contrast.csv")):
        folder = csv_path.parent.name
        entry = manifest.get(folder)
        if not entry:
            print(f"::warning::omics folder '{folder}' has no manifest entry, skipped")
            continue
        tissue, gravity = entry["tissue"], entry["gravity"]
        if tissue not in TISSUES or gravity not in GRAVITIES:
            fail(f"manifest entry '{folder}': unknown tissue/gravity {tissue}/{gravity}")
        programs = read_contrast(csv_path)
        if not programs:
            print(f"::warning::omics folder '{folder}' has no combined-layer rows, skipped")
            continue
        out.setdefault(tissue, {})[gravity] = {
            "programs": programs,
            "sourceFile": str(csv_path.relative_to(data_dir)).replace(os.sep, "/"),
            "contrast": entry.get("contrast", f"{gravity} vs ground_1g"),
            "detail": entry.get("detail", ""),
        }
    return out


# Only these run_metadata fields are published. Everything else (GPU, training set-up,
# sensitivity tables, internal file paths and module names) stays in the private dataset.
# Each entry is one field the page displays; check site/experiment/js before adding more.
PUBLIC_METADATA = {
    "profile": ["grid_n", "grid_h", "max_agents"],
    "physics": ["d_o2", "d_glc", "o2Hypoxic", "o2ProliferationSaturation", "o2Necrotic", "glucoseMinimum"],
    "initialization": ["datasetMinimumAgents", "datasetMaximumAgents"],
}


def public_metadata(metadata):
    out = {}
    for section, keys in PUBLIC_METADATA.items():
        values = {key: metadata[section][key] for key in keys if key in metadata.get(section, {})}
        if values:
            out[section] = values
    # Pipeline reference growth per tissue and gravity (n and median only), shown with the growth chart.
    table = (metadata.get("faceValidity") or {}).get("byTissueAndGravity")
    if table:
        out["faceValidity"] = {"byTissueAndGravity": {
            tissue: {gravity: {"n": cell.get("n"), "median_log_fold": cell.get("median_log_fold")}
                     for gravity, cell in by_gravity.items()}
            for tissue, by_gravity in table.items()
        }}
    return out


def public_omics(omics):
    # Keep the numbers and the condition label; drop source file paths and free-text detail.
    return {
        tissue: {gravity: {"programs": entry["programs"], "contrast": entry["contrast"]}
                 for gravity, entry in by_gravity.items()}
        for tissue, by_gravity in omics.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data", help="dataset folder")
    parser.add_argument("--out", default="_site", help="output folder")
    parser.add_argument("--dataset-ref", default=os.environ.get("DATASET_REF", ""),
                        help="commit or tag of the dataset, recorded in build_info.json")
    args = parser.parse_args()

    data_dir = pathlib.Path(args.data).resolve()
    out_dir = pathlib.Path(args.out).resolve()
    
    # Without the interactive experiment there is no data to publish: copy the site and stop.
    if not (ROOT / "site" / "experiment").exists():
        if out_dir.exists():
            shutil.rmtree(out_dir)
        shutil.copytree(ROOT / "site", out_dir)
        (out_dir / ".nojekyll").touch()
        print(f"built {out_dir.name} · no experiment page, no data published")
        return
    meta_path = data_dir / "run_metadata.json"
    if not meta_path.exists():
        fail("run_metadata.json not found in the dataset folder. Set the repository variables "
             "DATA_REPO (and DATA_PATH) and the secret DATA_REPO_TOKEN, or add a data/ folder.")

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    omics = build_omics(data_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(ROOT / "site", out_dir)
    (out_dir / ".nojekyll").touch()

    target = out_dir / "experiment" / "data"
    target.mkdir(parents=True, exist_ok=True)
    (target / "omics.json").write_text(json.dumps(public_omics(omics), ensure_ascii=False), encoding="utf-8")
    (target / "run_metadata.json").write_text(json.dumps(public_metadata(metadata), ensure_ascii=False), encoding="utf-8")
    (target / "build_info.json").write_text(json.dumps({
        "builtAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "datasetRef": args.dataset_ref,
        "omicsContrasts": sorted(f"{t}/{g}" for t, gs in omics.items() for g in gs),
    }, indent=2), encoding="utf-8")

    count = sum(len(g) for g in omics.values())
    print(f"built {out_dir.name} · {count} omics contrast(s)")


if __name__ == "__main__":
    main()
