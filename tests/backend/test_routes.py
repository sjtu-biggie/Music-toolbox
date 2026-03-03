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
async def test_upload_returns_track_id_and_name(client, wav_bytes):
    resp = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        data={"name": "My Test Track"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "track_id" in data
    assert data["name"] == "My Test Track"
    assert data["duration_sec"] > 0


@pytest.mark.anyio
async def test_upload_rejects_empty_name(client, wav_bytes):
    resp = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        data={"name": "   "},
    )
    assert resp.status_code == 400
    assert "name" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_upload_rejects_missing_name(client, wav_bytes):
    resp = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_waveform_returns_arrays(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        data={"name": "Waveform Test"},
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
        data={"name": "Playback Test"},
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
        data={"name": "Bad Format"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_record_accepts_audio_blob_with_name(client, wav_bytes):
    resp = await client.post(
        "/audio/record",
        files={"file": ("recording.wav", wav_bytes, "audio/wav")},
        data={"name": "My Recording"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "track_id" in data
    assert data["name"] == "My Recording"
    assert data["duration_sec"] > 0
    assert data["sample_rate"] > 0


@pytest.mark.anyio
async def test_record_rejects_whitespace_name(client, wav_bytes):
    resp = await client.post(
        "/audio/record",
        files={"file": ("recording.wav", wav_bytes, "audio/wav")},
        data={"name": "   "},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_record_rejects_missing_name(client, wav_bytes):
    resp = await client.post(
        "/audio/record",
        files={"file": ("recording.wav", wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_synthesize_returns_correct_playback_url(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        data={"name": "Synth Test"},
    )
    track_id = upload.json()["track_id"]
    # Extract MIDI first
    await client.post(f"/midi/{track_id}/extract")
    # Synthesize
    resp = await client.post(f"/midi/{track_id}/synthesize")
    assert resp.status_code == 200
    data = resp.json()
    assert data["playback_url"].startswith("/midi/")
    assert data["instrument"] == "piano"


@pytest.mark.anyio
async def test_synthesize_with_instrument(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        data={"name": "Instrument Test"},
    )
    track_id = upload.json()["track_id"]
    await client.post(f"/midi/{track_id}/extract")
    resp = await client.post(f"/midi/{track_id}/synthesize?instrument=violin")
    assert resp.status_code == 200
    assert resp.json()["instrument"] == "violin"


@pytest.mark.anyio
async def test_synthesize_rejects_unknown_instrument(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        data={"name": "Bad Instrument"},
    )
    track_id = upload.json()["track_id"]
    await client.post(f"/midi/{track_id}/extract")
    resp = await client.post(f"/midi/{track_id}/synthesize?instrument=kazoo")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_instruments_list(client):
    resp = await client.get("/midi/instruments/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "instruments" in data
    assert "piano" in data["instruments"]
    assert data["default"] == "piano"


@pytest.mark.anyio
async def test_region_pitch_shift(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("t.wav", wav_bytes, "audio/wav")},
        data={"name": "Region Test"},
    )
    tid = upload.json()["track_id"]
    await client.post(f"/midi/{tid}/extract")

    resp = await client.put(f"/midi/{tid}/region", json={
        "start_sec": 0.0, "end_sec": 10.0, "pitch_shift": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "notes" in data


@pytest.mark.anyio
async def test_region_playback_streams_audio(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("t.wav", wav_bytes, "audio/wav")},
        data={"name": "Region Playback Test"},
    )
    tid = upload.json()["track_id"]
    resp = await client.get(f"/audio/{tid}/region?start_sec=0.0&end_sec=1.0")
    assert resp.status_code == 200
    assert "audio" in resp.headers["content-type"]
