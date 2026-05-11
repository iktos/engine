# Virtual screening pipeline

This folder contains **two example notebooks** that chain the **Iktos Engine** APIs used in a typical 3D virtual screening workflow:

1. **Iktos 3D Align** — ligand-based (LB) alignment / ranking against a reference active  
2. **Iktos 3D Dock** — structure-based (SB) template docking into the protein pocket  
3. **Boltz 3D Affinity** — affinity scoring on **docked poses** (no cofolding)

## Files

- **`virtual_screening_pipeline_A.ipynb`** — full cascade: **Iktos 3D Align (LB)** → **Iktos 3D Dock (SB)** → **Boltz 3D Affinity**.
- **`virtual_screening_pipeline_B.ipynb`** — shorter cascade: **Iktos 3D Dock (SB)** → **Boltz 3D Affinity** (skips Align; docks the full SMILES list, then filters/ranks before Boltz).
- For API-specific details, see also:
  - `../3d-align/3DAlign_api_example.ipynb`
  - `../3d-dock/3DDock_api_example.ipynb`
  - `../boltz-3d-affinity/Boltz_3Daffinity_api_example.ipynb`

- **`data/`** — small example inputs used by the notebook (e.g. `data/3kl6_example/`).

## How to run

1. **Create a Python environment** and install dependencies.  
   The client modules live next to the API example notebooks; a practical baseline is:

   ```bash
   pip install -r ../requirements.txt
   ```

2. **Configure credentials / endpoints** via environment variables (recommended):

   - `API_KEY` — your API key  
   - `API_BASE_URL` — the api base url 

3. **Start Jupyter from this folder** ensure the repo’s `3d-align/`, `3d-dock/`, and `boltz-3d-affinity/` directories are on `PYTHONPATH` so imports such as `align_3d_client`, `dock_3d_client`, and `boltz_api_client` resolve.

4. Open **`virtual_screening_pipeline_A.ipynb`** or **`virtual_screening_pipeline_B.ipynb`** and run cells top-to-bottom.

