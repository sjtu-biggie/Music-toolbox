# Phase 2: Microphone Input Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add browser-based microphone recording to the Streamlit UI. Recorded audio flows through the same backend pipeline as file upload (Phase 1).

**Architecture:** Streamlit's `st.audio_input()` widget (added in v1.35) captures mic audio in the browser and returns bytes. Those bytes go to `POST /audio/record` — identical logic to `/audio/upload`. No WSL2 audio bridge required.

**Tech Stack:** Streamlit `st.audio_input()`, existing `audio_service`, existing FastAPI `/audio` router.

**Prerequisite:** Phase 1 complete and passing.

---

## Task 1: Backend — `/audio/record` Route

**Files:**
- Modify: `backend/api/routes/audio.py`
- Modify: `tests/backend/test_routes.py`

The `/audio/record` endpoint accepts a raw audio blob from the browser (WebM or WAV depending on browser). It writes it to disk, converts to WAV, then follows the same path as `/audio/upload`.

**Step 1: Add failing test**

```python
# append to tests/backend/test_routes.py

@pytest.mark.anyio
async def test_record_accepts_audio_blob(client, wav_bytes):
    resp = await client.post(
        "/audio/record",
        files={"file": ("recording.wav", wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "track_id" in data
    assert data["duration_sec"] > 0
```

**Step 2: Run to verify fails**

```bash
pytest tests/backend/test_routes.py::test_record_accepts_audio_blob -v
```
Expected: 404 (route doesn't exist)

**Step 3: Add route (one new endpoint in audio.py)**

```python
# add to backend/api/routes/audio.py after the upload route

@router.post("/record")
async def record_audio(file: UploadFile = File(...)):
    """Accept browser mic recording blob. Identical pipeline to /upload."""
    StaticConfig.ensure_dirs()
    from uuid import uuid4
    track_id = uuid4()
    # Browser may send webm/ogg — librosa handles it via ffmpeg
    suffix = ".webm" if "webm" in (file.content_type or "") else ".wav"
    raw_path = StaticConfig.TRACKS_DIR / f"{track_id}{suffix}"
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    convert_to_wav(raw_path, wav_path)
    audio, sr = load_audio(wav_path)
    track = Track(
        id=track_id,
        filename=f"recording{suffix}",
        duration_sec=round(len(audio) / sr, 3),
        sample_rate=sr,
        status="ready",
    )
    await _repo.save(track)
    return {"track_id": str(track_id), "duration_sec": track.duration_sec, "sample_rate": sr}
```

**Step 4: Run to verify passes**

```bash
pytest tests/backend/test_routes.py -v
```
Expected: all pass

**Step 5: Commit**

```bash
git add backend/api/routes/audio.py tests/backend/test_routes.py
git commit -m "feat: POST /audio/record endpoint for browser mic blobs"
```

---

## Task 2: Frontend — Record Tab

**Files:**
- Modify: `frontend/api_client.py`
- Create: `frontend/pages/record.py`
- Modify: `frontend/app.py`

**Step 1: Add record_audio to api_client.py**

```python
# append to frontend/api_client.py

def record_audio(audio_bytes: bytes, filename: str = "recording.wav") -> dict:
    resp = _client.post(
        "/audio/record",
        files={"file": (filename, audio_bytes, "audio/wav")},
    )
    resp.raise_for_status()
    return resp.json()
```

**Step 2: Create record page**

```python
# frontend/pages/record.py
import streamlit as st
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
import api_client


def render():
    st.header("Record from Microphone")
    st.caption("Click the microphone to start recording. Click again to stop.")

    audio_value = st.audio_input("Sing or play your melody")

    if audio_value is not None:
        st.audio(audio_value)  # preview the recording
        if st.button("Process Recording"):
            with st.spinner("Uploading to backend..."):
                try:
                    result = api_client.record_audio(audio_value.read(), "recording.wav")
                    st.session_state["track_id"] = result["track_id"]
                    st.success(
                        f"Recording processed — {result['duration_sec']:.1f}s. "
                        "Switch to the Editor tab."
                    )
                except Exception as e:
                    st.error(f"Failed: {e}")
```

**Step 3: Add Record tab to app.py**

```python
# frontend/app.py — replace with:
import streamlit as st

st.set_page_config(page_title="AI Music", layout="wide")
st.title("AI Music")

tab_record, tab_upload, tab_editor = st.tabs(["Record", "Upload", "Editor"])

with tab_record:
    from pages.record import render
    render()

with tab_upload:
    from pages.upload import render
    render()

with tab_editor:
    from pages.editor import render
    render()
```

**Step 4: Manual smoke test**

```bash
scripts/ctl restart frontend
```
Open `http://localhost:8501`. Go to Record tab. Record 5 seconds of humming. Click Process. Verify track_id appears and Editor tab shows waveform.

**Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: browser mic recording tab via st.audio_input"
```

---

## Task 3: Extend Integration Test

**Files:**
- Modify: `scripts/run_integration_test.sh`

Add a section that posts a WAV blob to `/audio/record` (simulating browser upload):

```bash
# append to run_integration_test.sh before final echo

echo "[5/5] Record endpoint..."
REC_RESPONSE=$(curl -sf -X POST "$BACKEND/audio/record" \
  -F "file=@$FIXTURE;type=audio/wav")
REC_TRACK=$(echo "$REC_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['track_id'])")
echo "      PASS — record track_id=$REC_TRACK"
```

```bash
scripts/ctl test integration
```
Expected: 5/5 PASS

```bash
git add scripts/run_integration_test.sh
git commit -m "test: extend integration test to cover /audio/record endpoint"
```

---

## Phase 2 Complete Checklist

- [ ] `ctl test unit` — all pass
- [ ] `ctl test integration` — 5/5 pass
- [ ] Record tab visible in browser
- [ ] Can record mic audio and see it in Editor tab
- [ ] Both Upload and Record paths produce the same Editor experience
