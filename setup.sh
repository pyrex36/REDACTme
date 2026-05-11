#!/usr/bin/env bash
# setup.sh  –  One-time setup + launch for the redaction engine
set -e

echo "── SecureRedact setup ──────────────────────────────"

cd "$(dirname "$0")/backend"

echo "→ Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo "→ Downloading spaCy language model..."
python -m spacy download en_core_web_sm --quiet

echo ""
echo "── Setup complete. Starting server... ─────────────"
echo ""
echo "  Backend API : http://localhost:8000"
echo "  Frontend UI : open frontend/index.html in your browser"
echo ""
echo "  (or serve the frontend: python -m http.server 3000 --directory ../frontend)"
echo ""

uvicorn main:app --reload --port 8000 --host 0.0.0.0