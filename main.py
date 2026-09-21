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

from fastapi.responses import FileResponse
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

@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    # Return a minimal 1x1 blue square ICO
    import base64
    ico_b64 = "AAABAAEAAQEAAAEAGAAsAAAAFgAAACgAAAABAAAAAgAAAAEAGAAAAAAAAAAAAMQOAADEDgAAAAAAAAAAAAD/AAAAAAA="
    ico_bytes = base64.b64decode(ico_b64)
    return Response(content=ico_bytes, media_type="image/x-icon")

@app.get("/favicon.svg", include_in_schema=False)
async def favicon_svg():
    return FileResponse("favicon.svg", media_type="image/svg+xml")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    try:
        return HTMLResponse(content=open(html_path).read())
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Template not found")

@app.get("/llms.txt", include_in_schema=False)
async def llms_text():
    return FileResponse("llms.txt", media_type="text/plain")

@app.get("/verify", response_class=HTMLResponse)
async def verify_portal(request: Request):
    html_path = os.path.join(os.path.dirname(__file__), "templates", "verify.html")
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

@app.get("/profile", response_class=HTMLResponse)
async def get_profile():
    with open("templates/profile.html", "r", encoding="utf-8") as f:
        return f.read()

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

@app.get("/stamp-generator", response_class=HTMLResponse)
async def stamp_generator(request: Request):
    html_path = os.path.join(os.path.dirname(__file__), "templates", "stamp-generator.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/stamp-generator", response_class=HTMLResponse)
async def stamp_generator(request: Request):
    html_path = os.path.join(os.path.dirname(__file__), "templates", "stamp-generator.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())

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

@app.get("/feedback", response_class=HTMLResponse, include_in_schema=False)
async def feedback_get(request: Request):
    """Redirect Googlebot away — this endpoint is POST only"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/tools", status_code=301)

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
        content="User-agent: *\nAllow: /\nDisallow: /health\nDisallow: /feedback\nDisallow: /api/\nDisallow: /admin-lhc-qa-panel\n",
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
        await pool.release(conn)

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
        await pool.release(conn)

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
        await pool.release(conn)

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
        await pool.release(conn)

@app.post("/api/qa/view/{qid}")
async def increment_view(qid: int):
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        await conn.execute(
            "UPDATE legal_questions SET views=views+1 WHERE id=$1", qid)
        return {"ok": True}
    finally:
        await pool.release(conn)

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
        await pool.release(conn)


# ══════════════════════════════════════════════════════
#  LEGAL Q&A — ADMIN PANEL
# ══════════════════════════════════════════════════════
import hmac, hashlib

ADMIN_PASSWORD = os.environ.get("QA_ADMIN_PASSWORD", "legaladmin2026")
ADMIN_TOKEN    = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

class AdminLogin(PydanticBase):
    password: str

def verify_admin(request: Request):
    token = request.headers.get("X-Admin-Token","")
    if token != ADMIN_TOKEN:
        raise HTTPException(403, "Unauthorized")

@app.get("/admin-lhc-qa-panel")
async def admin_page():
    p = os.path.join(os.path.dirname(__file__), "templates", "admin-qa.html")
    return HTMLResponse(content=open(p).read())

@app.post("/api/admin/qa/login")
async def admin_login(body: AdminLogin):
    if body.password == ADMIN_PASSWORD:
        return {"token": ADMIN_TOKEN}
    return {"error": "wrong password"}

@app.get("/api/admin/qa/questions")
async def admin_get_questions(request: Request):
    verify_admin(request)
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        rows = await conn.fetch("""
            SELECT q.id, q.question, q.category, q.asker_name, q.anonymous,
                   q.created_at::text, q.views, COUNT(a.id)::int AS answer_count
            FROM legal_questions q
            LEFT JOIN legal_answers a ON a.question_id = q.id
            GROUP BY q.id ORDER BY q.created_at DESC
        """)
        return [dict(r) for r in rows]
    finally:
        await pool.release(conn)

@app.get("/api/admin/qa/answers")
async def admin_get_answers(request: Request):
    verify_admin(request)
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        rows = await conn.fetch("""
            SELECT id, question_id, answer, advocate_name, advocate_enroll,
                   advocate_court, created_at::text, upvotes
            FROM legal_answers ORDER BY created_at DESC
        """)
        return [dict(r) for r in rows]
    finally:
        await pool.release(conn)

@app.delete("/api/admin/qa/questions/{qid}")
async def admin_delete_question(qid: int, request: Request):
    verify_admin(request)
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        await conn.execute("DELETE FROM legal_questions WHERE id=$1", qid)
        return {"ok": True}
    finally:
        await pool.release(conn)

@app.delete("/api/admin/qa/answers/{aid}")
async def admin_delete_answer(aid: int, request: Request):
    verify_admin(request)
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        await conn.execute("DELETE FROM legal_answers WHERE id=$1", aid)
        return {"ok": True}
    finally:
        await pool.release(conn)

class QuestionEdit(PydanticBase):
    question: str
    category: str
    asker_name: str

class AnswerEdit(PydanticBase):
    answer: str
    advocate_name: str
    advocate_enroll: Optional[str] = ""
    advocate_court: Optional[str] = ""

@app.patch("/api/admin/qa/questions/{qid}")
async def admin_edit_question(qid: int, body: QuestionEdit, request: Request):
    verify_admin(request)
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        await conn.execute("""
            UPDATE legal_questions
            SET question=$1, category=$2, asker_name=$3
            WHERE id=$4
        """, body.question.strip(), body.category, body.asker_name, qid)
        return {"ok": True}
    finally:
        await pool.release(conn)

@app.patch("/api/admin/qa/answers/{aid}")
async def admin_edit_answer(aid: int, body: AnswerEdit, request: Request):
    verify_admin(request)
    conn = await asyncpg.connect(QA_DB_URL)
    try:
        await conn.execute("""
            UPDATE legal_answers
            SET answer=$1, advocate_name=$2, advocate_enroll=$3, advocate_court=$4
            WHERE id=$5
        """, body.answer.strip(), body.advocate_name, body.advocate_enroll or "", body.advocate_court or "", aid)
        return {"ok": True}
    finally:
        await pool.release(conn)

@app.get("/cases", response_class=HTMLResponse)
async def get_cases():
    with open("templates/cases.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/alerts", response_class=HTMLResponse)
async def get_alerts():
    with open("templates/alerts.html", "r", encoding="utf-8") as f:
        return f.read()


# ── Judgments Module ─────────────────────────────────────────────────────────
JUDGMENT_DB_URL = "postgresql://legalqa_user:legalqa_pass_2026@localhost:5432/legalqa"

# Connection pool — reuse connections instead of new conn per request
_judgment_pool = None

async def get_judgment_pool():
    global _judgment_pool
    if _judgment_pool is None:
        _judgment_pool = await asyncpg.create_pool(
            JUDGMENT_DB_URL,
            min_size=2,
            max_size=8,
            command_timeout=10,
        )
    return _judgment_pool

VALID_AREAS  = ["criminal","civil","family","tax","constitutional","labour","ipr","general"]
VALID_COURTS = [
    # Normalised short names (2026 data)
    "Supreme Court","Delhi HC","Bombay HC","Calcutta HC","Madras HC",
    "Allahabad HC","Kerala HC","Gujarat HC","P&H HC","Rajasthan HC",
    "Karnataka HC","Patna HC","MP HC","Jharkhand HC",
    # Full names still in DB (2024/2025 data — trigger not yet active)
    "Supreme Court of India",
    "Delhi High Court","Bombay High Court","Calcutta High Court",
    "Madras High Court","Allahabad High Court","Kerala High Court",
    "Gujarat High Court","Karnataka High Court","Patna High Court",
    "Rajasthan High Court - Jodhpur","Punjab-Haryana High Court",
    "Madhya Pradesh High Court","Jharkhand High Court",
]

@app.get("/judgments", response_class=HTMLResponse)
async def get_judgments_page():
    p = os.path.join(os.path.dirname(__file__), "templates", "judgments.html")
    return HTMLResponse(content=open(p).read())

@app.get("/api/judgments")
async def api_judgments(
    area:   str = None,
    court:  str = None,
    days:   int = 7,
    year:   int = 0,
    q:      str = None,
    page:   int = 0,
    limit:  int = 18,
):
    """
    GET /api/judgments
    Params: area, court, days, year (0=off), q (search), page, limit
    Returns paginated deduplicated judgment list with total count.
    """
    import datetime
    limit = max(1, min(limit, 50))
    page  = max(0, page)

    # Validate inputs
    if area  and area  not in VALID_AREAS:  area  = None
    if court and court not in VALID_COURTS: court = None

    params = []
    i = 1
    conditions = []

    # Smart search: title + clean headnote + area inference
    if q and len(q.strip()) >= 2:
        qt = q.strip()
        # Strip IK citation prefix from headnote before matching
        # Use regexp_replace to skip [Cites N, Cited by N] prefix
        title_cond    = f"title ILIKE ${i}"
        headnote_cond = f"regexp_replace(headnote, '^\\[Cites[^\\]]+\\]\\s*', '', 'i') ILIKE ${i}"
        params.append(f"%{qt}%")
        i += 1

        # Keyword → practice area inference
        AREA_HINTS = {
            "criminal": ["bail","fir","arrest","murder","rape","robbery","cheque dishonour",
                         "section 302","section 376","section 420","section 138","ndps",
                         "pocso","uapa","conviction","acquittal","remand","chargesheet",
                         "anticipatory","custody","sentence","imprisonment","crpc","bnss"],
            "tax":      ["income tax","gst","customs","excise","itat","cestat","tds",
                         "capital gains","assessment","reassessment","tax evasion","dtaa"],
            "civil":    ["injunction","specific performance","decree","partition",
                         "eviction","land acquisition","arbitration","ibc","nclt","winding up"],
            "family":   ["divorce","maintenance","custody","matrimonial","adoption",
                         "succession","guardianship","dowry","stridhan","alimony"],
            "constitutional":["article 14","article 19","article 21","article 226","pil",
                              "fundamental rights","reservation","writ petition","habeas corpus"],
            "labour":   ["workman","retrenchment","gratuity","epfo","trade union",
                         "industrial dispute","regularisation","esic"],
            "ipr":      ["patent","trademark","copyright","passing off","infringement"],
        }
        ql = qt.lower()
        inferred_area = None
        for area_name, kws in AREA_HINTS.items():
            if any(kw in ql for kw in kws):
                inferred_area = area_name
                break

        if inferred_area and not area:
            # Search title+headnote OR inferred area
            area_cond = f"practice_area = ${i}"
            params.append(inferred_area); i += 1
            conditions.append(
                f"({title_cond} OR {headnote_cond} OR {area_cond})"
            )
        else:
            conditions.append(f"({title_cond} OR {headnote_cond})")
    elif year and 2020 <= year <= 2030:
        # Year filter: exact calendar year
        conditions.append(f"judgment_date >= ${i}::date")
        params.append(datetime.date(year, 1, 1)); i += 1
        conditions.append(f"judgment_date <= ${i}::date")
        params.append(datetime.date(year, 12, 31)); i += 1
    else:
        # Days filter (default)
        days = max(1, min(days, 1095))
        conditions.append(f"judgment_date >= CURRENT_DATE - ${i}::int * INTERVAL '1 day'")
        params.append(days); i += 1

    if area:
        conditions.append(f"practice_area = ${i}")
        params.append(area); i += 1

    if court:
        conditions.append(f"court = ${i}")
        params.append(court); i += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else "WHERE 1=1"

    pool = await get_judgment_pool()
    conn = await pool.acquire()
    try:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM judgments_dedup {where}", *params
        )
        rows = await conn.fetch(
            f"""
            SELECT id, title, court, judgment_date::text, source_url,
                   headnote, practice_area, source_name
            FROM judgments_dedup
            {where}
            ORDER BY judgment_date DESC
            LIMIT {limit} OFFSET {page * limit}
            """,
            *params
        )
        return {
            "total": total,
            "page":  page,
            "limit": limit,
            "pages": -(-int(total) // limit),
            "judgments": [dict(r) for r in rows],
        }
    finally:
        await pool.release(conn)

# Simple stats cache — refresh every 30 minutes
_stats_cache: dict = {}
_stats_cache_time: float = 0.0

@app.get("/api/judgments/stats")
async def api_judgment_stats(days: int = 0):
    """
    Returns count breakdown by area and court.
    days=0 (default) = all time
    days=7 = last 7 days, etc.
    """
    import time
    global _stats_cache, _stats_cache_time
    cache_key = str(days)
    if cache_key in _stats_cache and (time.time() - _stats_cache_time) < 1800:
        return _stats_cache[cache_key]
    pool = await get_judgment_pool()
    conn = await pool.acquire()
    try:
        where = "WHERE judgment_date >= CURRENT_DATE - $1::int * INTERVAL '1 day'" if days > 0 else "WHERE 1=1"
        params = [days] if days > 0 else []

        # where is either empty string or "WHERE ..." — handle both safely
        area_where  = where if where else "WHERE 1=1"
        by_area = await conn.fetch(f"""
            SELECT practice_area, COUNT(*) as cnt
            FROM judgments_dedup
            {area_where}
            GROUP BY practice_area ORDER BY cnt DESC
        """, *params)
        by_court = await conn.fetch(f"""
            SELECT court, COUNT(*) as cnt
            FROM judgments_dedup
            {area_where}
            GROUP BY court ORDER BY cnt DESC LIMIT 15
        """, *params)
        latest = await conn.fetchval(
            "SELECT MAX(scraped_at)::text FROM judgments"
        )
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM judgments_dedup{(' ' + where) if where else ''}",
            *params
        )
        result = {
            "by_area":     [dict(r) for r in by_area],
            "by_court":    [dict(r) for r in by_court],
            "last_updated": latest,
            "total":       total,
        }
        _stats_cache[cache_key] = result
        _stats_cache_time = time.time()
        return result
    finally:
        await pool.release(conn)
