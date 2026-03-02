import httpx

BACKEND_URL = "http://localhost:8000"
_client = httpx.Client(base_url=BACKEND_URL, timeout=120.0)


def upload_audio(file_bytes: bytes, filename: str) -> dict:
    resp = _client.post("/audio/upload", files={"file": (filename, file_bytes, "audio/wav")})
    resp.raise_for_status()
    return resp.json()


def record_audio(audio_bytes: bytes, filename: str = "recording.wav") -> dict:
    resp = _client.post(
        "/audio/record",
        files={"file": (filename, audio_bytes, "audio/wav")},
    )
    resp.raise_for_status()
    return resp.json()


def get_waveform(track_id: str) -> dict:
    resp = _client.get(f"/audio/{track_id}/waveform")
    resp.raise_for_status()
    return resp.json()


def get_playback_url(track_id: str) -> str:
    return f"{BACKEND_URL}/audio/{track_id}/playback"


def extract_midi(track_id: str) -> dict:
    resp = _client.post(f"/midi/{track_id}/extract", timeout=120.0)
    resp.raise_for_status()
    return resp.json()


def get_notes(track_id: str) -> dict:
    resp = _client.get(f"/midi/{track_id}")
    resp.raise_for_status()
    return resp.json()


def update_note(track_id: str, note_id: str, payload: dict) -> dict:
    resp = _client.put(f"/midi/{track_id}/notes/{note_id}", json=payload)
    resp.raise_for_status()
    return resp.json()


def synthesize(track_id: str, instrument: str = "piano") -> dict:
    resp = _client.post(f"/midi/{track_id}/synthesize", params={"instrument": instrument}, timeout=120.0)
    resp.raise_for_status()
    return resp.json()


def list_instruments() -> dict:
    resp = _client.get("/midi/instruments/list")
    resp.raise_for_status()
    return resp.json()


def get_synth_playback_url(track_id: str) -> str:
    return f"{BACKEND_URL}/midi/{track_id}/playback"


def get_playback_bytes(track_id: str) -> bytes | None:
    resp = _client.get(f"/audio/{track_id}/playback")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content


def get_synth_playback_bytes(track_id: str) -> bytes | None:
    resp = _client.get(f"/midi/{track_id}/playback")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content
