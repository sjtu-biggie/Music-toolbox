from pathlib import Path
from uuid import UUID, uuid4
import pretty_midi
from basic_pitch import ICASSP_2022_MODEL_PATH
from basic_pitch.inference import predict
from midi2audio import FluidSynth
from ..config import StaticConfig
from ..models.schemas import Note

# Use ONNX model: the default TF saved model may be incompatible with
# the installed TensorFlow version, whereas the ONNX model works reliably.
_ONNX_MODEL_PATH = ICASSP_2022_MODEL_PATH.parent / (
    ICASSP_2022_MODEL_PATH.name + ".onnx"
)


def _filter_short_notes(notes: list[Note], min_dur: float) -> list[Note]:
    """Remove notes shorter than min_dur seconds."""
    return [n for n in notes if (n.end_sec - n.start_sec) >= min_dur]


def _merge_close_notes(notes: list[Note], gap_sec: float) -> list[Note]:
    """Merge consecutive same-pitch notes separated by less than gap_sec."""
    if not notes:
        return notes
    sorted_notes = sorted(notes, key=lambda n: (n.pitch_midi, n.start_sec))
    merged: list[Note] = [sorted_notes[0].model_copy()]
    for note in sorted_notes[1:]:
        prev = merged[-1]
        if note.pitch_midi == prev.pitch_midi and (note.start_sec - prev.end_sec) < gap_sec:
            # Merge: extend prev to cover both, keep higher velocity
            merged[-1] = prev.model_copy(update={
                "end_sec": max(prev.end_sec, note.end_sec),
                "velocity": max(prev.velocity, note.velocity),
            })
        else:
            merged.append(note.model_copy())
    return merged


def extract_midi(audio_path: Path, midi_path: Path, track_id: UUID) -> list[Note]:
    _model_output, midi_data, _note_events = predict(
        str(audio_path),
        model_or_model_path=_ONNX_MODEL_PATH,
        onset_threshold=StaticConfig.MIDI_ONSET_THRESHOLD,
        frame_threshold=StaticConfig.MIDI_FRAME_THRESHOLD,
        minimum_note_length=StaticConfig.MIDI_MIN_NOTE_LENGTH_MS,
        minimum_frequency=StaticConfig.MIDI_MIN_FREQUENCY,
        maximum_frequency=StaticConfig.MIDI_MAX_FREQUENCY,
    )
    midi_data.write(str(midi_path))
    notes = []
    for instrument in midi_data.instruments:
        for note in instrument.notes:
            notes.append(Note(
                id=uuid4(),
                track_id=track_id,
                pitch_midi=note.pitch,
                start_sec=float(note.start),
                end_sec=float(note.end),
                velocity=int(note.velocity),
            ))
    notes = _filter_short_notes(notes, StaticConfig.MIN_NOTE_SEC)
    notes = _merge_close_notes(notes, StaticConfig.MERGE_GAP_SEC)
    return notes


def synthesize_midi(midi_path: Path, audio_path: Path) -> None:
    fs = FluidSynth(
        str(StaticConfig.SOUNDFONT_PATH),
        sample_rate=StaticConfig.FLUIDSYNTH_SAMPLE_RATE,
    )
    fs.midi_to_audio(str(midi_path), str(audio_path))


def notes_to_midi(notes: list[Note], midi_path: Path, tempo: float = 120.0, program: int = 0) -> None:
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    instrument = pretty_midi.Instrument(program=program)
    for note in sorted(notes, key=lambda n: n.start_sec):
        instrument.notes.append(pretty_midi.Note(
            velocity=note.velocity,
            pitch=note.pitch_midi,
            start=note.start_sec,
            end=note.end_sec,
        ))
    pm.instruments.append(instrument)
    pm.write(str(midi_path))
