from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import time
import threading
import requests
from collections import defaultdict

app = Flask(__name__)

# ================= CONFIG =================
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

RECAPTCHA_SECRET = "6Ld5ay4sAAAAAHsmqRhd31pNmaw6vEhVqsHzR7d-"

REQUEST_LIMIT = 5
TIME_WINDOW = 300  # 5 minutes

user_requests = defaultdict(list)

# ================= RATE LIMIT =================
def is_rate_limited(ip):
    now = time.time()
    user_requests[ip] = [t for t in user_requests[ip] if now - t < TIME_WINDOW]
    if len(user_requests[ip]) >= REQUEST_LIMIT:
        return True
    user_requests[ip].append(now)
    return False

# ================= AUTO DELETE =================
def delete_file_later(path, delay=120):
    def delete():
        time.sleep(delay)
        if os.path.exists(path):
            os.remove(path)
    threading.Thread(target=delete, daemon=True).start()

# ================= CAPTCHA =================
def verify_captcha(token):
    try:
        response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": RECAPTCHA_SECRET,
                "response": token
            },
            timeout=10
        ).json()
        return response.get("success", False)
    except:
        return False

# ================= ROUTES =================
@app.route("/")
def index():
    return render_template("index.html")

# ---------- GET FORMATS ----------
@app.route("/formats", methods=["POST"])
def get_formats():
    data = request.json or {}
    url = data.get("url")

    if not url:
        return jsonify({"error": "Invalid URL"}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True
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
                "acodec": f.get("acodec")
            })

        return jsonify({
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "formats": formats
        })

    except yt_dlp.utils.DownloadError:
        return jsonify({
            "error": "This video cannot be downloaded (restricted or login required)."
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
    captcha_token = data.get("captcha", "")

    if not url or not format_id:
        return jsonify({"error": "Invalid request"}), 400

    if captcha_token:
        if not verify_captcha(captcha_token):
            return jsonify({"error": "CAPTCHA verification failed"}), 403

    try:
        ydl_opts = {
            "format": format_id,
            "outtmpl": f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
            "merge_output_format": "mp4",
            "quiet": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        return jsonify({
            "success": True,
            "file": filename
        })

    except yt_dlp.utils.DownloadError as e:
        if "Sign in" in str(e) or "age restricted" in str(e):
            return jsonify({
                "error": "This video cannot be downloaded (restricted or login required)."
            }), 403
        return jsonify({"error": "Download failed"}), 500

# ---------- SERVE FILE ----------
@app.route("/file")
def serve_file():
    path = request.args.get("path")

    if not path or not os.path.exists(path):
        return "File not found", 404

    delete_file_later(path)
    return send_file(path, as_attachment=True)

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
