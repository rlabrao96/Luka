#!/usr/bin/env bash
# Usage: ./run_chunk_verifications.sh <chunk-letter>
#   A|B|C|D|E|F|G|H  - run that chunk's §11.4 checkpoint
#   day4              - integration verification
#   day6              - UX consistency pass
set -euo pipefail

CHUNK="${1:-}"
if [ -z "$CHUNK" ]; then
  echo "Usage: $0 <A|B|C|D|E|F|G|H|day4|day6>"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

echo "→ Seeding budget test fixtures..."
python backend/scripts/seed_budget_test_fixtures.py

echo "→ Starting dev backend on :8000 (background)..."
(cd backend && uvicorn main:app --port 8000 > /tmp/luka-verify-backend.log 2>&1) &
BACKEND_PID=$!
trap "kill $BACKEND_PID 2>/dev/null || true" EXIT

echo "→ Starting dev frontend on :3000 (background)..."
(cd frontend && npm run dev > /tmp/luka-verify-frontend.log 2>&1) &
FRONTEND_PID=$!
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true" EXIT

echo "→ Waiting 6s for servers..."
sleep 6

echo "→ Chunk $CHUNK checkpoint — dispatch the corresponding verification agent per spec §11.4"
echo "→ Backend log: /tmp/luka-verify-backend.log"
echo "→ Frontend log: /tmp/luka-verify-frontend.log"
