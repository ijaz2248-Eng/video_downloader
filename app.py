from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os, time, threading, re, uuid
from collections import defaultdict
from urllib.parse import quote

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ===== RATE LIMITING =====
REQUEST_LIMIT = 8          # requests
TIME_WINDOW = 300          # seconds (5 minutes)
user_requests = defaultdict(list)

def get_client_ip():
    # Render / proxies
    ip = request.headers.get("X-Forwarded-For", "")
    if ip:
        return ip.split(",")[0].strip()
    return request.remote_addr or "unknown"

def is_rate_limited(ip):
    now = time.time()
    user_requests[ip] = [t for t in user_requests[ip] if now - t < TIME_WINDOW]
    if len(user_requests[ip]) >= REQUEST_LIMIT:
        return True
    user_requests[ip].append(now)
    return False

# ===== AUTO DELETE FILES =====
def delete_file_later(path, delay=90):
    def _del():
        time.sleep(delay)
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
    threading.Thread(target=_del, daemon=True).start()

def safe_filename(name: str) -> str:
    name = (name or "video").strip()
    name = re.sub(r"[^\w\-. ]+", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:80] if len(name) > 80 else name

def ytdlp_base_opts():
    # Keep it stable on cloud hosts
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 20,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

def normalize_formats(info):
    fmts = info.get("formats") or []
    out = []

    for f in fmts:
        # Skip useless entries
        if not f.get("url"):
            continue

        vcodec = f.get("vcodec") or "none"
        acodec = f.get("acodec") or "none"

        is_video = vcodec != "none"
        is_audio = acodec != "none"
        progressive = is_video and is_audio

        height = f.get("height") or 0
        fps = f.get("fps") or 0
        vbr = f.get("vbr") or 0
        abr = f.get("abr") or 0
        tbr = f.get("tbr") or 0
        ext = f.get("ext") or ""

        filesize = f.get("filesize") or f.get("filesize_approx") or 0
        size_mb = round(filesize / (1024 * 1024), 2) if filesize else None

        label_bits = []
        if progressive:
            label_bits.append("Video+Audio")
        elif is_video:
            label_bits.append("Video only")
        elif is_audio:
            label_bits.append("Audio only")

        if height:
            label_bits.append(f"{height}p")
        if fps:
            label_bits.append(f"{int(fps)}fps")
        if abr and is_audio and not is_video:
            label_bits.append(f"{int(abr)}kbps")
        elif tbr:
            label_bits.append(f"{int(tbr)}kbps")

        if ext:
            label_bits.append(ext.upper())

        display = " • ".join(label_bits) if label_bits else (f.get("format") or f.get("format_id"))

        out.append({
            "format_id": f.get("format_id"),
            "ext": ext,
            "height": height,
            "fps": fps,
            "vcodec": vcodec,
            "acodec": acodec,
            "filesize_mb": size_mb,
            "progressive": progressive,
            "video_only": (is_video and not is_audio),
            "audio_only": (is_audio and not is_video),
            "tbr": tbr,
            "display": display
        })

    # Sort: best video first, then progressive, then audio
    def sort_key(x):
        return (
            0 if x["progressive"] else (1 if x["video_only"] else 2),
            -(x["height"] or 0),
            -(x["tbr"] or 0),
        )

    out.sort(key=sort_key)
    return out

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/formats")
def api_formats():
    ip = get_client_ip()
    if is_rate_limited(ip):
        return jsonify({"ok": False, "error": "Too many requests. Please wait a few minutes and try again."}), 429

    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Please paste a valid video URL."}), 400

    try:
        opts = ytdlp_base_opts()
        opts.update({
            "skip_download": True,
            "dump_single_json": True,
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Some sites return "entries" for playlists even with noplaylist; handle first entry
        if isinstance(info, dict) and info.get("_type") == "playlist" and info.get("entries"):
            info = next((e for e in info["entries"] if e), info)

        title = info.get("title") or "Video"
        thumb = info.get("thumbnail")
        webpage_url = info.get("webpage_url") or url
        duration = info.get("duration")  # seconds

        formats = normalize_formats(info)

        # Split into groups for UI
        progressive = [f for f in formats if f["progressive"]]
        video_only = [f for f in formats if f["video_only"]]
        audio_only = [f for f in formats if f["audio_only"]]

        return jsonify({
            "ok": True,
            "title": title,
            "thumbnail": thumb,
            "duration": duration,
            "webpage_url": webpage_url,
            "groups": {
                "progressive": progressive[:20],
                "video_only": video_only[:20],
                "audio_only": audio_only[:20],
            }
        })

    except Exception as e:
        msg = str(e)
        # Make error user-friendly (no scary traceback)
        return jsonify({
            "ok": False,
            "error": "Could not fetch formats for this link. Try a different link or try again later.",
            "debug": msg[:500]
        }), 200

@app.get("/download")
def download():
    ip = get_client_ip()
    if is_rate_limited(ip):
        return jsonify({"ok": False, "error": "Too many requests. Please wait and try again."}), 429

    url = (request.args.get("url") or "").strip()
    format_id = (request.args.get("format_id") or "").strip()
    kind = (request.args.get("kind") or "").strip()  # progressive|video_only|audio_only

    if not url or not format_id:
        return jsonify({"ok": False, "error": "Missing url/format_id"}), 400

    file_id = str(uuid.uuid4())[:8]
    outtmpl = os.path.join(DOWNLOAD_FOLDER, f"{file_id}.%(ext)s")

    try:
        opts = ytdlp_base_opts()
        opts.update({
            "format": format_id,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "postprocessors": [
                # If audio-only, let yt-dlp keep original ext; no forced conversion here
            ],
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Find the downloaded file
        final_path = None
        for fn in os.listdir(DOWNLOAD_FOLDER):
            if fn.startswith(file_id + "."):
                final_path = os.path.join(DOWNLOAD_FOLDER, fn)
                break

        if not final_path or not os.path.exists(final_path):
            return jsonify({"ok": False, "error": "Download failed. Please try another format."}), 500

        delete_file_later(final_path, delay=120)

        title = safe_filename((info.get("title") if isinstance(info, dict) else "video") or "video")
        ext = os.path.splitext(final_path)[1].lstrip(".") or "mp4"
        download_name = f"{title}.{ext}"

        return send_file(final_path, as_attachment=True, download_name=download_name)

    except Exception:
        return jsonify({"ok": False, "error": "Download failed for this format. Try another one."}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
