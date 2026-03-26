#!/usr/bin/env bash
# scripts/run_integration_test.sh — Phase 1+2+3 end-to-end test
set -euo pipefail

BACKEND="http://localhost:8000"
FIXTURE="tests/fixtures/sample.wav"

echo "=== Integration Test: Phase 1+2+3 Core Pipeline ==="

# 1. Health check
echo "[1/8] Health check..."
curl -sf "$BACKEND/health" | grep '"ok"' > /dev/null
echo "      PASS"

# 2. Upload
echo "[2/8] Upload audio..."
RESPONSE=$(curl -sf -X POST "$BACKEND/audio/upload" \
  -F "file=@$FIXTURE;type=audio/wav" \
  -F "name=Integration Test Track")
TRACK_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['track_id'])")
echo "      PASS — track_id=$TRACK_ID"

# 3. Extract MIDI
echo "[3/8] Extract MIDI..."
NOTES=$(curl -sf -X POST "$BACKEND/midi/$TRACK_ID/extract" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['notes']))")
echo "      PASS — $NOTES notes extracted"

# 4. Synthesize
echo "[4/8] Synthesize..."
curl -sf -X POST "$BACKEND/midi/$TRACK_ID/synthesize" > /dev/null
# Verify file exists
WAV="data/audio/${TRACK_ID}_synth.wav"
[[ -f "$WAV" ]] || { echo "FAIL — $WAV not found"; exit 1; }
SIZE=$(stat -c%s "$WAV")
[[ "$SIZE" -gt 1000 ]] || { echo "FAIL — $WAV is suspiciously small ($SIZE bytes)"; exit 1; }
echo "      PASS — synth.wav is ${SIZE} bytes"

# 5. Record endpoint
echo "[5/8] Record endpoint..."
REC_RESPONSE=$(curl -sf -X POST "$BACKEND/audio/record" \
  -F "file=@$FIXTURE;type=audio/wav" \
  -F "name=Integration Recording")
REC_TRACK=$(echo "$REC_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['track_id'])")
echo "      PASS — record track_id=$REC_TRACK"

# 6. Region edit + re-synthesize
echo "[6/8] Region edit + synthesize..."
curl -sf -X PUT "$BACKEND/midi/$TRACK_ID/region" \
  -H "Content-Type: application/json" \
  -d '{"start_sec":0.0,"end_sec":5.0,"pitch_shift":2}' > /dev/null
curl -sf -X POST "$BACKEND/midi/$TRACK_ID/synthesize" > /dev/null
echo "      PASS"

echo "[7/8] AI modify job..."
JOB_RESP=$(curl -sf -X POST "$BACKEND/ai/$TRACK_ID/modify" \
  -H "Content-Type: application/json" \
  -d "{\"mode\":\"style\",\"prompt\":\"test\",\"start_sec\":0.0,\"end_sec\":1.0,\"provider\":\"local\"}")
JOB_ID=$(echo "$JOB_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
JOB_STATUS=$(curl -sf "$BACKEND/ai/jobs/$JOB_ID" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
[[ "$JOB_STATUS" =~ ^(pending|running|done|failed)$ ]] || { echo "FAIL — unexpected status: $JOB_STATUS"; exit 1; }
echo "      PASS — job $JOB_ID status=$JOB_STATUS"

echo "[8/8] Health check..."
HEALTH=$(curl -sf "$BACKEND/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
[[ "$HEALTH" == "ok" ]] || { echo "FAIL — health check returned: $HEALTH"; exit 1; }
echo "      PASS — health ok"

echo ""
echo "=== All integration tests PASSED ==="
