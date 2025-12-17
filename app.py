from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import time
from collections import defaultdict
import threading

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

    if not url:
        return jsonify({"error": "Invalid URL"}), 400

    try:
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
            info = ydl.extract_info(url)
            filename = ydl.prepare_filename(info)

        return jsonify({"success": True, "file": filename})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/file")
def serve_file():
    path = request.args.get("path")
    if not path or not os.path.exists(path):
        return "File not found", 404

    # Schedule deletion after 60 seconds
    delete_file_later(path, delay=60)
    return send_file(path, as_attachment=True)

# ===== RUN APP =====
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
