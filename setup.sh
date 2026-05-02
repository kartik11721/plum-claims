#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

log() { echo "▶ $*"; }
err() { echo "✗ $*" >&2; exit 1; }

# ── Prerequisites ────────────────────────────────────────────────────────────

command -v python3 >/dev/null 2>&1 || err "Python 3.11+ is required"
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
[ "$PYTHON_MINOR" -ge 11 ] || err "Python 3.11+ required (found $PYTHON_VERSION)"

command -v node >/dev/null 2>&1 || err "Node.js 18+ is required"

if ! command -v uv >/dev/null 2>&1; then
  log "Installing uv..."
  pip install uv --quiet
fi

# ── Load .env if present ─────────────────────────────────────────────────────

if [ -f "$ROOT_DIR/.env" ]; then
  # shellcheck disable=SC1091
  set -a; source "$ROOT_DIR/.env"; set +a
fi

# ── API key ──────────────────────────────────────────────────────────────────

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  read -rp "Enter your Anthropic API key (or press Enter to skip): " api_key
  if [ -n "$api_key" ]; then
    export ANTHROPIC_API_KEY="$api_key"
    # Persist to a local .env so future runs don't re-prompt
    echo "ANTHROPIC_API_KEY=$api_key" > "$ROOT_DIR/.env"
    log "API key saved to .env"
  else
    log "Skipping API key — vision pipeline will not work (eval mode still works)"
  fi
fi

# ── Backend setup ────────────────────────────────────────────────────────────

log "Setting up backend..."
cd "$BACKEND_DIR"
uv venv .venv --quiet
# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install -e ".[dev]" --quiet
log "Backend dependencies installed"

# ── Frontend setup ───────────────────────────────────────────────────────────

log "Setting up frontend..."
cd "$FRONTEND_DIR"
npm install --silent
log "Frontend dependencies installed"

# ── Start services ───────────────────────────────────────────────────────────

log "Starting backend on http://localhost:8000 ..."
cd "$BACKEND_DIR"
# shellcheck disable=SC1091
source .venv/bin/activate
POLICY_FILE="$ROOT_DIR/policy_terms.json" uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

log "Starting frontend on http://localhost:3000 ..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✓ Running — press Ctrl+C to stop both servers"
echo ""
echo "  Backend:  http://localhost:8000/docs"
echo "  Frontend: http://localhost:3000"
echo ""

# Forward signals so both children are killed on Ctrl+C
trap 'echo ""; log "Stopping..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' INT TERM

wait $BACKEND_PID $FRONTEND_PID
