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
    status.innerText = "🔍 Fetching formats...";
    formatsBox.style.display = "none";
    formatsBox.innerHTML = "";

    fetch("/formats", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url})
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            status.innerText = "❌ " + data.error;
            progress.style.width = "0%";
            return;
        }

        progress.style.width = "50%";
        status.innerText = "✅ Select a format";

        formatsBox.style.display = "block";

        data.formats.forEach(f => {
            const btn = document.createElement("button");
            btn.style.marginTop = "8px";
            btn.innerHTML = `${f.ext.toUpperCase()} | ${f.resolution} | ${f.filesize} MB`;
            btn.onclick = () => downloadSelected(url, f.format_id);
            formatsBox.appendChild(btn);
        });
    })
    .catch(() => {
        status.innerText = "❌ Server error";
        progress.style.width = "0%";
    });
}

function downloadSelected(url, format_id) {
    const status = document.getElementById("status");
    const progress = document.getElementById("progress");

    progress.style.width = "70%";
    status.innerText = "⬇ Downloading...";

    fetch("/download", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url, format_id})
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
    });
}
