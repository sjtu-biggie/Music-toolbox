# AI Music

AI-assisted music tool: sing or upload audio → MIDI extraction → synthesis → AI modification.

## Setup

**System dependencies:**
```bash
sudo apt-get install -y ffmpeg fluidsynth tmux
```

**Python dependencies:**
```bash
pip install -e .
```

**Soundfont** (required for synthesis): download any General MIDI `.sf2` to `assets/soundfonts/GeneralUser.sf2`

## Running

```bash
scripts/ctl start        # starts backend (port 8000) and frontend (port 5173)
scripts/ctl status       # check running state
scripts/ctl logs backend # tail backend logs
```

Open `http://localhost:5173` in your browser.

## Testing

```bash
scripts/ctl test unit         # unit tests only
scripts/ctl test integration  # end-to-end pipeline (requires backend running)
scripts/ctl test              # all tests
scripts/ctl test watch        # TDD watch mode
```

## Architecture

- `backend/` — FastAPI API (port 8000). Audio processing, MIDI, AI providers.
- `frontend/` — Vite + TypeScript SPA (port 5173). Thin HTTP client only.
- `docs/plans/` — Phase implementation plans.
- `scripts/ctl` — process control.

See `docs/plans/2026-03-01-ai-music-design.md` for full design.
