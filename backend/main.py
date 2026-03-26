import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .config import StaticConfig
from .models.schemas import AIJob
from .api.routes import audio, midi, ai

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs_dir = StaticConfig.JOBS_DIR
    if jobs_dir.exists():
        for job_file in jobs_dir.glob("*.json"):
            try:
                job = AIJob.model_validate_json(job_file.read_text())
                if job.status == "running":
                    job.status = "failed"
                    job.error_msg = "Server restarted"
                    job_file.write_text(job.model_dump_json())
                    logger.info("Reset stale job %s to failed", job.id)
            except Exception as exc:
                logger.warning("Skipping corrupt job file %s: %s", job_file.name, exc)
    yield


app = FastAPI(title="AI Music API", version="0.1.0", lifespan=lifespan)
app.include_router(audio.router)
app.include_router(midi.router)
app.include_router(ai.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
