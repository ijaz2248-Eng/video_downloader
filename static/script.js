function startDownload() {
    const url = document.getElementById("url").value;
    const status = document.getElementById("status");
    const progress = document.getElementById("progress");
    const formatsBox = document.getElementById("formats-box");

    if (!url) {
        status.innerText = "❌ Please enter a URL";
        return;
    }

    progress.style.width = "20%";
    status.innerText = "🔍 Fetching available formats...";
    formatsBox.style.display = "none";
    formatsBox.innerHTML = "";

    fetch("/formats", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            status.innerText = "❌ " + data.error;
            progress.style.width = "0%";
            return;
        }

        progress.style.width = "60%";
        status.innerText = "✅ Select a format to download";

        formatsBox.style.display = "block";

        // Title
        const title = document.createElement("h3");
        title.innerText = "🎬 " + data.title;
        title.style.marginTop = "10px";
        formatsBox.appendChild(title);

        // VIDEO FORMATS
        const videoTitle = document.createElement("h4");
        videoTitle.innerText = "📹 Video Formats";
        videoTitle.style.marginTop = "15px";
        formatsBox.appendChild(videoTitle);

        data.formats
            .filter(f => f.vcodec !== "none")
            .forEach(f => {
                const btn = document.createElement("button");
                btn.innerText = `${f.ext.toUpperCase()} | ${f.resolution} | ${f.filesize} MB`;
                btn.onclick = () => downloadSelected(url, f.format_id);
                formatsBox.appendChild(btn);
            });

        // AUDIO FORMATS
        const audioTitle = document.createElement("h4");
        audioTitle.innerText = "🎵 Audio Formats";
        audioTitle.style.marginTop = "15px";
        formatsBox.appendChild(audioTitle);

        data.formats
            .filter(f => f.vcodec === "none")
            .forEach(f => {
                const btn = document.createElement("button");
                btn.innerText = `${f.ext.toUpperCase()} | Audio | ${f.filesize} MB`;
                btn.onclick = () => downloadSelected(url, f.format_id);
                formatsBox.appendChild(btn);
            });

        progress.style.width = "80%";
    })
    .catch(() => {
        status.innerText = "❌ Server error";
        progress.style.width = "0%";
    });
}

function downloadSelected(url, format_id) {
    const status = document.getElementById("status");
    const progress = document.getElementById("progress");

    progress.style.width = "85%";
    status.innerText = "⬇ Downloading...";

    fetch("/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, format_id })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            status.innerText = "❌ " + data.error;
            progress.style.width = "0%";
        } else {
            progress.style.width = "100%";
            status.innerText = "✅ Download ready!";
            window.location = "/file?path=" + encodeURIComponent(data.file);
        }
    })
    .catch(() => {
        status.innerText = "❌ Download failed";
        progress.style.width = "0%";
    });
}
