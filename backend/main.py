from fastapi import FastAPI
from .api.routes import audio, midi

app = FastAPI(title="AI Music API", version="0.1.0")
app.include_router(audio.router)
app.include_router(midi.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
