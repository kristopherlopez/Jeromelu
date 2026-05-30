from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .miner.routes import router as miner_router
from .routers.admin import router as admin_router
from .routers.ask import router as ask_router
from .routers.crew import router as crew_router
from .routers.feed import router as feed_router
from .routers.insights import router as insights_router
from .routers.lineup import router as lineup_router
from .routers.players import router as players_router
from .routers.presenters import router as presenters_router
from .routers.recon import router as recon_router
from .routers.sources import router as sources_router
from .routers.squad import router as squad_router
from .routers.teams import router as teams_router
from .routers.wiki import router as wiki_router

app = FastAPI(title="Jeromelu API", version="0.3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources_router, prefix="/api")
# Lineup (speaker identification) — legacy in-repo surface, slated to move
# behind an external API. See memory/project_lineup_external.md.
app.include_router(lineup_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(ask_router, prefix="/api")
app.include_router(crew_router, prefix="/api")
app.include_router(feed_router, prefix="/api")
app.include_router(insights_router, prefix="/api")
app.include_router(players_router, prefix="/api")
app.include_router(presenters_router, prefix="/api")
app.include_router(recon_router, prefix="/api")
app.include_router(squad_router, prefix="/api")
app.include_router(teams_router, prefix="/api")
app.include_router(wiki_router, prefix="/api")
# Miner pipelines — folder per pipeline per Miner charter D9
app.include_router(miner_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": "jeromelu-api"}
