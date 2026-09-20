# Wavelength — Setup

Local setup instructions for running the app end to end: FastAPI backend + static frontend.

## Project structure

```
src/
├── backend/
│   ├── main.py
│   ├── trend_retrieval.py
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html
    ├── styles.css
    ├── script.js
    └── assets/
        └── logo.png
```

## 1. Backend setup

```bash
cd src/backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # fill in keys once an LLM provider is picked
uvicorn main:app --reload
```

Backend runs at `http://localhost:8000`.
Check it's alive at `http://localhost:8000/health` → should return `{"status":"ok"}`.

Leave this terminal window running while using the frontend.

## 2. Frontend setup

No build step — plain HTML/CSS/JS.

```bash
cd src/frontend
```

Open `index.html` directly in a browser (double-click it, or right-click → Open With → your browser).

Put your logo file at `src/frontend/assets/logo.png`. If it's missing or fails to load, the page falls back to a text "Wavelength" wordmark automatically.

## What's real vs. stubbed right now

| Component | Status |
|---|---|
| `/generate-caption` endpoint | Real, working |
| Weather lookup | Real (Open-Meteo API, no key needed) |
| Trend lookup | Stub — placeholder text, replace in `trend_retrieval.py` |
| Caption generation | Stub — template string, replace with a real LLM call in `main.py` (`call_llm()`) once a provider is picked |

## Troubleshooting

- **"Could not reach the backend" in the browser** → make sure `uvicorn` is still running in its terminal.
- **Port 8000 already in use** → run `uvicorn main:app --reload --port 8001` and update `API_BASE` in `script.js` to match.
- **Logo not showing** → confirm the file is at `src/frontend/assets/logo.png` exactly (case-sensitive on some systems).

## Next steps (Session 5+)

- Wire `get_trend_stub()` to the real Google Trends API + relevance ranking
- Implement `call_llm()` with the chosen provider
- Add festival-calendar signal for India regions
- Expand `CITY_COORDS` in `trend_retrieval.py` to the locked-in launch cities/states