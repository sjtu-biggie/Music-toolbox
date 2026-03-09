from uuid import uuid4
from backend.models.schemas import Note
from backend.services.edit_service import (
    shift_pitch,
    shift_timing,
    notes_in_region,
    apply_pitch_shift_to_region,
    apply_timing_shift_to_region,
)


def _note(pitch=60, start=0.0, end=0.5) -> Note:
    return Note(track_id=uuid4(), pitch_midi=pitch, start_sec=start, end_sec=end, velocity=80)


def test_shift_pitch_clamps_to_valid_midi():
    note = _note(pitch=126)
    result = shift_pitch(note, semitones=5)
    assert result.pitch_midi == 127  # clamped


def test_shift_pitch_negative():
    note = _note(pitch=60)
    result = shift_pitch(note, semitones=-3)
    assert result.pitch_midi == 57


def test_shift_timing_moves_note():
    note = _note(start=1.0, end=1.5)
    result = shift_timing(note, delta_sec=0.5)
    assert abs(result.start_sec - 1.5) < 0.001
    assert abs(result.end_sec - 2.0) < 0.001


def test_notes_in_region_filters_correctly():
    notes = [_note(start=0.0, end=0.5), _note(start=1.0, end=1.5), _note(start=2.0, end=2.5)]
    result = notes_in_region(notes, start_sec=0.8, end_sec=1.8)
    assert len(result) == 1
    assert result[0].start_sec == 1.0


def test_apply_pitch_shift_to_region():
    notes = [_note(pitch=60, start=0.0, end=0.5), _note(pitch=62, start=1.0, end=1.5)]
    result = apply_pitch_shift_to_region(notes, start_sec=0.8, end_sec=1.8, semitones=2)
    pitches = {n.start_sec: n.pitch_midi for n in result}
    assert pitches[0.0] == 60   # outside region, unchanged
    assert pitches[1.0] == 64   # inside region, shifted +2


def test_apply_timing_shift_to_region():
    notes = [_note(start=0.0, end=0.5), _note(start=1.0, end=1.5)]
    result = apply_timing_shift_to_region(notes, start_sec=0.8, end_sec=1.8, delta_sec=0.5)
    starts = {round(n.start_sec, 3): round(n.end_sec, 3) for n in result}
    assert starts[0.0] == 0.5    # outside region, unchanged
    assert starts[1.5] == 2.0    # inside region, shifted +0.5


def test_apply_timing_shift_to_region_clamps_to_zero():
    notes = [_note(start=0.1, end=0.5)]
    result = apply_timing_shift_to_region(notes, start_sec=0.0, end_sec=1.0, delta_sec=-0.5)
    assert result[0].start_sec == 0.0  # clamped to 0
    assert result[0].end_sec >= result[0].start_sec + 0.01  # min duration preserved
