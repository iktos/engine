# Iktos 3D Align

This folder supports **ligand-based alignment** workflows using the **Iktos 3D Align API**. Given a reference ligand in 3D (SDF) and a list of query SMILES, the API predicts aligned 3D poses scored by pharmacophore and shape similarity — no protein structure required.

## What is here

- **`align_3d_client.py`** — Async API client and helpers imported by the notebooks.
- **`3DAlign_api_example.ipynb`** — End-to-end example: submit a batch of SMILES against a reference ligand, monitor progress, retrieve scored poses, and optionally save SDF files.
- **`3DAlign_api_benchmark.ipynb`** — Benchmark on the [AlignDockBench](https://zenodo.org/records/15395813) dataset: loads protein/reference/query triplets, submits prediction jobs, then computes RMSD against crystallographic ground-truth poses using `posebusters`.
- **`results/3DAlign_benchmark_results.csv`** — Pre-computed benchmark results.

## API output

Each completed ligand job returns:

- `pharmaco_score` : Pharmacophore similarity to the reference (0–1)
- `shape_score` : Shape similarity to the reference (0–1)
- `ligand_smiles` : Canonicalized SMILES of the query
- `ligand_pose_sdf` : Predicted 3D pose as an molblock string

## Getting started

1. Create a virtual environment (recommended), then from the repo root install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set **`API_URL`** and **`API_KEY`** (see the notebooks; defaults point at a dev API host).

3. Run Jupyter noteboks from this directory (or add it to `PYTHONPATH`) so imports like `from align_3d_client import …` resolve to `align_3d_client.py` next to the notebooks.
