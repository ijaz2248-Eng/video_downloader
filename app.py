from flask import Flask, render_template, request, jsonify, send_file
import os, time, uuid
import yt_dlp

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.get("/")
def home():
    return render_template("index.html")

def ytdlp_extract(url: str):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {
            # Helps reduce “playlist”/related extraction surprises
            "youtube": {"player_client": ["android"]},
        },
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

@app.post("/api/formats")
def api_formats():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Please paste a video URL."}), 400

    try:
        info = ytdlp_extract(url)

        # Build a compact format list for UI
        formats = []
        for f in info.get("formats", []) or []:
            if not f.get("url"):
                continue
            formats.append({
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "height": f.get("height"),
                "fps": f.get("fps"),
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "tbr": f.get("tbr"),
                "format_note": f.get("format_note"),
            })

        # Sort by height then bitrate (best first)
        def sort_key(x):
            h = x["height"] or 0
            t = x["tbr"] or 0
            return (h, t)

        formats.sort(key=sort_key, reverse=True)

        return jsonify({
            "ok": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "webpage_url": info.get("webpage_url"),
            "formats": formats[:200],  # keep response reasonable
        })

    except Exception as e:
        # IMPORTANT: show real error so you can fix Render problems
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/download")
def api_download():
    url = (request.args.get("url") or "").strip()
    format_id = (request.args.get("format_id") or "").strip()
    if not url or not format_id:
        return jsonify({"ok": False, "error": "Missing url or format_id"}), 400

    out_id = str(uuid.uuid4())[:10]
    outtmpl = os.path.join(DOWNLOAD_FOLDER, f"{out_id}.%(ext)s")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "format": format_id,
        # If you want best “single file” often:
        # "format": "bv*+ba/best"  # but you are selecting format_id so keep it as-is
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Find the produced file
        # yt-dlp returns _filename sometimes; otherwise scan folder by prefix
        produced = None
        if info and info.get("_filename") and os.path.exists(info["_filename"]):
            produced = info["_filename"]
        else:
            for fn in os.listdir(DOWNLOAD_FOLDER):
                if fn.startswith(out_id + "."):
                    produced = os.path.join(DOWNLOAD_FOLDER, fn)
                    break

        if not produced or not os.path.exists(produced):
            return jsonify({"ok": False, "error": "Download completed but file not found."}), 500

        # Friendly filename
        safe_title = (info.get("title") or "video").replace("/", "_").replace("\\", "_")
        download_name = f"{safe_title}.{produced.split('.')[-1]}"

        return send_file(produced, as_attachment=True, download_name=download_name)

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
