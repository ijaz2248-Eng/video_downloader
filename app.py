from flask import Flask, render_template, request, jsonify, send_file
import os, time, threading, uuid
from collections import defaultdict

import yt_dlp

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Simple rate limit (per IP)
REQUEST_LIMIT = 12
TIME_WINDOW = 300
user_requests = defaultdict(list)

def is_rate_limited(ip: str) -> bool:
    now = time.time()
    user_requests[ip] = [t for t in user_requests[ip] if now - t < TIME_WINDOW]
    if len(user_requests[ip]) >= REQUEST_LIMIT:
        return True
    user_requests[ip].append(now)
    return False

def delete_file_later(path, delay=15*60):
    def _delete():
        time.sleep(delay)
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
    threading.Thread(target=_delete, daemon=True).start()

def ytdlp_base_opts():
    # More robust defaults for cloud hosts (best-effort)
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        # Helps some YouTube cases:
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
    }

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/formats")
def api_formats():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if is_rate_limited(ip):
        return jsonify({"ok": False, "error": "Rate limit exceeded. Try again in a few minutes."}), 429

    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Please paste a video URL."}), 400

    try:
        opts = ytdlp_base_opts()
        opts.update({
            "skip_download": True,
            "dump_single_json": True,
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Flatten (handle single video)
        title = info.get("title") or "Video"
        thumbnail = info.get("thumbnail")
        webpage_url = info.get("webpage_url") or url

        formats = info.get("formats") or []
        cleaned = []
        for f in formats:
            # Some formats are useless/empty
            if not f.get("url"):
                continue
            vcodec = f.get("vcodec")
            acodec = f.get("acodec")
            ext = f.get("ext")
            height = f.get("height") or 0
            fps = f.get("fps") or 0
            tbr = f.get("tbr") or 0
            filesize = f.get("filesize") or f.get("filesize_approx") or 0

            # label
            if vcodec != "none" and acodec != "none":
                kind = "video+audio"
            elif vcodec != "none" and acodec == "none":
                kind = "video"
            else:
                kind = "audio"

            cleaned.append({
                "format_id": f.get("format_id"),
                "ext": ext,
                "kind": kind,
                "height": height,
                "fps": fps,
                "tbr": tbr,
                "vcodec": vcodec,
                "acodec": acodec,
                "filesize": filesize,
                "note": f.get("format_note") or "",
            })

        # Sort: best first
        cleaned.sort(key=lambda x: (x["kind"] != "video+audio", x["kind"] != "video", x["height"], x["tbr"]), reverse=True)

        return jsonify({
            "ok": True,
            "title": title,
            "thumbnail": thumbnail,
            "webpage_url": webpage_url,
            "formats": cleaned[:200],  # keep response light
        })

    except Exception as e:
        msg = str(e)
        # Make message user-friendly
        if "Sign in to confirm" in msg or "confirm you’re not a bot" in msg:
            msg = "This platform is blocking automated access for this link. Try another public link."
        return jsonify({"ok": False, "error": msg}), 500


@app.get("/download")
def download():
    """
    /download?url=...&format_id=...
    """
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if is_rate_limited(ip):
        return jsonify({"ok": False, "error": "Rate limit exceeded. Try again later."}), 429

    url = (request.args.get("url") or "").strip()
    fmt = (request.args.get("format_id") or "").strip()
    if not url or not fmt:
        return "Missing url or format_id", 400

    file_id = str(uuid.uuid4())
    outtmpl = os.path.join(DOWNLOAD_FOLDER, f"{file_id}.%(ext)s")

    try:
        opts = ytdlp_base_opts()
        opts.update({
            "format": fmt,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded = ydl.prepare_filename(info)

        if not os.path.exists(downloaded):
            # maybe merged to mp4
            mp4_try = os.path.splitext(downloaded)[0] + ".mp4"
            if os.path.exists(mp4_try):
                downloaded = mp4_try

        delete_file_later(downloaded, delay=15*60)
        return send_file(downloaded, as_attachment=True)

    except Exception as e:
        return f"Download failed: {e}", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
