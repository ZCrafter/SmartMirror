#!/usr/bin/env bash
set -e

APP_DIR="${HOME}/smart_mirror"

echo "Installing Smart Mirror Weather LEDs into ${APP_DIR}"

mkdir -p "${APP_DIR}"
cp -r . "${APP_DIR}/"

cd "${APP_DIR}"

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
  echo "Edit it with: nano ${APP_DIR}/.env"
fi

echo
echo "Install complete."
echo "Run tests:"
echo "  cd ${APP_DIR}"
echo "  source venv/bin/activate"
echo "  python tests/layout_test.py"
echo "  python tests/weather_api_test.py"
echo "  python tests/weather_render_test.py"
echo
echo "Run main app:"
echo "  python main.py"
