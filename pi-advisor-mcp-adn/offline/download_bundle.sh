#!/usr/bin/env bash
# Build the offline installation bundle on an INTERNET-CONNECTED Linux/macOS
# machine, cross-downloading Windows wheels.
#
# The fully-pinned requirements-lock.txt + --no-deps is what makes this safe
# cross-platform: pip never has to evaluate dependency markers (which it would
# do against THIS machine's OS and get wrong — e.g. pulling Linux-only NVIDIA
# CUDA packages for torch).
#
# Usage:  ./download_bundle.sh [bundle_dir] [entra_tenant_id]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUNDLE_DIR="${1:-$PROJECT_ROOT/bundle}"
TENANT_ID="${2:-}"
LOGIN_HOST="${LOGIN_HOST:-login.microsoftonline.com}"
PY_INSTALLER_VERSION="3.12.10"

mkdir -p "$BUNDLE_DIR"/{python,wheels,models,app}

echo "== PI Advisor ADN offline bundle builder =="
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert sys.version_info[:2] >= (3, 10), "need python >= 3.10 to run pip download"'

echo "[1/5] Downloading Windows Python installer ..."
curl -fL -o "$BUNDLE_DIR/python/python-$PY_INSTALLER_VERSION-amd64.exe" \
  "https://www.python.org/ftp/python/$PY_INSTALLER_VERSION/python-$PY_INSTALLER_VERSION-amd64.exe"

echo "[2/5] Cross-downloading locked wheels for win_amd64 / cp312 ..."
"$PYTHON" -m pip download -r "$PROJECT_ROOT/requirements-lock.txt" -d "$BUNDLE_DIR/wheels" \
  --no-deps --only-binary=:all: --platform win_amd64 --python-version 312 --implementation cp
"$PYTHON" -m pip download pip setuptools wheel -d "$BUNDLE_DIR/wheels" \
  --only-binary=:all: --platform win_amd64 --python-version 312 --implementation cp
echo "Wheels: $(ls "$BUNDLE_DIR/wheels" | wc -l) files, $(du -sh "$BUNDLE_DIR/wheels" | cut -f1)"

echo "[3/5] Downloading embedding model ..."
"$PYTHON" -m pip install --quiet "huggingface_hub>=0.23"
"$PYTHON" "$SCRIPT_DIR/download_model.py" "$BUNDLE_DIR/models"

if [[ -n "$TENANT_ID" ]]; then
  echo "[4/5] Exporting Entra ID JWKS ..."
  mkdir -p "$BUNDLE_DIR/auth"
  curl -fL -o "$BUNDLE_DIR/auth/jwks.json" \
    "https://$LOGIN_HOST/$TENANT_ID/discovery/v2.0/keys"
  echo "JWKS saved. Re-export monthly — Microsoft rotates signing keys."
else
  echo "[4/5] Skipping JWKS export (no tenant id argument)."
fi

echo "[5/5] Copying application source ..."
cp "$PROJECT_ROOT"/*.py "$PROJECT_ROOT"/requirements*.txt "$PROJECT_ROOT"/.env.example \
   "$PROJECT_ROOT"/README.md "$BUNDLE_DIR/app/" 2>/dev/null || true
cp -r "$PROJECT_ROOT"/offline "$PROJECT_ROOT"/deploy "$PROJECT_ROOT"/docs "$BUNDLE_DIR/app/"

echo
echo "== Bundle complete: $BUNDLE_DIR =="
echo "Carry it into the air-gapped environment and run app\\offline\\install_offline.ps1"
