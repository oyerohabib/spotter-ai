#!/usr/bin/env bash
# Build script for Render (Python + Node monorepo).
set -euo pipefail

echo "==> Installing Node 20 via nvm"
export NVM_DIR="${HOME}/.nvm"
if [ ! -s "${NVM_DIR}/nvm.sh" ]; then
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi
# shellcheck disable=SC1091
. "${NVM_DIR}/nvm.sh"
nvm install 20
nvm use 20

echo "==> Installing Python dependencies"
pip install -r backend/requirements.txt

echo "==> Building frontend (needs VITE_MAPBOX_ACCESS_TOKEN at build time)"
cd frontend
npm ci
npm run build
cd ..

echo "==> Collecting Django static files"
cd backend
python manage.py collectstatic --noinput
cd ..

echo "==> Build complete"
