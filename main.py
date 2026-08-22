import os

# Load .env file
import pathlib as _pl
_env_file = _pl.Path(__file__).parent / '.env'
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())
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
        "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self' https://www.google-analytics.com https://static.cloudflareinsights.com; worker-src blob:; "
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


@app.get("/memo-appearance", response_class=HTMLResponse)
async def memo_appearance(request: Request):
    html_path = os.path.join(os.path.dirname(__file__), "templates", "memo-appearance.html")
    try:
        return HTMLResponse(content=open(html_path).read())
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Template not found")

@app.get("/bail-bond", response_class=HTMLResponse)
async def bail_bond(request: Request):
    html_path = os.path.join(os.path.dirname(__file__), "templates", "bail-bond.html")
    try:
        return HTMLResponse(content=open(html_path).read())
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Template not found")


@app.get("/bns-lookup", response_class=HTMLResponse)
async def bns_lookup(request: Request):
    p = os.path.join(os.path.dirname(__file__), "templates", "bns-lookup.html")
    return HTMLResponse(content=open(p).read())

@app.get("/limitation-calculator", response_class=HTMLResponse)
async def limitation_calculator(request: Request):
    p = os.path.join(os.path.dirname(__file__), "templates", "limitation-calculator.html")
    return HTMLResponse(content=open(p).read())

@app.get("/court-fee", response_class=HTMLResponse)
async def court_fee(request: Request):
    p = os.path.join(os.path.dirname(__file__), "templates", "court-fee.html")
    return HTMLResponse(content=open(p).read())


@app.get("/legal-notice", response_class=HTMLResponse)
async def legal_notice(request: Request):
    p = os.path.join(os.path.dirname(__file__), "templates", "legal-notice.html")
    try:
        return HTMLResponse(content=open(p).read())
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Template not found")


@app.get("/law-converter", response_class=HTMLResponse)
async def law_converter(request: Request):
    p = os.path.join(os.path.dirname(__file__), "templates", "law-converter.html")
    return HTMLResponse(content=open(p).read())

@app.get("/legal-dictionary", response_class=HTMLResponse)
async def legal_dictionary(request: Request):
    p = os.path.join(os.path.dirname(__file__), "templates", "legal-dictionary.html")
    return HTMLResponse(content=open(p).read())


@app.get("/women-children-law", response_class=HTMLResponse)
async def women_children_law(request: Request):
    p = os.path.join(os.path.dirname(__file__), "templates", "women-children-law.html")
    try:
        return HTMLResponse(content=open(p).read())
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Template not found")


@app.get("/legal-notice-custom", response_class=HTMLResponse)
async def legal_notice_custom(request: Request):
    p = os.path.join(os.path.dirname(__file__), "templates", "legal-notice-custom.html")
    return HTMLResponse(content=open(p).read())


import smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pydantic import BaseModel

class FeedbackForm(BaseModel):
    type: str
    page: str
    message: str
    email: str = ""
    url: str = ""

@app.post("/feedback")
async def submit_feedback(data: FeedbackForm):
    try:
        gmail_user = os.getenv("GMAIL_USER", "umangmathpal@gmail.com")
        gmail_pass = os.getenv("GMAIL_PASS", "")
        to_email   = os.getenv("FEEDBACK_TO", "umangmathpal@gmail.com")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[LegalHashChecksum] {data.type} — {data.page}"
        msg["From"]    = f"LegalHashChecksum <{gmail_user}>"
        msg["To"]      = to_email

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <div style="background:#2563EB;padding:16px 24px;border-radius:12px 12px 0 0">
            <h2 style="color:#fff;margin:0;font-size:18px">[LegalHashChecksum] Feedback</h2>
          </div>
          <div style="background:#f9fafb;padding:24px;border:1px solid #e5e7eb;border-top:none">
            <table style="width:100%;border-collapse:collapse">
              <tr><td style="padding:8px 0;font-size:13px;color:#6b7280;width:120px"><strong>Type</strong></td><td style="padding:8px 0;font-size:14px;color:#111">{data.type}</td></tr>
              <tr><td style="padding:8px 0;font-size:13px;color:#6b7280"><strong>Page</strong></td><td style="padding:8px 0;font-size:14px;color:#111">{data.page}</td></tr>
              <tr><td style="padding:8px 0;font-size:13px;color:#6b7280"><strong>URL</strong></td><td style="padding:8px 0;font-size:14px;color:#2563EB"><a href="{data.url}">{data.url}</a></td></tr>
              <tr><td style="padding:8px 0;font-size:13px;color:#6b7280"><strong>Reply to</strong></td><td style="padding:8px 0;font-size:14px;color:#111">{data.email or "Not provided"}</td></tr>
            </table>
            <div style="margin-top:16px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px">
              <p style="font-size:13px;color:#6b7280;margin:0 0 8px"><strong>Message</strong></p>
              <p style="font-size:15px;color:#111;margin:0;line-height:1.6;white-space:pre-wrap">{data.message}</p>
            </div>
          </div>
          <div style="background:#f3f4f6;padding:12px 24px;border-radius:0 0 12px 12px;border:1px solid #e5e7eb;border-top:none">
            <p style="font-size:12px;color:#9ca3af;margin:0">Sent from legalhashchecksum.com feedback widget</p>
          </div>
        </div>"""

        msg.attach(MIMEText(html, "html"))

        # If reply email provided, set Reply-To
        if data.email:
            msg["Reply-To"] = data.email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, to_email, msg.as_string())

        return {"ok": True}
    except Exception as e:
        print(f"Feedback email error: {e}")
        return {"ok": False, "error": str(e)}






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


# ══════════════════════════════════════════════════════
#  LEGAL Q&A — PostgreSQL backend
# ══════════════════════════════════════════════════════
import asyncpg
from typing import Optional
from pydantic import BaseModel as PydanticBase

QA_DB_URL = os.environ.get("QA_DATABASE_URL",
    "postgresql://legalqa_user:legalqa_pass_2026@localhost:5432/legalqa")

class QuestionIn(PydanticBase):
    question: str
    category: str = "General"
    asker_name: str = "Anonymous"
    anonymous: bool = True

class AnswerIn(PydanticBase):
    question_id: int
    answer: str
    advocate_name: str
    advocate_enroll: Optional[str] = ""
    advocate_court: Optional[str] = ""

@app.get("/legal-qa")
async def qa_page():
    p = os.path.join(os.path.dirname(__file__), "templates", "legal-qa.html")
    return HTMLResponse(content=open(p).read())

@app.get("/api/qa/questions")
async def get_questions():
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        rows = await conn.fetch("""
            SELECT q.id, q.question, q.category, q.asker_name, q.anonymous,
                   q.created_at::text, q.views, COUNT(a.id)::int AS answer_count
            FROM legal_questions q
            LEFT JOIN legal_answers a ON a.question_id = q.id
            GROUP BY q.id ORDER BY q.created_at DESC LIMIT 100
        """)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

@app.post("/api/qa/questions")
async def post_question(q: QuestionIn):
    if len(q.question.strip()) < 10:
        raise HTTPException(400, "Question too short")
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        await conn.execute("""
            INSERT INTO legal_questions (question, category, asker_name, anonymous)
            VALUES ($1,$2,$3,$4)
        """, q.question.strip(), q.category, q.asker_name or "Anonymous", q.anonymous)
        return {"ok": True}
    finally:
        await conn.close()

@app.get("/api/qa/answers/{qid}")
async def get_answers(qid: int):
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        rows = await conn.fetch("""
            SELECT id, question_id, answer, advocate_name, advocate_enroll,
                   advocate_court, created_at::text, upvotes
            FROM legal_answers WHERE question_id=$1
            ORDER BY upvotes DESC, created_at ASC
        """, qid)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

@app.post("/api/qa/answers")
async def post_answer(a: AnswerIn):
    if len(a.answer.strip()) < 20:
        raise HTTPException(400, "Answer too short")
    if not a.advocate_name.strip():
        raise HTTPException(400, "Advocate name required")
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        await conn.execute("""
            INSERT INTO legal_answers
              (question_id, answer, advocate_name, advocate_enroll, advocate_court)
            VALUES ($1,$2,$3,$4,$5)
        """, a.question_id, a.answer.strip(), a.advocate_name.strip(),
             a.advocate_enroll or "", a.advocate_court or "")
        return {"ok": True}
    finally:
        await conn.close()

@app.post("/api/qa/view/{qid}")
async def increment_view(qid: int):
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        await conn.execute(
            "UPDATE legal_questions SET views=views+1 WHERE id=$1", qid)
        return {"ok": True}
    finally:
        await conn.close()

@app.post("/api/qa/upvote/{aid}")
async def upvote_answer(aid: int):
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        row = await conn.fetchrow("""
            UPDATE legal_answers SET upvotes=upvotes+1
            WHERE id=$1 RETURNING upvotes
        """, aid)
        return {"upvotes": row["upvotes"]}
    finally:
        await conn.close()
