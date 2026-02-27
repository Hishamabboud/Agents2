#!/bin/bash
# run.sh - Orchestrator for the job finder pipeline
# Searches US, Canada, Netherlands, and Scotland for matching jobs
# Output: output/job-leads.txt
#
# Usage:
#   ./scripts/run.sh              — run full finder
#   ./scripts/run.sh --agent      — launch Claude agent for richer browser-based search

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_FILE="logs/finder.log"
mkdir -p logs output

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $*" | tee -a "$LOG_FILE"
}

log "========================================="
log "JOB FINDER — Mohamad Abboud"
log "Countries: US, Canada, Netherlands, Scotland"
log "Visa sponsorship required in all"
log "========================================="

# Run the finder script
log "--- Searching job boards ---"
python3 scripts/find_jobs.py 2>&1 | tee -a "$LOG_FILE"
log "Search complete"

# Count results
LEADS_FILE="output/job-leads.txt"
if [ -f "$LEADS_FILE" ]; then
    COUNT=$(grep -c "^Company:" "$LEADS_FILE" 2>/dev/null || echo 0)
    log "Total leads collected so far: $COUNT"
    echo ""
    echo "Results saved to: $LEADS_FILE"
    echo "Total job leads: $COUNT"
else
    log "No output file found — check for errors above"
fi

log "========================================="
log "Finder cycle complete"
log "========================================="

echo ""
echo "Next steps:"
echo "  1. Review output/job-leads.txt"
echo "  2. Pick roles you're interested in"
echo "  3. Apply directly via the links provided"
echo "  4. Run again to find more: ./scripts/run.sh"
