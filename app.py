import os
import re
import time
import uuid
import threading
from pathlib import Path

import requests
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_FOLDER = BASE_DIR / "downloads"
DOWNLOAD_FOLDER.mkdir(exist_ok=True)

# ========= ENV VARS (Render -> Environment) =========
ENABLE_RECAPTCHA = os.getenv("ENABLE_RECAPTCHA", "1") == "1"
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "").strip()
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "").strip()

# ========= SIMPLE RATE LIMIT (IP-based) =========
REQUEST_LIMIT = int(os.getenv("REQUEST_LIMIT", "8"))     # per TIME_WINDOW seconds
TIME_WINDOW = int(os.getenv("TIME_WINDOW", "300"))       # 5 minutes
user_requests = {}

def is_rate_limited(ip: str) -> bool:
    now = time.time()
    times = user_requests.get(ip, [])
    times = [t for t in times if now - t < TIME_WINDOW]
    if len(times) >= REQUEST_LIMIT:
        user_requests[ip] = times
        return True
    times.append(now)
    user_requests[ip] = times
    return False

def delete_file_later(path: Path, delay: int = 120):
    def worker():
        try:
            time.sleep(delay)
            if path.exists():
                path.unlink()
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()

# ========= reCAPTCHA VERIFY =========
def verify_recaptcha(token: str, remote_ip: str) -> (bool, str):
    """
    Verify reCAPTCHA v2 checkbox token (g-recaptcha-response).
    """
    if not ENABLE_RECAPTCHA:
        return True, "recaptcha_disabled"

    if not RECAPTCHA_SECRET_KEY:
        # If enabled but missing secret, fail clearly
        return False, "Server reCAPTCHA is not configured (missing secret key)."

    if not token:
        return False, "Verification expired. Check the checkbox again."

    try:
        resp = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": RECAPTCHA_SECRET_KEY,
                "response": token,
                "remoteip": remote_ip,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("success") is True:
            return True, "ok"

        # common case: timeout-or-duplicate
        codes = data.get("error-codes", [])
        if "timeout-or-duplicate" in codes:
            return False, "Verification expired. Check the checkbox again."
        return False, f"reCAPTCHA failed: {', '.join(codes) if codes else 'unknown error'}"
    except Exception:
        return False, "reCAPTCHA verification error. Try again."

# ========= yt-dlp helpers =========
RESTRICTED_PATTERNS = [
    r"sign in",
    r"login",
    r"confirm you'?re not a bot",
    r"not a robot",
    r"this video is private",
    r"age-restricted",
    r"requires authentication",
    r"requested content is not available",
]

def is_restricted_error(msg: str) -> bool:
    low = (msg or "").lower()
    return any(re.search(p, low) for p in RESTRICTED_PATTERNS)

def ydl_base_opts():
    """
    Safe-ish defaults for public extraction.
    Note: We do NOT provide bypass instructions for login/CAPTCHA.
    """
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "consoletitle": False,
        "http_headers": {
            # Helps avoid some basic blocks; not a CAPTCHA bypass.
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        # Prefer not to download huge by default; we only extract info in /api/info
        "skip_download": True,
    }

def normalize_formats(info: dict):
    formats = info.get("formats") or []
    out = []

    for f in formats:
        # Keep only useful formats (video/audio)
        if f.get("url") is None:
            continue

        fmt_id = f.get("format_id")
        ext = f.get("ext")
        acodec = f.get("acodec")
        vcodec = f.get("vcodec")
        height = f.get("height") or 0
        fps = f.get("fps") or 0
        abr = f.get("abr") or 0
        vbr = f.get("vbr") or 0
        tbr = f.get("tbr") or 0
        filesize = f.get("filesize") or f.get("filesize_approx") or 0

        # classify
        is_audio_only = (vcodec == "none" and acodec != "none")
        is_video = (vcodec != "none")

        label_parts = []
        if is_audio_only:
            label_parts.append("AUDIO")
            if abr:
                label_parts.append(f"{int(abr)}kbps")
        elif is_video:
            label_parts.append("VIDEO")
            if height:
                label_parts.append(f"{height}p")
            if fps:
                label_parts.append(f"{int(fps)}fps")
            if vbr:
                label_parts.append(f"v{int(vbr)}kbps")
        if ext:
            label_parts.append(ext.upper())

        out.append({
            "format_id": fmt_id,
            "ext": ext,
            "height": height,
            "fps": fps,
            "tbr": tbr,
            "filesize": filesize,
            "is_audio_only": is_audio_only,
            "label": " • ".join(label_parts) if label_parts else (f.get("format") or fmt_id),
        })

    # Sort: video desc by height then bitrate, audio desc by abr
    def sort_key(x):
        if x["is_audio_only"]:
            return (0, 0, x["tbr"] or 0)
        return (1, x["height"] or 0, x["tbr"] or 0)

    out.sort(key=sort_key, reverse=True)
    return out

@app.get("/")
def index():
    return render_template(
        "index.html",
        recaptcha_site_key=RECAPTCHA_SITE_KEY if ENABLE_RECAPTCHA else "",
        enable_recaptcha=ENABLE_RECAPTCHA,
    )

@app.post("/api/info")
def api_info():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if is_rate_limited(ip):
        return jsonify({"ok": False, "error": "Too many requests. Try again in a few minutes."}), 429

    url = (request.json or {}).get("url", "").strip()
    token = (request.json or {}).get("recaptcha", "").strip()

    ok, msg = verify_recaptcha(token, ip)
    if not ok:
        return jsonify({"ok": False, "error": msg, "need_recaptcha": True}), 400

    if not url:
        return jsonify({"ok": False, "error": "Please paste a video URL."}), 400

    ydl_opts = ydl_base_opts()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title") or "video"
        thumbnail = info.get("thumbnail")
        formats = normalize_formats(info)

        if not formats:
            return jsonify({"ok": False, "error": "No downloadable formats found for this URL."}), 400

        return jsonify({
            "ok": True,
            "title": title,
            "thumbnail": thumbnail,
            "formats": formats,
        })

    except Exception as e:
        err = str(e)
        if is_restricted_error(err):
            return jsonify({
                "ok": False,
                "restricted": True,
                "error": (
                    "Restricted/login detected. This hosted app can only download PUBLIC videos. "
                    "If the video requires login, cookies are needed (upload/paste), or use official access."
                )
            }), 400
        return jsonify({"ok": False, "error": f"Extraction failed: {err}"}), 400

@app.post("/api/download")
def api_download():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if is_rate_limited(ip):
        return jsonify({"ok": False, "error": "Too many requests. Try again in a few minutes."}), 429

    url = (request.json or {}).get("url", "").strip()
    fmt = (request.json or {}).get("format_id", "").strip()
    token = (request.json or {}).get("recaptcha", "").strip()

    ok, msg = verify_recaptcha(token, ip)
    if not ok:
        return jsonify({"ok": False, "error": msg, "need_recaptcha": True}), 400

    if not url or not fmt:
        return jsonify({"ok": False, "error": "Missing URL or format."}), 400

    file_id = uuid.uuid4().hex
    outtmpl = str(DOWNLOAD_FOLDER / f"{file_id}.%(ext)s")

    ydl_opts = {
        **ydl_base_opts(),
        "skip_download": False,
        "format": fmt,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # find produced file
        # yt-dlp resolves actual extension; search for matching prefix
        produced = None
        for p in DOWNLOAD_FOLDER.glob(f"{file_id}.*"):
            produced = p
            break

        if not produced or not produced.exists():
            return jsonify({"ok": False, "error": "Download failed (file not created)."}), 400

        delete_file_later(produced, delay=180)

        # A cleaner filename for user
        title = (info.get("title") or "video").strip()
        safe_title = re.sub(r'[\\/*?:"<>|]+', "_", title)[:90]
        download_name = f"{safe_title}.{produced.suffix.lstrip('.')}"
        return send_file(produced, as_attachment=True, download_name=download_name)

    except Exception as e:
        err = str(e)
        if is_restricted_error(err):
            return jsonify({
                "ok": False,
                "restricted": True,
                "error": (
                    "Restricted/login detected. This hosted app can only download PUBLIC videos. "
                    "If login is required, cookies are needed (upload/paste) or use official access."
                )
            }), 400
        return jsonify({"ok": False, "error": f"Download failed: {err}"}), 400
