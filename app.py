import os
import time
import uuid
import threading
from collections import defaultdict

import requests
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)

# -----------------------------
# Config
# -----------------------------
DOWNLOAD_FOLDER = os.environ.get("DOWNLOAD_FOLDER", "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

REQUEST_LIMIT = int(os.environ.get("REQUEST_LIMIT", "8"))
TIME_WINDOW = int(os.environ.get("TIME_WINDOW", "300"))
AUTO_DELETE_SECONDS = int(os.environ.get("AUTO_DELETE_SECONDS", "600"))

RECAPTCHA_ENABLED = os.environ.get("RECAPTCHA_ENABLED", "true").lower() == "true"
RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY", "")
ALLOWED_HOSTNAMES = [
    h.strip().lower()
    for h in os.environ.get(
        "RECAPTCHA_ALLOWED_HOSTNAMES",
        "video-downloader-cdso.onrender.com,onrender.com,localhost"
    ).split(",")
    if h.strip()
]

user_requests = defaultdict(list)


# -----------------------------
# Helpers
# -----------------------------
def is_rate_limited(ip: str) -> bool:
    now = time.time()
    user_requests[ip] = [t for t in user_requests[ip] if now - t < TIME_WINDOW]
    if len(user_requests[ip]) >= REQUEST_LIMIT:
        return True
    user_requests[ip].append(now)
    return False


def delete_file_later(path: str, delay: int = AUTO_DELETE_SECONDS):
    def _delete():
        try:
            time.sleep(delay)
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    threading.Thread(target=_delete, daemon=True).start()


def client_ip() -> str:
    # Render/Proxies
    xf = request.headers.get("X-Forwarded-For", "")
    if xf:
        return xf.split(",")[0].strip()
    return request.remote_addr or "unknown"


def verify_recaptcha(token: str):
    """
    Returns: (ok: bool, error_message: str)
    """
    if not RECAPTCHA_ENABLED:
        return True, ""

    if not (RECAPTCHA_SECRET_KEY and RECAPTCHA_SITE_KEY):
        return False, "reCAPTCHA keys are not configured on server."

    if not token:
        return False, "Please complete the reCAPTCHA checkbox."

    try:
        resp = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": RECAPTCHA_SECRET_KEY,
                "response": token,
                # "remoteip": client_ip(),  # optional
            },
            timeout=15,
        )
        data = resp.json()
    except Exception:
        return False, "reCAPTCHA verification failed (network/server error)."

    if not data.get("success"):
        codes = data.get("error-codes", [])
        # common: timeout-or-duplicate, invalid-input-secret, invalid-input-response
        return False, f"reCAPTCHA failed: {', '.join(codes) if codes else 'unknown error'}"

    # Hostname verification (important when 'Verify the origin...' is enabled)
    hostname = (data.get("hostname") or "").lower().strip()
    if hostname and hostname not in ALLOWED_HOSTNAMES:
        return False, f"reCAPTCHA hostname mismatch: {hostname}"

    return True, ""


def ydl_base_opts():
    # Keep options conservative for hosted environments
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        # If you want extra debugging:
        # "verbose": True,
    }


def extract_info(url: str):
    opts = ydl_base_opts()
    opts.update({"skip_download": True})

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def simplify_formats(info: dict):
    fmts = info.get("formats") or []
    out = []

    for f in fmts:
        # Skip broken entries
        if not f.get("format_id"):
            continue

        vcodec = f.get("vcodec")
        acodec = f.get("acodec")

        is_video = vcodec and vcodec != "none"
        is_audio = acodec and acodec != "none"

        # Only show useful types
        if not (is_video or is_audio):
            continue

        out.append({
            "format_id": f.get("format_id"),
            "ext": f.get("ext"),
            "resolution": f.get("resolution") or (f"{f.get('width','?')}x{f.get('height','?')}" if f.get("width") else None),
            "height": f.get("height"),
            "fps": f.get("fps"),
            "vcodec": vcodec,
            "acodec": acodec,
            "filesize": f.get("filesize") or f.get("filesize_approx"),
            "tbr": f.get("tbr"),
            "abr": f.get("abr"),
            "format_note": f.get("format_note"),
            "is_video": bool(is_video),
            "is_audio": bool(is_audio),
        })

    # Sort: best height then bitrate
    out.sort(key=lambda x: (x["height"] or 0, x["tbr"] or 0), reverse=True)
    return out


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        site_key=RECAPTCHA_SITE_KEY,
        recaptcha_enabled=RECAPTCHA_ENABLED
    )


@app.route("/api/extract", methods=["POST"])
def api_extract():
    ip = client_ip()
    if is_rate_limited(ip):
        return jsonify({"ok": False, "error": "Too many requests. Please wait a few minutes."}), 429

    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()
    token = (data.get("recaptchaToken") or "").strip()

    ok, msg = verify_recaptcha(token)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 400

    if not url:
        return jsonify({"ok": False, "error": "Please paste a video URL."}), 400

    try:
        info = extract_info(url)
        title = info.get("title") or "Video"
        thumbnail = info.get("thumbnail")
        formats = simplify_formats(info)
        if not formats:
            return jsonify({"ok": False, "error": "No downloadable formats found (maybe restricted or blocked)."}), 400

        return jsonify({
            "ok": True,
            "title": title,
            "thumbnail": thumbnail,
            "formats": formats
        })
    except yt_dlp.utils.DownloadError as e:
        # Most common for restricted/login/bot-check
        return jsonify({
            "ok": False,
            "error": "Restricted/login/bot-check detected. Public hosted site may fail for this URL.",
            "details": str(e)[:500]
        }), 400
    except Exception as e:
        return jsonify({"ok": False, "error": "Server error while extracting formats.", "details": str(e)[:500]}), 500


@app.route("/api/download", methods=["POST"])
def api_download():
    ip = client_ip()
    if is_rate_limited(ip):
        return jsonify({"ok": False, "error": "Too many requests. Please wait a few minutes."}), 429

    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()
    format_id = (data.get("format_id") or "").strip()
    token = (data.get("recaptchaToken") or "").strip()

    ok, msg = verify_recaptcha(token)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 400

    if not url or not format_id:
        return jsonify({"ok": False, "error": "Missing URL or format id."}), 400

    file_id = str(uuid.uuid4())
    outtmpl = os.path.join(DOWNLOAD_FOLDER, f"{file_id}.%(ext)s")

    try:
        opts = ydl_base_opts()
        opts.update({
            "format": format_id,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Determine final file path
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                # merged file may change extension
                base = os.path.splitext(filename)[0]
                for ext in ("mp4", "mkv", "webm", "mp3", "m4a"):
                    candidate = base + "." + ext
                    if os.path.exists(candidate):
                        filename = candidate
                        break

        delete_file_later(filename)
        safe_name = (info.get("title") or "video").replace("/", "_").replace("\\", "_")
        return send_file(filename, as_attachment=True, download_name=f"{safe_name}{os.path.splitext(filename)[1]}")
    except yt_dlp.utils.DownloadError as e:
        return jsonify({
            "ok": False,
            "error": "Download failed (restricted/login/bot-check or extractor issue).",
            "details": str(e)[:500]
        }), 400
    except Exception as e:
        return jsonify({"ok": False, "error": "Server error while downloading.", "details": str(e)[:500]}), 500
