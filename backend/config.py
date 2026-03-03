from pathlib import Path


class StaticConfig:
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173

    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    TRACKS_DIR: Path = DATA_DIR / "tracks"
    AUDIO_DIR: Path = DATA_DIR / "audio"
    MIDI_DIR: Path = DATA_DIR / "midi"
    JOBS_DIR: Path = DATA_DIR / "jobs"

    SOUNDFONT_PATH: Path = BASE_DIR / "assets" / "soundfonts" / "GeneralUser.sf2"
    INTERNAL_SAMPLE_RATE: int = 22050
    FLUIDSYNTH_SAMPLE_RATE: int = 22050
    SPLICE_CROSSFADE_MS: int = 80
    WAVEFORM_MAX_POINTS: int = 1000
    AI_CONTEXT_SECONDS: float = 10.0

    REPLICATE_API_TOKEN: str = ""

    # General MIDI program numbers for available instruments
    INSTRUMENTS: dict[str, int] = {
        "piano": 0,
        "violin": 40,
        "cello": 42,
        "flute": 73,
        "acoustic guitar": 25,
        "electric guitar": 27,
        "trumpet": 56,
        "clarinet": 71,
        "organ": 19,
        "strings ensemble": 48,
    }
    DEFAULT_INSTRUMENT: str = "piano"

    @classmethod
    def ensure_dirs(cls) -> None:
        for d in [cls.TRACKS_DIR, cls.AUDIO_DIR, cls.MIDI_DIR, cls.JOBS_DIR]:
            d.mkdir(parents=True, exist_ok=True)
