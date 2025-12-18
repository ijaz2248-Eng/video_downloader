from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os, time, threading
from collections import defaultdict
from urllib.parse import urlparse

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ===== RATE LIMITING =====
REQUEST_LIMIT = 6          # requests per TIME_WINDOW per IP
TIME_WINDOW = 300          # seconds (5 minutes)
user_requests = defaultdict(list)

def is_rate_limited(ip):
    now = time.time()
    user_requests[ip] = [t for t in user_requests[ip] if now - t < TIME_WINDOW]
    if len(user_requests[ip]) >= REQUEST_LIMIT:
        return True
    user_requests[ip].append(now)
    return False

# ===== AUTO DELETE FILES =====
def delete_file_later(path, delay=120):
    def _delete():
        time.sleep(delay)
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
    threading.Thread(target=_delete, daemon=True).start()

def human_size(num):
    try:
        num = float(num)
    except:
        return ""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"

def platform_name(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except:
        return "Video"
    if "youtube" in host or "youtu.be" in host:
        return "YouTube"
    if "facebook" in host or "fb.watch" in host:
        return "Facebook"
    if "instagram" in host:
        return "Instagram"
    if "tiktok" in host:
        return "TikTok"
    return "Video"

def simplify_format(f):
    # Determine filesize (not always available)
    filesize = f.get("filesize") or f.get("filesize_approx") or 0
    return {
        "format_id": f.get("format_id"),
        "ext": f.get("ext"),
        "format_note": f.get("format_note"),
        "resolution": f.get("resolution") or f"{f.get('width','')}x{f.get('height','')}".strip("x"),
        "width": f.get("width"),
        "height": f.get("height"),
        "fps": f.get("fps"),
        "vcodec": f.get("vcodec"),
        "acodec": f.get("acodec"),
        "tbr": f.get("tbr"),
        "abr": f.get("abr"),
        "filesize": filesize,
        "filesize_h": human_size(filesize) if filesize else "",
        "protocol": f.get("protocol"),
    }

def is_audio_only(f):
    return (f.get("vcodec") == "none") and (f.get("acodec") not in (None, "none"))

def is_video_only(f):
    return (f.get("acodec") == "none") and (f.get("vcodec") not in (None, "none"))

def is_progressive(f):
    return (f.get("acodec") not in (None, "none")) and (f.get("vcodec") not in (None, "none"))

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/info")
def info():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if is_rate_limited(ip):
        return jsonify({"ok": False, "error": "Too many requests. Please wait a few minutes and try again."}), 429

    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Please paste a valid video URL."}), 400

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
        # Reduce random failures
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "consoletitle": False,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title") or "Untitled"
        thumb = info.get("thumbnail")
        plat = platform_name(url)

        formats = info.get("formats") or []
        # Keep only downloadable formats with ext/format_id
        formats = [f for f in formats if f.get("format_id") and f.get("ext")]

        progressive = []
        video_only = []
        audio_only = []

        for f in formats:
            if is_progressive(f):
                progressive.append(simplify_format(f))
            elif is_video_only(f):
                video_only.append(simplify_format(f))
            elif is_audio_only(f):
                audio_only.append(simplify_format(f))

        # Sorting (best first)
        def sort_key_video(x):
            h = x.get("height") or 0
            tbr = x.get("tbr") or 0
            return (h, tbr)

        def sort_key_audio(x):
            abr = x.get("abr") or 0
            tbr = x.get("tbr") or 0
            return (abr, tbr)

        progressive.sort(key=sort_key_video, reverse=True)
        video_only.sort(key=sort_key_video, reverse=True)
        audio_only.sort(key=sort_key_audio, reverse=True)

        return jsonify({
            "ok": True,
            "platform": plat,
            "title": title,
            "thumbnail": thumb,
            "progressive": progressive,
            "video_only": video_only,
            "audio_only": audio_only,
        })

    except Exception as e:
        msg = str(e)
        # Cleaner user error
        return jsonify({
            "ok": False,
            "error": f"Could not fetch formats. Try another link (public video) or try again later.\n\nDetails: {msg}"
        }), 500

@app.get("/download")
def download():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if is_rate_limited(ip):
        return jsonify({"ok": False, "error": "Too many requests. Please wait and try again."}), 429

    url = (request.args.get("url") or "").strip()
    format_id = (request.args.get("format_id") or "").strip()
    if not url or not format_id:
        return jsonify({"ok": False, "error": "Missing url or format_id"}), 400

    filename = f"video_{int(time.time())}.%(ext)s"
    outtmpl = os.path.join(DOWNLOAD_FOLDER, filename)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "format": format_id,
        # If user selected video-only, yt-dlp may need merging with audio
        "merge_output_format": "mp4",
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 20,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(info)

        # If merged, yt-dlp may change ext; try to locate final file
        if not os.path.exists(downloaded_path):
            base = os.path.splitext(downloaded_path)[0]
            for ext in ("mp4", "mkv", "webm", "m4a", "mp3"):
                cand = base + "." + ext
                if os.path.exists(cand):
                    downloaded_path = cand
                    break

        delete_file_later(downloaded_path, delay=180)

        return send_file(downloaded_path, as_attachment=True)

    except Exception as e:
        return jsonify({"ok": False, "error": f"Download failed: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
