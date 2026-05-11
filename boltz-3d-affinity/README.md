# Boltz 3D affinity

This folder supports **protein–ligand binding affinity** workflows using the **Iktos Boltz2 affinity scoring API** (3D structure–based scoring). It is meant for **hands-on API usage**, **benchmarking**, and **storing related inputs and outputs**—not for running the Boltz model locally.

## What is here

- **`Boltz_3Daffinity_api_example.ipynb`** — Step-by-step guide: connect to the API, optional MSA upload and PDB cleaning, submit affinity jobs, and retrieve results for individual protein–ligand pairs.
- **`Boltz_3Daffinity_api_benchmark.ipynb`** — Runs the **OpenFE binding-affinity benchmark** at scale (~56 targets, 1054 ligands) through the same API: upload MSAs, submit jobs, merge predictions with experimental data, and compute correlation metrics (e.g. Spearman / Pearson).
- **`boltz_api_client.py`** — Async API client and helpers imported by the notebooks.
- **`data/`** — Benchmark assets and artifacts, including OpenFE/FEP+ targets under `data/benchmark/` (structures, ligands, edges), precomputed MSAs where applicable, and example **results** CSVs under `data/results/`.

## Getting started

1. Create a virtual environment (recommended), then from the repo root install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set **`API_URL`** and **`API_KEY`** (see the notebooks; defaults point at a dev API host).
3. Run Jupyter from this directory (or add this directory to **`PYTHONPATH`**) so imports like `from boltz_api_client import …` resolve to `boltz_api_client.py` next to the notebooks.

Use the scoring notebook for one-off or small-batch scoring; use the benchmark notebook when you need a full benchmark style evaluation pipeline over the API.
