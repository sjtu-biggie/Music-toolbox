from ..models.schemas import Note


def shift_pitch(note: Note, semitones: int) -> Note:
    new_pitch = max(0, min(127, note.pitch_midi + semitones))
    return note.model_copy(update={"pitch_midi": new_pitch})


def shift_timing(note: Note, delta_sec: float) -> Note:
    new_start = max(0.0, note.start_sec + delta_sec)
    new_end = max(new_start + 0.01, note.end_sec + delta_sec)
    return note.model_copy(update={"start_sec": new_start, "end_sec": new_end})


def notes_in_region(notes: list[Note], start_sec: float, end_sec: float) -> list[Note]:
    return [n for n in notes if n.start_sec >= start_sec and n.end_sec <= end_sec]


def apply_pitch_shift_to_region(
    notes: list[Note], start_sec: float, end_sec: float, semitones: int
) -> list[Note]:
    return [
        shift_pitch(n, semitones) if start_sec <= n.start_sec and n.end_sec <= end_sec else n
        for n in notes
    ]


def apply_timing_shift_to_region(
    notes: list[Note], start_sec: float, end_sec: float, delta_sec: float
) -> list[Note]:
    return [
        shift_timing(n, delta_sec) if start_sec <= n.start_sec and n.end_sec <= end_sec else n
        for n in notes
    ]
