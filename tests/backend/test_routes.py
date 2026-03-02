import pytest
import io
import soundfile as sf
import numpy as np
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.config import StaticConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(isolated_dirs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def wav_bytes():
    buf = io.BytesIO()
    sr = 22050
    audio = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, sr))
    sf.write(buf, audio, sr, format="WAV")
    buf.seek(0)
    return buf.read()


@pytest.mark.anyio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.anyio
async def test_upload_returns_track_id(client, wav_bytes):
    resp = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "track_id" in data
    assert data["duration_sec"] > 0


@pytest.mark.anyio
async def test_waveform_returns_arrays(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    track_id = upload.json()["track_id"]
    resp = await client.get(f"/audio/{track_id}/waveform")
    assert resp.status_code == 200
    data = resp.json()
    assert "times" in data and "amplitudes" in data
    assert len(data["times"]) > 0


@pytest.mark.anyio
async def test_playback_streams_audio(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    track_id = upload.json()["track_id"]
    resp = await client.get(f"/audio/{track_id}/playback")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"


@pytest.mark.anyio
async def test_upload_rejects_bad_format(client):
    resp = await client.post(
        "/audio/upload",
        files={"file": ("test.xyz", b"garbage", "application/octet-stream")},
    )
    assert resp.status_code == 400


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
