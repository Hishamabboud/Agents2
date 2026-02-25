#!/bin/bash
# run.sh - Orchestrator for the full job application pipeline
# Usage: ./scripts/run.sh [--search-only] [--no-apply]

set -e

# Navigate to project root (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_FILE="logs/agent.log"
mkdir -p logs

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $*" | tee -a "$LOG_FILE"
}

log "========================================="
log "Starting job application pipeline cycle"
log "========================================="

# Phase 1: Search / URL processing
log "--- Phase 1: Search ---"
python3 scripts/search.py 2>&1 | tee -a "$LOG_FILE"
log "Search complete"

if [[ "$1" == "--search-only" ]]; then
    log "Search-only mode. Stopping here."
    exit 0
fi

# Phase 2: Score
log "--- Phase 2: Score ---"
python3 scripts/score.py 2>&1 | tee -a "$LOG_FILE"
log "Scoring complete"

# Phase 3: Tailor
log "--- Phase 3: Tailor ---"
python3 scripts/tailor.py 2>&1 | tee -a "$LOG_FILE"
log "Tailoring complete"

if [[ "$1" == "--no-apply" ]]; then
    log "No-apply mode. Stopping before submission."
    log "Review tailored materials in output/ before applying."
    exit 0
fi

# Phase 4: Apply
log "--- Phase 4: Apply ---"
python3 scripts/apply.py 2>&1 | tee -a "$LOG_FILE"
log "Applications processed"

# Phase 5: Summary
log "--- Phase 5: Summary ---"
if command -v python3 &>/dev/null; then
    python3 - <<'EOF' 2>&1 | tee -a "$LOG_FILE"
import json, os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in dir() else '.'
apps_file = os.path.join('.', 'data', 'applications.json')
if os.path.exists(apps_file):
    with open(apps_file) as f:
        apps = json.load(f)
    print(f"Total applications logged: {len(apps)}")
    by_status = {}
    for a in apps:
        s = a.get('status', 'unknown')
        by_status[s] = by_status.get(s, 0) + 1
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")
else:
    print("No applications.json found yet.")
EOF
fi

log "========================================="
log "Pipeline cycle complete"
log "========================================="

echo ""
echo "Check output:"
echo "  - data/applications.json  (application tracker)"
echo "  - output/tailored-resumes/ (generated resumes)"
echo "  - output/cover-letters/   (generated cover letters)"
echo "  - output/screenshots/     (pre-submit screenshots)"
echo "  - logs/agent.log          (full pipeline log)"
