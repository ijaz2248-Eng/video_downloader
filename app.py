from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os, time, threading, requests
from collections import defaultdict

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ===== RATE LIMITING =====
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

# ===== AUTO DELETE FILES =====
def delete_file_later(path, delay=60):
    def delete():
        time.sleep(delay)
        if os.path.exists(path):
            os.remove(path)
    threading.Thread(target=delete).start()

# ===== CAPTCHA Verification =====
def verify_captcha(token):
    secret_key = "6Ld5ay4sAAAAAHsmqRhd31pNmaw6vEhVqsHzR7d-"
    url = "https://www.google.com/recaptcha/api/siteverify"
    data = {"secret": secret_key, "response": token}
    try:
        response = requests.post(url, data=data).json()
        return response.get("success", False)
    except:
        return False

# ===== ROUTES =====
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    ip = request.remote_addr
    if is_rate_limited(ip):
        return jsonify({"error": "Too many requests. Try again later."}), 429

    data = request.json
    url = data.get("url")
    quality = data.get("quality")
    format_type = data.get("format")
    captcha_response = data.get("captcha") or ""  # Always get a string

    if not url:
        return jsonify({"error": "Invalid URL"}), 400

    # Verify CAPTCHA only if token is provided
    if captcha_response:
        if not verify_captcha(captcha_response):
            return jsonify({"error": "CAPTCHA verification failed"}), 403

    try:
        ydl_opts = {}
        if format_type == "mp3":
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            }
        else:
            ydl_opts = {
                "format": quality,
                "outtmpl": f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        return jsonify({"success": True, "file": filename})

    except yt_dlp.utils.DownloadError as e:
        if "Sign in" in str(e) or "age restricted" in str(e):
            return jsonify({"error": "This video cannot be downloaded (restricted or login required)."}), 403
        return jsonify({"error": str(e)}), 500

@app.route("/file")
def serve_file():
    path = request.args.get("path")
    if not path or not os.path.exists(path):
        return "File not found", 404

    delete_file_later(path, delay=60)
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
