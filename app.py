from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os, time, threading, requests
from collections import defaultdict

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ================= RATE LIMIT =================
REQUEST_LIMIT = 5
TIME_WINDOW = 300
user_requests = defaultdict(list)

def is_rate_limited(ip):
    now = time.time()
    user_requests[ip] = [t for t in user_requests[ip] if now - t < TIME_WINDOW]
    if len(user_requests[ip]) >= REQUEST_LIMIT:
        return True
    user_requests[ip].append(now)
    return False

# ================= AUTO DELETE =================
def delete_file_later(path, delay=60):
    def delete():
        time.sleep(delay)
        if os.path.exists(path):
            os.remove(path)
    threading.Thread(target=delete, daemon=True).start()

# ================= CAPTCHA =================
def verify_captcha(token):
    SECRET_KEY = "6Ld5ay4sAAAAAHsmqRhd31pNmaw6vEhVqsHzR7d-"
    try:
        res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": SECRET_KEY, "response": token},
            timeout=5
        ).json()
        return res.get("success", False)
    except:
        return False

# ================= ROUTES =================
@app.route("/")
def index():
    return render_template("index.html")

# ---------- FORMAT LIST ----------
@app.route("/formats", methods=["POST"])
def formats():
    data = request.json
    url = data.get("url")

    if not url:
        return jsonify({"error": "Invalid URL"}), 400

    try:
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        video_formats = []
        audio_formats = []

        for f in info.get("formats", []):
            size = f.get("filesize") or f.get("filesize_approx")
            if not size:
                continue

            size_mb = round(size / 1024 / 1024, 2)

            # ---------- AUDIO ----------
            if f.get("vcodec") == "none" and f.get("acodec") != "none":
                audio_formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "bitrate": f.get("abr") or 0,
                    "filesize": size_mb
                })

            # ---------- VIDEO ----------
            elif f.get("vcodec") != "none":
                video_formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution") or f.get("format_note"),
                    "filesize": size_mb
                })

        # Sorting
        video_formats.sort(key=lambda x: (
            int("".join(filter(str.isdigit, str(x["resolution"]))) or 0)
        ), reverse=True)

        audio_formats.sort(key=lambda x: x["bitrate"], reverse=True)

        return jsonify({
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "video": video_formats,
            "audio": audio_formats
        })

    except Exception:
        return jsonify({
            "restricted": True,
            "message": "Restricted video. CAPTCHA required."
        }), 403

# ---------- DOWNLOAD ----------
@app.route("/download", methods=["POST"])
def download():
    ip = request.remote_addr
    if is_rate_limited(ip):
        return jsonify({"error": "Too many requests"}), 429

    data = request.json
    url = data.get("url")
    format_id = data.get("format_id")
    captcha = data.get("captcha", "")

    if not url or not format_id:
        return jsonify({"error": "Invalid request"}), 400

    # CAPTCHA only when provided
    if captcha and not verify_captcha(captcha):
        return jsonify({"error": "CAPTCHA verification failed"}), 403

    try:
        ydl_opts = {
            "format": format_id,
            "outtmpl": f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        return jsonify({"success": True, "file": filename})

    except yt_dlp.utils.DownloadError as e:
        return jsonify({
            "restricted": True,
            "message": "Login / age restricted. CAPTCHA required."
        }), 403

# ---------- FILE ----------
@app.route("/file")
def file():
    path = request.args.get("path")
    if not path or not os.path.exists(path):
        return "File not found", 404

    delete_file_later(path)
    return send_file(path, as_attachment=True)

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
