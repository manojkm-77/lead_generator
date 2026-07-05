import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import init_db
from backend.api.routes import router
from backend.api.crm_routes import router as crm_router
from backend.api.intelligence_routes import router as intel_router
from backend.infrastructure.redis import get_redis, close_redis
from backend.infrastructure.sse import get_sse_publisher
from backend.infrastructure.worker import DiscoveryWorker
from backend.infrastructure.registry import set_worker

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await get_redis()

    worker = DiscoveryWorker(
        concurrency=settings.worker_concurrency,
        poll_interval=settings.worker_poll_interval,
        batch_size=settings.worker_queue_batch_size,
    )
    set_worker(worker)
    await worker.start()
    logger = logging.getLogger(__name__)
    logger.info("Infrastructure initialized (worker pool=%d)", settings.worker_concurrency)
    yield
    w = worker
    set_worker(None)
    if w:
        await w.stop()
    await close_redis()
    logger.info("Infrastructure shut down")


app = FastAPI(
    title="BuyerHunter AI",
    description="Edible Oil Buyer Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(router, prefix="/api")
app.include_router(crm_router, prefix="/api")
app.include_router(intel_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "BuyerHunter AI", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
