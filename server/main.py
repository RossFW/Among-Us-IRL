"""Among Us IRL - PWA Server.

A Progressive Web App for playing Among Us in real life.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path

from .routes import lobby, game, websocket

# Get the project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="Among Us IRL",
    description="Real-life Among Us game companion",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Set up templates
templates = Jinja2Templates(directory=BASE_DIR / "server" / "templates")

# Include API routes
app.include_router(lobby.router)
app.include_router(game.router)
app.include_router(websocket.router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the home page."""
    return templates.TemplateResponse("pages/home.html", {"request": request})


@app.get("/game/{code}", response_class=HTMLResponse)
async def game_page(request: Request, code: str):
    """Serve the game page."""
    return templates.TemplateResponse("pages/game.html", {"request": request, "code": code})


@app.get("/manifest.json")
async def manifest():
    """Serve the PWA manifest."""
    return {
        "name": "Among Us IRL",
        "short_name": "Among Us",
        "description": "Real-life Among Us game companion",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1a1a2e",
        "theme_color": "#e94560",
        "icons": [
            {
                "src": "/static/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
