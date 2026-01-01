# qibo-e91-sim

Interactive E91 protocol simulations using Qibo and Qiskit backends.

## Run locally ✅

1. Install Python dependencies:

```bash
pip install -r requirement.txt
```

2. Start the backend (FastAPI + static files):

```bash
python qiskit_api.py
# or: uvicorn qiskit_api:app --host 0.0.0.0 --port 8000 --reload
```

3. Open the dashboard in your browser:

http://127.0.0.1:8000/index.html

The Phase pages call backend API endpoints under `/api/` (e.g. `/api/phase1/chsh`). This project now requires the Qiskit backend to be running; client-side fallback simulations have been removed.

## Testing

Run the automated test suite locally:

```bash
pip install -r requirement.txt
pytest -q
```

A GitHub Actions workflow `.github/workflows/ci.yml` runs the tests on push and pull requests to `main`.
