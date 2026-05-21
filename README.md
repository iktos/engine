# Iktos Engine

This repository contains the first version of **Iktos Engine**: a set of focused, production-scale APIs for 3D virtual screening workflows spanning both **ligand-based** and **structure-based** regimes.

For more technical depth, see the **[Iktos 3D Engine technical report](Iktos_3D_Engine_Technical_Report.pdf)** in this repository.

## APIs

- **Iktos 3D Align**
  - Accurate ligand alignment method, useful for **3D ligand-based (LB) virtual screening**.

- **Iktos 3D Dock**
  - Accurate template-based docking method, useful for **3D structure-based (SB) virtual screening**.

- **Boltz 3D Affinity**
  - Reuses the **Boltz-2 affinity trunk** (Passaro et al., 2025) to score **binding affinity directly from a user-supplied protein–ligand complex**, without the time-consuming **cofolding** step.

## Repository layout

- `3d-align/`: notebooks, client code, and benchmark assets for the **Iktos 3D Align** API integration.
- `3d-dock/`: notebooks, client code, and benchmark assets for the **Iktos 3D Dock** API integration.
- `boltz-3d-affinity/`: notebooks, client code, and benchmark assets for the **Boltz 3D Affinity** API integration.
- `virtual-screening-pipeline/`: **virtual screening pipelines** combining these APIs — **`virtual_screening_pipeline_A.ipynb`** (full **3D Align → 3D Dock → Boltz 3D Affinity**) and **`virtual_screening_pipeline_B.ipynb`** (**3D Dock → Boltz 3D Affinity**, skips Align). See `virtual-screening-pipeline/README.md` for how to run them, and example data under `virtual-screening-pipeline/data/`.
- **`Iktos_3D_Engine_Technical_Report.pdf`** : technical report with **additional implementation and performance details** on Iktos Engine and the APIs above. Open this PDF for deeper context beyond the README and example notebooks.

## Getting started

Set up an isolated environment using any tool of your choice (venv, conda, uv, …), then install dependencies from the repo root:

```bash
# example with venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Access & Contact

To request access or learn more, reach out at **contact@iktos.com**.

## Status

This is an initial release of the Engine APIs and supporting materials; the repository will evolve as additional endpoints, examples, and benchmarking utilities are added.
