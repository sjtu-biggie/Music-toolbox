import pytest
from pathlib import Path
from uuid import uuid4
from backend.services.midi_service import extract_midi, synthesize_midi, notes_to_midi
from backend.services.midi_service import _filter_short_notes, _merge_close_notes
from backend.models.schemas import Note
from backend.config import StaticConfig


def test_extract_midi_returns_notes(sample_wav_path, isolated_dirs):
    midi_path = isolated_dirs / "out.mid"
    notes = extract_midi(sample_wav_path, midi_path, track_id=uuid4())
    assert midi_path.exists()
    assert isinstance(notes, list)
    assert len(notes) >= 1
    assert all(isinstance(n, Note) for n in notes)
    assert all(0 <= n.pitch_midi <= 127 for n in notes)


def test_synthesize_midi_produces_wav_at_canonical_rate(sample_mid_path, isolated_dirs):
    import soundfile as sf
    out_wav = isolated_dirs / "synth.wav"
    synthesize_midi(sample_mid_path, out_wav)
    assert out_wav.exists()
    assert out_wav.stat().st_size > 0
    _, sr = sf.read(str(out_wav))
    assert sr == StaticConfig.INTERNAL_SAMPLE_RATE


def test_notes_to_midi_roundtrip(isolated_dirs):
    track_id = uuid4()
    notes = [
        Note(track_id=track_id, pitch_midi=60, start_sec=0.0, end_sec=0.5, velocity=80),
        Note(track_id=track_id, pitch_midi=64, start_sec=0.5, end_sec=1.0, velocity=80),
    ]
    midi_path = isolated_dirs / "roundtrip.mid"
    notes_to_midi(notes, midi_path)
    assert midi_path.exists()
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    pitches = [n.pitch for inst in pm.instruments for n in inst.notes]
    assert 60 in pitches
    assert 64 in pitches


def _make_note(pitch=60, start=0.0, end=0.5, velocity=80):
    return Note(track_id=uuid4(), pitch_midi=pitch, start_sec=start, end_sec=end, velocity=velocity)


def test_filter_short_notes_removes_tiny():
    notes = [_make_note(start=0.0, end=0.05), _make_note(start=1.0, end=1.5)]
    result = _filter_short_notes(notes, 0.08)
    assert len(result) == 1
    assert result[0].start_sec == 1.0


def test_filter_short_notes_keeps_long():
    notes = [_make_note(start=0.0, end=0.5), _make_note(start=1.0, end=2.0)]
    result = _filter_short_notes(notes, 0.08)
    assert len(result) == 2


def test_merge_close_notes_merges_same_pitch():
    notes = [
        _make_note(pitch=60, start=0.0, end=0.5, velocity=80),
        _make_note(pitch=60, start=0.6, end=1.0, velocity=90),  # gap=0.1 < 0.15
    ]
    result = _merge_close_notes(notes, 0.15)
    assert len(result) == 1
    assert result[0].start_sec == 0.0
    assert result[0].end_sec == 1.0
    assert result[0].velocity == 90  # keeps higher


def test_merge_close_notes_does_not_merge_different_pitch():
    notes = [
        _make_note(pitch=60, start=0.0, end=0.5),
        _make_note(pitch=62, start=0.6, end=1.0),
    ]
    result = _merge_close_notes(notes, 0.15)
    assert len(result) == 2


def test_merge_close_notes_does_not_merge_large_gap():
    notes = [
        _make_note(pitch=60, start=0.0, end=0.5),
        _make_note(pitch=60, start=1.0, end=1.5),  # gap=0.5 > 0.15
    ]
    result = _merge_close_notes(notes, 0.15)
    assert len(result) == 2


def test_merge_empty_list():
    assert _merge_close_notes([], 0.15) == []
