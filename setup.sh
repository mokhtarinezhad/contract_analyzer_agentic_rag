#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Contract Analyzer — One-command setup
# Usage: bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

echo "==> Contract Analyzer Setup"
echo ""

# ── Python version check ──────────────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python)
PY_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
echo "Using Python: $PYTHON ($PY_VERSION)"

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "==> Creating virtual environment..."
    $PYTHON -m venv .venv
fi

source .venv/bin/activate
PYTHON=$(command -v python)   # re-point to the venv python now that it is active
echo "==> Virtual environment activated: .venv"

# ── Upgrade pip ───────────────────────────────────────────────────────────────
pip install --upgrade pip --quiet

# ── Install dependencies ──────────────────────────────────────────────────────
echo "==> Installing Python dependencies..."
pip install -r requirements.txt

# ── Environment file ──────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "==> Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "  IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY before running."
    echo ""
fi

# ── System dependencies (macOS) ───────────────────────────────────────────────
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "==> Checking system dependencies (macOS)..."
    if command -v brew &>/dev/null; then
        # poppler is needed by pdf2image (unstructured dependency)
        brew list poppler &>/dev/null || brew install poppler
        # tesseract is needed for OCR (optional)
        brew list tesseract &>/dev/null || brew install tesseract
        echo "  System deps OK"
    else
        echo "  WARNING: Homebrew not found. If PDF parsing fails, install poppler:"
        echo "  brew install poppler tesseract"
    fi
fi

# ── Create required directories ────────────────────────────────────────────────
mkdir -p data logs data/chroma_db data/models

# ── Download sentence-transformers model (once, into ./data/models) ───────────
echo "==> Pre-downloading embedding model (all-MiniLM-L6-v2) into ./data/models ..."
$PYTHON -c "
from sentence_transformers import SentenceTransformer
import os, pathlib
cache = str(pathlib.Path('./data/models').resolve())
SentenceTransformer('all-MiniLM-L6-v2', cache_folder=cache)
print('  Embedding model cached at:', cache)
" && echo "  Embedding model ready" \
  || echo "  WARNING: Model download failed. Will retry on first run."

# ── Verify Anthropic API key ──────────────────────────────────────────────────
if grep -q "sk-ant-..." .env 2>/dev/null; then
    echo ""
    echo "  WARNING: ANTHROPIC_API_KEY is still the placeholder value."
    echo "  Edit .env and set your real key."
fi

echo ""
echo "==> Setup complete!"
echo ""
echo "To start the application:"
echo ""
echo "  1. Edit .env and set ANTHROPIC_API_KEY=sk-ant-..."
echo ""
echo "  2. Start the API server (terminal 1):"
echo "     source .venv/bin/activate"
echo "     uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "  3. Start the Streamlit UI (terminal 2):"
echo "     source .venv/bin/activate"
echo "     streamlit run frontend/app.py"
echo ""
echo "  4. Open http://localhost:8501 in your browser"
echo "  5. API docs: http://localhost:8000/docs"
echo ""
