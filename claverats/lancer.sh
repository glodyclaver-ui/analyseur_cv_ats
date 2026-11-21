#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
command -v tesseract >/dev/null || echo "OCR : Tesseract non installé (voir INSTALLATION.txt)"
( sleep 2; command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:5002 || open http://127.0.0.1:5002 ) >/dev/null 2>&1 &
python app.py
