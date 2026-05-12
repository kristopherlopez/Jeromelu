from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.admin import router as admin_router
from .routers.ask import router as ask_router
from .routers.crew import router as crew_router
from .routers.feed import router as feed_router
from .routers.insights import router as insights_router
from .routers.players import router as players_router
from .routers.presenters import router as presenters_router
from .routers.recon import router as recon_router
from .routers.sources import router as sources_router
from .routers.squad import router as squad_router
from .routers.teams import router as teams_router
from .routers.wiki import router as wiki_router
from .scout.nrlcom_casualty_ward import router as scout_nrlcom_casualty_ward_router
from .scout.nrlcom_draw import router as scout_nrlcom_draw_router
from .scout.nrlcom_ladder import router as scout_nrlcom_ladder_router
from .scout.nrlcom_match_centre import router as scout_nrlcom_match_centre_router
from .scout.nrlcom_players_roster import router as scout_nrlcom_players_roster_router
from .scout.nrlcom_stats import router as scout_nrlcom_stats_router
from .scout.supercoach_roster import router as scout_supercoach_roster_router
from .scout.supercoach_settings import router as scout_supercoach_settings_router
from .scout.supercoach_stats import router as scout_supercoach_stats_router
from .scout.supercoach_teams import router as scout_supercoach_teams_router

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
app.include_router(insights_router, prefix="/api")
app.include_router(players_router, prefix="/api")
app.include_router(presenters_router, prefix="/api")
app.include_router(recon_router, prefix="/api")
app.include_router(squad_router, prefix="/api")
app.include_router(teams_router, prefix="/api")
app.include_router(wiki_router, prefix="/api")
# Scout pipelines — folder per pipeline per Scout charter D9
app.include_router(scout_supercoach_roster_router, prefix="/api")
app.include_router(scout_supercoach_settings_router, prefix="/api")
app.include_router(scout_supercoach_stats_router, prefix="/api")
app.include_router(scout_supercoach_teams_router, prefix="/api")
app.include_router(scout_nrlcom_draw_router, prefix="/api")
app.include_router(scout_nrlcom_match_centre_router, prefix="/api")
app.include_router(scout_nrlcom_casualty_ward_router, prefix="/api")
app.include_router(scout_nrlcom_ladder_router, prefix="/api")
app.include_router(scout_nrlcom_stats_router, prefix="/api")
app.include_router(scout_nrlcom_players_roster_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": "jeromelu-api"}
