import os
import time
import uuid
import logging
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("hashverify")

app = FastAPI(
    title="Hash Verify",
    description="Client-side file hash verification tool",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Rate limiting ─────────────────────────────────────────────────
# Simple in-memory sliding window: max 60 requests per IP per minute.
# For multi-worker production, swap this for Redis.
_rate_store = defaultdict(list)
RATE_LIMIT = 60
RATE_WINDOW = 60


def check_rate(ip: str) -> bool:
    now = time.time()
    timestamps = _rate_store[ip]
    _rate_store[ip] = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(_rate_store[ip]) >= RATE_LIMIT:
        return False
    _rate_store[ip].append(now)
    return True


# ── Security headers middleware ───────────────────────────────────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"

    if not check_rate(ip):
        logger.warning("Rate limit hit — IP: %s", ip)
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please wait a moment."},
        )

    req_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000

    logger.info(
        "req_id=%s method=%s path=%s status=%s ip=%s duration=%.1fms",
        req_id, request.method, request.url.path,
        response.status_code, ip, elapsed,
    )

    # Security headers — defence in depth even though computation is client-side
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # CSP: allows Web Crypto (self), Google Fonts, no inline scripts except hashes
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; worker-src blob:; "
        "frame-ancestors 'none'"
    )
    return response


# ── Routes ────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    try:
        return HTMLResponse(content=open(html_path).read())
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Template not found")



@app.get("/tools", response_class=HTMLResponse)
async def tools(request: Request):
    html_path = os.path.join(os.path.dirname(__file__), "templates", "tools.html")
    try:
        return HTMLResponse(content=open(html_path).read())
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Template not found")


@app.get("/vakalatnama", response_class=HTMLResponse)
async def vakalatnama(request: Request):
    html_path = os.path.join(os.path.dirname(__file__), "templates", "vakalatnama.html")
    try:
        return HTMLResponse(content=open(html_path).read())
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Template not found")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "ts": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }




@app.get("/sitemap.xml")
async def sitemap():
    return HTMLResponse(
        content='''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://legalhashchecksum.com/</loc>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>''',
        media_type="application/xml",
    )

@app.get("/google75decac8b13364d6.html")
async def google_verify():
    return HTMLResponse(
        content="google-site-verification: google75decac8b13364d6.html",
        media_type="text/html",
    )

@app.get("/robots.txt")
async def robots():
    return HTMLResponse(
        content="User-agent: *\nAllow: /\nDisallow: /health\n",
        media_type="text/plain",
    )
