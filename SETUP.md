# Wavelength — Setup

## Project structure

```
src/
├── backend/
│   ├── main.py              FastAPI app: auth, profile, generation, feedback, email stub
│   ├── auth.py               bcrypt password hashing + JWT sessions
│   ├── db.py                 MongoDB connection
│   ├── models.py             request/response schemas
│   ├── trend_retrieval.py    weather (real) + trend (stub)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html             redirects to login or app based on session
    ├── login.html             log in / sign up
    ├── profile.html           onboarding (first login) + settings (later edits)
    ├── app.html                chat (left) + agent loop and per-state drafts (right)
    ├── styles.css              design tokens: dark (default) + light theme
    ├── js/
    │   ├── common.js           API base, token storage, authFetch()
    │   ├── auth.js
    │   ├── profile.js
    │   └── app.js
    └── assets/
        └── logo.png            put your logo here
```

## 1. MongoDB

Either works:
- **Local**: install MongoDB Community and run it (`mongod`), or via Docker: `docker run -d -p 27017:27017 mongo`
- **Atlas (free tier)**: create a free cluster at mongodb.com/atlas, get its connection string

## 2. Backend setup

```bash
cd src/backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- `MONGODB_URI` — your local or Atlas connection string
- `JWT_SECRET` — any long random string (used to sign login sessions)

```bash
uvicorn main:app --reload
```

Runs at `http://localhost:8000`. Check `http://localhost:8000/health`.

## 3. Frontend setup

No build step. Put your logo at `src/frontend/assets/logo.png`, then open `src/frontend/index.html` in a browser. It'll route you to `login.html` (or straight to `app.html` if already logged in).

## First-time flow

1. Sign up on `login.html`
2. Redirected to `profile.html?onboarding=1` — enter business name, industry, tone, pick states to promote in, optionally paste past taglines
3. Redirected to `app.html` — chat on the left. Type a brief (optionally attach a `.txt`/`.md`/`.csv` of past posts as style examples), press Enter, and watch the agent loop run on the right. One draft card appears per selected state
4. Thumbs up/down each draft, regenerate per state, mark ones you like as "Use this"
5. Once at least one state has a selection, "Draft email" appears — review/edit, then "Approve & send"

## Auth validation

Client (`js/common.js`, `js/auth.js`) and server (`models.py`) enforce the same rules:
- Email must be a valid address (server lowercases it, so `Sam@Gmail.com` and `sam@gmail.com` are one account). The form also suggests fixes for common typos like `gmial.com`.
- Password: 8+ characters, at least one letter and one number, at most 72 bytes (bcrypt's limit). Signup also asks you to confirm it.
- Existing accounts keep working: passlib and bcrypt both produce standard `$2b$` hashes.
- After changing requirements, run `pip install -r requirements.txt` again (`passlib` was replaced by `bcrypt`).

## What's real vs. stubbed right now

| Component | Status |
|---|---|
| Signup / login (bcrypt-hashed passwords, JWT sessions) | Real |
| Profile storage (MongoDB) | Real |
| Weather grounding | Real (Open-Meteo, no key needed) |
| Trend grounding | Stub — replace `get_trend_stub()` in `trend_retrieval.py` |
| Agent loop animation | Front-end only — steps are choreographed while one `/generate-taglines` request runs. Stream real step events from the backend when the LLM call is wired in |
| Tagline generation | Stub — template string in `generate_for_state()` in `main.py`; swap in a real LLM call |
| Thumbs up/down feedback | Real (stored in MongoDB `feedback` collection) — not yet fed back into generation as a reward signal |
| Email draft | Stub — template in `/draft-email` |
| Email send | Stub — `/send-email` doesn't actually send anything yet; wire up a provider (SendGrid, SES, etc.) |
| Auto-posting to social accounts | Not built — later-phase item per the product vision |

## Next steps

- Wire a real LLM call into `generate_for_state()`, using `past_taglines` as few-shot style examples
- Replace `get_trend_stub()` with a real Google Trends call + relevance ranking
- Feed thumbs up/down feedback into prompt selection or fine-tuning
- Wire a real email provider for `/send-email`
- Expand `STATE_TO_CITY` / `AVAILABLE_STATES` as more launch regions are locked in
