"""MFR Director — FastAPI web application."""
import json
import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import (
    Cookie, Depends, FastAPI, File, Form, HTTPException,
    Request, UploadFile, status,
)
from fastapi.responses import (
    FileResponse, HTMLResponse, JSONResponse, RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import auth
import analysis
import email_sender

BASE_DIR = Path(__file__).parent
EXPORTS_DIR = BASE_DIR / "data" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MFR Director", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

ADMIN_KEY = os.environ.get("ADMIN_KEY", "")


# ── Session dependency ────────────────────────────────────────────────────────

def require_session(session: Annotated[str | None, Cookie()] = None) -> str:
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    email = auth.decode_session_token(session)
    if not email:
        raise HTTPException(status_code=401, detail="Session expired")
    return email


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, session: str | None = Cookie(default=None)):
    email = auth.decode_session_token(session) if session else None
    return templates.TemplateResponse("index.html", {"request": request, "email": email})


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/auth/request-code")
async def request_code(email: str = Form(...)):
    email = email.lower().strip()

    if not auth.is_subscriber(email):
        # Return generic response — don't reveal whether email is in system
        return JSONResponse({"status": "sent"})

    code = auth.generate_monthly_code(email)
    try:
        email_sender.send_login_code(email, code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")

    return JSONResponse({"status": "sent"})


@app.post("/auth/verify-code")
async def verify_code(email: str = Form(...), code: str = Form(...)):
    email = email.lower().strip()

    if not auth.is_subscriber(email):
        raise HTTPException(status_code=403, detail="Email not authorized.")

    if not auth.verify_code(email, code):
        raise HTTPException(status_code=403, detail="Invalid or expired code.")

    token = auth.create_session_token(email)
    response = JSONResponse({"status": "ok", "email": email})
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=os.environ.get("HTTPS", "false").lower() == "true",
        samesite="lax",
        max_age=60 * 60 * 24,  # 24h
    )
    return response


@app.post("/auth/logout")
async def logout():
    response = JSONResponse({"status": "ok"})
    response.delete_cookie("session")
    return response


# ── Analysis endpoint ─────────────────────────────────────────────────────────

@app.post("/analyze")
async def analyze(
    email: str = Depends(require_session),
    files: list[UploadFile] = File(...),
    city: str = Form(...),
    nickname: str = Form(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if not city.strip() or not nickname.strip():
        raise HTTPException(status_code=400, detail="City and nickname are required.")

    # Read file contents
    file_tuples: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        file_tuples.append((f.filename or "upload", content))

    try:
        result = analysis.run_analysis(file_tuples, city.strip(), nickname.strip())
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    # Generate and cache the Excel file for this session
    analysis_id = str(uuid.uuid4())
    excel_path = None
    try:
        excel_path = analysis.generate_excel(result, nickname.strip())
        if excel_path and excel_path.exists():
            dest = EXPORTS_DIR / f"{analysis_id}.xlsx"
            excel_path.rename(dest)
            excel_path = dest
    except Exception:
        excel_path = None

    return JSONResponse({
        "html_dashboard": result.get("html_dashboard"),
        "sheets_data": result.get("sheets_data"),
        "analysis_id": analysis_id if excel_path else None,
        "raw_response": result.get("raw_response") if not result.get("html_dashboard") else None,
    })


# ── Export endpoints ──────────────────────────────────────────────────────────

@app.get("/export/excel/{analysis_id}")
async def download_excel(analysis_id: str, email: str = Depends(require_session)):
    # Sanitize
    if not analysis_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid analysis ID.")

    path = EXPORTS_DIR / f"{analysis_id}.xlsx"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export not found or expired.")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="mfr_analysis.xlsx",
    )


@app.post("/export/sheets")
async def export_to_sheets(
    email: str = Depends(require_session),
    analysis_id: str = Form(...),
    share_email: str = Form(...),
    nickname: str = Form(...),
):
    try:
        from sheets_export import export_to_sheets as _export
    except ImportError:
        raise HTTPException(status_code=501, detail="Google Sheets export not available (library not installed).")

    # Load cached sheets_data
    data_path = EXPORTS_DIR / f"{analysis_id}.json"
    if not data_path.exists():
        raise HTTPException(status_code=404, detail="Analysis data not found.")

    with open(data_path) as f:
        sheets_data = json.load(f)

    try:
        url = _export(sheets_data, nickname, share_email)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Sheets export failed: {e}")

    return JSONResponse({"url": url})


@app.post("/analyze-and-cache")
async def analyze_and_cache(
    email: str = Depends(require_session),
    files: list[UploadFile] = File(...),
    city: str = Form(...),
    nickname: str = Form(...),
):
    """Extended version of /analyze that also caches sheets_data for Google Sheets export."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    file_tuples: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        file_tuples.append((f.filename or "upload", content))

    try:
        result = analysis.run_analysis(file_tuples, city.strip(), nickname.strip())
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    analysis_id = str(uuid.uuid4())

    # Cache sheets_data
    if result.get("sheets_data"):
        data_path = EXPORTS_DIR / f"{analysis_id}.json"
        with open(data_path, "w") as f:
            json.dump(result["sheets_data"], f)

    # Generate Excel
    excel_cached = False
    try:
        excel_path = analysis.generate_excel(result, nickname.strip())
        if excel_path and excel_path.exists():
            dest = EXPORTS_DIR / f"{analysis_id}.xlsx"
            excel_path.rename(dest)
            excel_cached = True
    except Exception:
        pass

    return JSONResponse({
        "html_dashboard": result.get("html_dashboard"),
        "sheets_data": result.get("sheets_data"),
        "analysis_id": analysis_id,
        "has_excel": excel_cached,
        "has_sheets_data": bool(result.get("sheets_data")),
        "raw_response": result.get("raw_response") if not result.get("html_dashboard") else None,
    })


# ── Admin endpoints ───────────────────────────────────────────────────────────

def require_admin(x_admin_key: str | None = None):
    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.get("/admin/subscribers")
async def list_subs(x_admin_key: str | None = None):
    require_admin(x_admin_key)
    return {"subscribers": auth.list_subscribers()}


@app.post("/admin/subscribers/add")
async def add_sub(email: str = Form(...), x_admin_key: str | None = Form(default=None)):
    require_admin(x_admin_key)
    auth.add_subscriber(email.lower().strip())
    return {"status": "added", "email": email.lower().strip()}


@app.post("/admin/subscribers/remove")
async def remove_sub(email: str = Form(...), x_admin_key: str | None = Form(default=None)):
    require_admin(x_admin_key)
    removed = auth.remove_subscriber(email.lower().strip())
    return {"status": "removed" if removed else "not_found", "email": email.lower().strip()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
