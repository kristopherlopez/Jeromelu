from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.admin import router as admin_router
from .routers.ask import router as ask_router
from .routers.crew import router as crew_router
from .routers.feed import router as feed_router
from .routers.sources import router as sources_router
from .routers.squad import router as squad_router

app = FastAPI(title="Jeromelu API", version="0.3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(ask_router, prefix="/api")
app.include_router(crew_router, prefix="/api")
app.include_router(feed_router, prefix="/api")
app.include_router(squad_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": "jeromelu-api"}
