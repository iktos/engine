# Iktos 3D Dock

This folder supports **structure-based template docking** workflow using the **Iktos 3D Dock API**. Given a protein structure, a reference ligand in 3D (SDF), and a list of query SMILES, the API predicts docked 3D poses scored by Vina energy, pharmacophore, and shape similarity.

## What is here

- **`dock_3d_client.py`** — Async API client and helpers imported by the notebooks.
- **`3DDock_api_example.ipynb`** — End-to-end example: optionally clean the protein, submit a batch of SMILES for docking, monitor progress, retrieve scored poses, and optionally save SDF files.
- **`3DDock_api_benchmark.ipynb`** — Benchmark on the [AlignDockBench](https://zenodo.org/records/15395813) dataset: cleans proteins via the API, loads protein/reference/query triplets, submits prediction jobs, then computes RMSD against crystallographic ground-truth poses using `posebusters`.
  **`results/3DDock_benchmark_results.csv`** — Pre-computed benchmark results.

## Protein cleaning

The API exposes an optional `clean_protein` endpoint used before docking. It is not a full preparation pipeline, but a targeted cleaning step to prevent common issues. It:

- Normalizes atom and residue names to standard PDB conventions
- Converts non-standard amino acids to their canonical equivalents (e.g., SEP → SER)
- Removes terminal cap residues (ACE / NME)
- Removes all non-residue molecules (e.g., water, ions), while retaining cofactors
- Resolves alternate atom locations by keeping only the highest-occupancy conformation

## API output

Each completed ligand job returns:

- `vina_score` : Vina energy (lower is better)
- `pharmaco_score` : Pharmacophore similarity to the reference (0–1)
- `shape_score` : Shape similarity to the reference (0–1)
- `ligand_smiles` : Canonicalized SMILES of the query
- `ligand_pose_sdf` : Predicted 3D docked pose as an molblock string

## Getting started

1. Create a virtual environment (recommended), then from the repo root install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set **`API_URL`** and **`API_KEY`** (see the notebooks; defaults point at a dev API host).

3. Run Jupyter noteboks from this directory (or add it to `PYTHONPATH`) so imports like `from dock_3d_client import …` resolve to `dock_3d_client.py` next to the notebooks.
