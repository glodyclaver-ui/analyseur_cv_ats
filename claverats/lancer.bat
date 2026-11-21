@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === CLAVERATS Pro ===
where python >nul 2>nul || (echo Python est introuvable. Installez Python 3.11+ puis relancez. & pause & exit /b 1)
if not exist .venv ( echo Creation de l'environnement... & python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
where tesseract >nul 2>nul && (echo OCR : Tesseract detecte.) || (echo OCR : Tesseract NON installe - lecture des images/PDF scannes indisponible. Voir INSTALLATION.txt)
start "" http://127.0.0.1:5002
python app.py
pause
