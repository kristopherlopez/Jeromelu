from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.admin import router as admin_router
from .routers.sources import router as sources_router

app = FastAPI(title="Jeromelu API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": "jeromelu-api"}
