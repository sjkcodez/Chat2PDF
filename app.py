"""Flask web app for chat-to-pdf."""

import os
import re
import threading
import time
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, send_file, abort,
)

import config
from core.converter import start_session, cleanup_session
from core.session_manager import manager


print(config.config_summary())


app = Flask(__name__)
app.secret_key = config.SECRET_KEY


PLATFORM_NAMES = {
    "chatgpt": "ChatGPT",
    "claude": "ClaudeAI",
    "gemini": "GeminiAI",
    "deepseek": "DeepSeek",
    "google_ai_mode": "GoogleAIMode",
    "perplexity": "PerplexityAI",
    "grok": "GrokAI",
    "meta": "MetaAI",
    "copilot": "Copilot",
    "qwen": "QwenAI",
    "generic": "Chatbot",
}


def _sanitize_filename(name: str) -> str:
    if not name:
        return ""
    name = re.sub(r"[^\w\s.\-]", "", name, flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:80]


def _build_download_name(s) -> str:
    platform_label = PLATFORM_NAMES.get(s.platform, "Chatbot")
    stamp = s.created_at.strftime("%d-%m-%Y-%H-%M-%S")
    base = _sanitize_filename(s.filename) if s.filename else ""
    if base:
        return f"{base}-{platform_label}-{stamp}.pdf"
    return f"{platform_label}-{stamp}.pdf"


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("auth_ok"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == config.APP_PASSWORD:
            session["auth_ok"] = True
            return redirect(url_for("index"))
        error = "Incorrect password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/viewer/<sid>")
@login_required
def viewer(sid):
    s = manager.get(sid)
    if not s:
        abort(404)
    return render_template("viewer.html", session_id=sid,
                           vnc_url=s.vnc_url or "")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def _is_allowed(url: str) -> bool:
    """Use the pattern-based allowlist from config."""
    return config.is_host_allowed(url)


@app.route("/api/convert", methods=["POST"])
@login_required
def api_convert():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    filename = _sanitize_filename((data.get("filename") or "").strip())

    if not url:
        return jsonify(error="Please paste a link."), 400
    if not re.match(r"^https?://", url):
        return jsonify(error="Link must start with http:// or https://"), 400
    if not _is_allowed(url):
        return jsonify(
            error="This link doesn't look like an AI chat share link. "
                  "Paste a share URL from ChatGPT, Claude, Gemini, DeepSeek, "
                  "Perplexity, Grok, Meta AI, Copilot, Qwen, or any other "
                  "AI platform."
        ), 400

    if manager.active_count() >= config.MAX_CONCURRENT_SESSIONS:
        return jsonify(error="Server is busy — please try again."), 429

    s = start_session(url, filename=filename)
    return jsonify(session_id=s.id)


@app.route("/api/status/<sid>")
@login_required
def api_status(sid):
    s = manager.get(sid)
    if not s:
        return jsonify(error="Session not found."), 404
    download_ready = (
        s.status == "done"
        and s.pdf_path
        and os.path.exists(s.pdf_path)
        and os.path.getsize(s.pdf_path) > 0
    )
    return jsonify(
        status=s.status,
        message=s.message,
        error=s.error,
        vnc_url=s.vnc_url,
        viewer_path=url_for("viewer", sid=sid)
            if s.status == "awaiting_captcha" else None,
        download_path=url_for("api_download", sid=sid)
            if download_ready else None,
        pdf_size=os.path.getsize(s.pdf_path)
            if (s.pdf_path and os.path.exists(s.pdf_path)) else 0,
    )


@app.route("/api/download/<sid>", strict_slashes=False)
@login_required
def api_download(sid):
    s = manager.get(sid)
    if s is None:
        return jsonify(
            error="Session not found.",
            detail="The session expired. Please run the conversion again."
        ), 404
    if s.status != "done":
        return jsonify(error="Not ready yet.",
                       detail=f"Status: {s.status}."), 409
    if not s.pdf_path or not os.path.exists(s.pdf_path):
        return jsonify(error="PDF file is missing.",
                       detail=f"Expected at: {s.pdf_path}"), 404
    size = os.path.getsize(s.pdf_path)
    if size == 0:
        return jsonify(error="PDF file is empty."), 500

    s.pinned = True
    download_name = _build_download_name(s)
    return send_file(
        s.pdf_path,
        as_attachment=True,
        download_name=download_name,
        mimetype="application/pdf",
    )


@app.route("/api/cleanup/<sid>", methods=["POST"])
@login_required
def api_cleanup(sid):
    cleanup_session(sid)
    return jsonify(ok=True)


@app.route("/api/debug")
@login_required
def api_debug_all():
    sessions = manager.all()
    return jsonify(
        count=len(sessions),
        active_count=manager.active_count(),
        max_concurrent=config.MAX_CONCURRENT_SESSIONS,
        sessions=[
            {
                "id": s.id,
                "status": s.status,
                "platform": s.platform,
                "filename": s.filename,
                "url": s.url,
                "message": s.message,
                "error": s.error,
                "pdf_path": s.pdf_path,
                "pdf_exists": bool(s.pdf_path and os.path.exists(s.pdf_path)),
                "pdf_size": os.path.getsize(s.pdf_path)
                    if (s.pdf_path and os.path.exists(s.pdf_path)) else 0,
                "pinned": s.pinned,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in sessions
        ],
    )


@app.route("/api/debug/<sid>")
@login_required
def api_debug(sid):
    s = manager.get(sid)
    if not s:
        return jsonify(
            exists=False,
            hint="Session not in memory. Server may have restarted.",
            active_sessions=[x.id for x in manager.all()],
        )
    return jsonify(
        exists=True,
        id=s.id,
        url=s.url,
        platform=s.platform,
        filename=s.filename,
        status=s.status,
        message=s.message,
        error=s.error,
        pdf_path=s.pdf_path,
        pdf_exists=bool(s.pdf_path and os.path.exists(s.pdf_path)),
        pdf_size=os.path.getsize(s.pdf_path)
            if (s.pdf_path and os.path.exists(s.pdf_path)) else 0,
        pinned=s.pinned,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Background sweeper
# ---------------------------------------------------------------------------

def _sweeper():
    import shutil
    while True:
        time.sleep(60)
        try:
            stale = manager.sweepable(config.SESSION_TIMEOUT_SECONDS)
            for s in stale:
                print(f"[sweeper] Removing stale session {s.id}")
                cleanup_session(s.id)
                d = config.SESSIONS_DIR / s.id
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
        except Exception as e:
            print(f"[sweeper] Error: {e}")


threading.Thread(target=_sweeper, daemon=True).start()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True,
        use_reloader=False,
    )
