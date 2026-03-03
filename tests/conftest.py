import sys
from pathlib import Path as _Path
from unittest.mock import MagicMock

# Mock basic_pitch (ONNX model not available in CI/test)
_bp_mock = MagicMock()
_bp_mock.ICASSP_2022_MODEL_PATH = _Path("/mock/model")
sys.modules.setdefault("basic_pitch", _bp_mock)

# predict() must return a 3-tuple: (model_output, midi_data, note_events)
import pretty_midi as _pm
_dummy_midi = _pm.PrettyMIDI(initial_tempo=120.0)
_inst = _pm.Instrument(program=0)
_inst.notes.append(_pm.Note(velocity=80, pitch=60, start=0.0, end=0.5))
_dummy_midi.instruments.append(_inst)
sys.modules.setdefault(
    "basic_pitch.inference",
    MagicMock(predict=MagicMock(return_value=(None, _dummy_midi, None))),
)

import numpy as np
import soundfile as sf
import pretty_midi
import pytest
from pathlib import Path
from backend.config import StaticConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _make_sample_wav() -> Path:
    path = FIXTURES_DIR / "sample.wav"
    if path.exists():
        return path
    sr = 22050
    t = np.linspace(0, 3.0, int(sr * 3.0))
    audio = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    sf.write(str(path), audio, sr)
    return path


def _make_sample_mid() -> Path:
    path = FIXTURES_DIR / "sample.mid"
    if path.exists():
        return path
    pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    inst = pretty_midi.Instrument(program=0)
    inst.notes.append(pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=0.5))
    inst.notes.append(pretty_midi.Note(velocity=80, pitch=62, start=0.5, end=1.0))
    pm.instruments.append(inst)
    pm.write(str(path))
    return path


@pytest.fixture(scope="session", autouse=True)
def generate_fixtures():
    FIXTURES_DIR.mkdir(exist_ok=True)
    _make_sample_wav()
    _make_sample_mid()


@pytest.fixture
def sample_wav_path() -> Path:
    return FIXTURES_DIR / "sample.wav"


@pytest.fixture
def sample_mid_path() -> Path:
    return FIXTURES_DIR / "sample.mid"


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect all data dirs to tmp_path for test isolation."""
    monkeypatch.setattr(StaticConfig, "TRACKS_DIR", tmp_path / "tracks")
    monkeypatch.setattr(StaticConfig, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(StaticConfig, "MIDI_DIR", tmp_path / "midi")
    monkeypatch.setattr(StaticConfig, "JOBS_DIR", tmp_path / "jobs")
    StaticConfig.ensure_dirs()
    return tmp_path
