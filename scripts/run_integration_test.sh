#!/usr/bin/env bash
# scripts/run_integration_test.sh — Phase 1 end-to-end test
set -euo pipefail

BACKEND="http://localhost:8000"
FIXTURE="tests/fixtures/sample.wav"

echo "=== Integration Test: Phase 1 Core Pipeline ==="

# 1. Health check
echo "[1/4] Health check..."
curl -sf "$BACKEND/health" | grep '"ok"' > /dev/null
echo "      PASS"

# 2. Upload
echo "[2/4] Upload audio..."
RESPONSE=$(curl -sf -X POST "$BACKEND/audio/upload" \
  -F "file=@$FIXTURE;type=audio/wav")
TRACK_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['track_id'])")
echo "      PASS — track_id=$TRACK_ID"

# 3. Extract MIDI
echo "[3/4] Extract MIDI..."
NOTES=$(curl -sf -X POST "$BACKEND/midi/$TRACK_ID/extract" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['notes']))")
echo "      PASS — $NOTES notes extracted"

# 4. Synthesize
echo "[4/4] Synthesize..."
curl -sf -X POST "$BACKEND/midi/$TRACK_ID/synthesize" > /dev/null
# Verify file exists
WAV="data/audio/${TRACK_ID}_synth.wav"
[[ -f "$WAV" ]] || { echo "FAIL — $WAV not found"; exit 1; }
SIZE=$(stat -c%s "$WAV")
[[ "$SIZE" -gt 1000 ]] || { echo "FAIL — $WAV is suspiciously small ($SIZE bytes)"; exit 1; }
echo "      PASS — synth.wav is ${SIZE} bytes"

echo ""
echo "=== All integration tests PASSED ==="
