from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qdata.core.config import settings
from qdata.web.routes import auth, analyze, reports, rules, synthetic, scheduler as scheduler_router, upload, processes, datasources, sources, groups, admin
from qdata.scheduler.service import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.env != "test":
        start_scheduler()
    yield
    if settings.env != "test":
        stop_scheduler()


app = FastAPI(
    title="QData API",
    description="Sistema de Análisis de Calidad de Datos",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(analyze.router, prefix="/analyze", tags=["Analyze"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(rules.router, prefix="/rules", tags=["Rules"])
app.include_router(synthetic.router, prefix="/synthetic", tags=["Synthetic"])
app.include_router(scheduler_router.router, prefix="/scheduler", tags=["Scheduler"])
app.include_router(upload.router, prefix="/upload", tags=["Upload"])
app.include_router(processes.router, prefix="/processes", tags=["Processes"])
app.include_router(datasources.router, prefix="/datasources", tags=["DataSources"])
app.include_router(sources.router, prefix="/sources", tags=["Sources"])
app.include_router(groups.router, prefix="/api", tags=["Groups"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
