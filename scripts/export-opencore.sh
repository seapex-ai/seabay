#!/usr/bin/env bash
# export-opencore.sh — Generate the public open-core repository from the monorepo.
#
# Usage: ./scripts/export-opencore.sh [output_dir]
#
# This script copies only open-core files to a clean directory using a strict
# WHITELIST approach based on .opencore-manifest.yml. Nothing is copied unless
# it is explicitly listed below. This prevents accidental exposure of hosted
# intelligence code (production weights, admin API, anti-abuse thresholds).
#
# Principle: manifest is the source of truth; this script enforces it.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="${1:-${REPO_ROOT}/../seabay-public}"

echo "==> Exporting open-core from: ${REPO_ROOT}"
echo "==> Output directory: ${OUTPUT}"

# Clean output
rm -rf "${OUTPUT}"
mkdir -p "${OUTPUT}"

# ── Root files (whitelisted) ──
for f in LICENSE NOTICE README.md README.zh-CN.md CHANGELOG.md ROADMAP.md \
         docker-compose.yml docker-compose.prod.yml .gitignore \
         .opencore-manifest.yml; do
  [ -f "${REPO_ROOT}/${f}" ] && cp "${REPO_ROOT}/${f}" "${OUTPUT}/"
done

# ── .github (CI/CD) ──
[ -d "${REPO_ROOT}/.github" ] && cp -r "${REPO_ROOT}/.github" "${OUTPUT}/"

# ── Full directories (all open per manifest) ──
for dir in sdk-py sdk-js cli adapters widgets skill specs examples \
           helm-lite reference-stack website docs scripts; do
  [ -d "${REPO_ROOT}/${dir}" ] && cp -r "${REPO_ROOT}/${dir}" "${OUTPUT}/"
done

# ══════════════════════════════════════════════════════════════
# ── Backend (STRICT WHITELIST — nothing copied by default) ──
# ══════════════════════════════════════════════════════════════
mkdir -p "${OUTPUT}/backend"

# Non-app backend files
for f in pyproject.toml Dockerfile entrypoint.sh alembic.ini .env.example; do
  [ -f "${REPO_ROOT}/backend/${f}" ] && cp "${REPO_ROOT}/backend/${f}" "${OUTPUT}/backend/"
done

# Alembic migrations
[ -d "${REPO_ROOT}/backend/alembic" ] && cp -r "${REPO_ROOT}/backend/alembic" "${OUTPUT}/backend/"

# Tests
[ -d "${REPO_ROOT}/backend/tests" ] && cp -r "${REPO_ROOT}/backend/tests" "${OUTPUT}/backend/"

# ── Backend app root-level files ──
mkdir -p "${OUTPUT}/backend/app"
for f in "${REPO_ROOT}"/backend/app/*.py; do
  [ -f "$f" ] && cp "$f" "${OUTPUT}/backend/app/"
done

# ── Backend app directories (whitelisted, NO hosted/) ──
for dir in models schemas core workers; do
  if [ -d "${REPO_ROOT}/backend/app/${dir}" ]; then
    cp -r "${REPO_ROOT}/backend/app/${dir}" "${OUTPUT}/backend/app/"
  fi
done

# Remove admin schema (must not be in public repo)
rm -f "${OUTPUT}/backend/app/schemas/admin.py"

# ── API endpoints (WHITELIST — manifest api_open + deps) ──
mkdir -p "${OUTPUT}/backend/app/api/v1"

# Copy api/ root files
for f in __init__.py deps.py; do
  [ -f "${REPO_ROOT}/backend/app/api/${f}" ] && cp "${REPO_ROOT}/backend/app/api/${f}" "${OUTPUT}/backend/app/api/"
done

# Whitelisted API v1 endpoints (from .opencore-manifest.yml api_open)
API_WHITELIST=(
  __init__.py
  health.py
  agents.py
  tasks.py
  relationships.py
  circles.py
  intents.py
  verifications.py
  public.py
  events.py
  reports.py
)
# admin.py is NEVER copied — it is hosted_private

for f in "${API_WHITELIST[@]}"; do
  [ -f "${REPO_ROOT}/backend/app/api/v1/${f}" ] && \
    cp "${REPO_ROOT}/backend/app/api/v1/${f}" "${OUTPUT}/backend/app/api/v1/"
done

# Remove admin route registration from __init__.py if present
if [ -f "${OUTPUT}/backend/app/api/v1/__init__.py" ]; then
  sed -i.bak '/admin/d' "${OUTPUT}/backend/app/api/v1/__init__.py"
  rm -f "${OUTPUT}/backend/app/api/v1/__init__.py.bak"
fi

# ── Services (WHITELIST — two groups per manifest) ──
mkdir -p "${OUTPUT}/backend/app/services"

# Group 1: Open-core services (full implementations, no hosted override)
SERVICES_OPEN=(
  __init__.py
  agent_service.py
  relationship_service.py
  circle_service.py
  task_service.py
  verification_service.py
  introduction_service.py
  visibility_service.py
  contact_policy_service.py
  webhook_config_service.py
  webhook_service.py
  idempotency_service.py
  dlp_service.py
  notification_service.py
  passport_service.py
)

# Group 2: Reference implementations of hosted services
# These ship with open-core using default weights. Production overrides
# live in app/hosted/services/ and are NEVER exported.
# Each file MUST have a "Reference implementation" header comment.
SERVICES_REFERENCE=(
  intent_service.py
  search_service.py
  trust_service.py
  metrics_service.py
  activity_service.py
  moderation_service.py
  report_service.py
  shadow_throttle_service.py
  budget_service.py
  new_account_service.py
)

for f in "${SERVICES_OPEN[@]}" "${SERVICES_REFERENCE[@]}"; do
  [ -f "${REPO_ROOT}/backend/app/services/${f}" ] && \
    cp "${REPO_ROOT}/backend/app/services/${f}" "${OUTPUT}/backend/app/services/"
done

# ── Safety: ensure hosted/ NEVER leaks ──
rm -rf "${OUTPUT}/backend/app/hosted"

# ── Verify no admin files leaked ──
if [ -f "${OUTPUT}/backend/app/api/v1/admin.py" ]; then
  echo "ERROR: admin.py found in output! Aborting."
  exit 1
fi
if [ -f "${OUTPUT}/backend/app/schemas/admin.py" ]; then
  echo "ERROR: admin schema found in output! Aborting."
  exit 1
fi

# ── Clean up build artifacts ──
find "${OUTPUT}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT}" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT}" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT}" -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT}" -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT}" -type d -name ".venv" -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT}" -type f -name "*.pyc" -delete 2>/dev/null || true

# ── Summary ──
echo ""
echo "==> Open-core export complete!"
echo "    Files: $(find "${OUTPUT}" -type f | wc -l | tr -d ' ')"
echo "    Size:  $(du -sh "${OUTPUT}" | cut -f1)"
echo ""
echo "    Exported (whitelist):"
echo "    - API endpoints: ${#API_WHITELIST[@]} files"
echo "    - Services (open): ${#SERVICES_OPEN[@]} files"
echo "    - Services (reference): ${#SERVICES_REFERENCE[@]} files"
echo ""
echo "    Excluded from public repo:"
echo "    - backend/app/hosted/          (production weights & thresholds)"
echo "    - backend/app/api/v1/admin.py  (admin control panel)"
echo "    - backend/app/schemas/admin.py (admin schemas)"
echo ""
echo "    Next: cd ${OUTPUT} && git init && git remote add origin git@github.com:seapex-ai/seabay.git"
