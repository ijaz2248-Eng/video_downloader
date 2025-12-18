from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import time
import threading
import requests
from collections import defaultdict

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ===== RATE LIMITING =====
REQUEST_LIMIT = 5
TIME_WINDOW = 300  # 5 minutes
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
    def delete():
        time.sleep(delay)
        if os.path.exists(path):
            os.remove(path)
    threading.Thread(target=delete, daemon=True).start()

# ===== CAPTCHA Verification =====
def verify_captcha(token):
    secret_key = "6Ld5ay4sAAAAAHsmqRhd31pNmaw6vEhVqsHzR7d-"
    url = "https://www.google.com/recaptcha/api/siteverify"
    data = {"secret": secret_key, "response": token}
    try:
        response = requests.post(url, data=data, timeout=10).json()
        return response.get("success", False)
    except:
        return False

# ===== ROUTES =====
@app.route("/")
def index():
    return render_template("index.html")

# ---------- FORMATS (Public videos) ----------
@app.route("/formats", methods=["POST"])
def get_formats():
    data = request.json or {}
    url = data.get("url")

    if not url:
        return jsonify({"error": "Invalid URL"}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []
        for f in info.get("formats", []):
            size = f.get("filesize") or f.get("filesize_approx")
            if not size:
                continue

            formats.append({
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f.get("resolution") or f.get("format_note"),
                "filesize": round(size / 1024 / 1024, 2),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "abr": f.get("abr") or 0
            })

        return jsonify({
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "formats": formats
        })

    except:
        return jsonify({
            "restricted": True,
            "error": "Restricted/login detected. Complete CAPTCHA and retry."
        }), 403

# ---------- DOWNLOAD ----------
@app.route("/download", methods=["POST"])
def download():
    ip = request.remote_addr
    if is_rate_limited(ip):
        return jsonify({"error": "Too many requests. Try again later."}), 429

    data = request.json or {}
    url = data.get("url")
    format_id = data.get("format_id")
    captcha_response = data.get("captcha", "")

    if not url or not format_id:
        return jsonify({"error": "Invalid request"}), 400

    # Verify CAPTCHA only if token is provided
    if captcha_response:
        if not verify_captcha(captcha_response):
            return jsonify({"error": "CAPTCHA verification failed"}), 403

    try:
        ydl_opts = {
            "format": format_id,
            "outtmpl": f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
            "noplaylist": True,
            "quiet": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        return jsonify({"success": True, "file": filename})

    except yt_dlp.utils.DownloadError as e:
        if "Sign in" in str(e) or "age restricted" in str(e):
            return jsonify({
                "restricted": True,
                "error": "Restricted/login detected. Complete CAPTCHA and retry."
            }), 403
        return jsonify({"error": "Download failed"}), 500

@app.route("/file")
def serve_file():
    path = request.args.get("path")
    if not path or not os.path.exists(path):
        return "File not found", 404

    delete_file_later(path)
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
