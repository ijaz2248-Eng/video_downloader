const urlEl = document.getElementById("url");
const btn = document.getElementById("btn");
const statusEl = document.getElementById("status");
const listEl = document.getElementById("list");
const clearBtn = document.getElementById("clear");

const videoBox = document.getElementById("videoBox");
const thumbEl = document.getElementById("thumb");
const titleEl = document.getElementById("title");
const openLinkEl = document.getElementById("openLink");
const toolbar = document.getElementById("toolbar");

let lastUrl = "";
let allFormats = [];
let activeFilter = "all";

function setStatus(msg, type="") {
  statusEl.className = "status " + type;
  statusEl.textContent = msg || "";
}

function fmtSize(bytes){
  if(!bytes || bytes <= 0) return "";
  const units = ["B","KB","MB","GB"];
  let i = 0, n = bytes;
  while(n >= 1024 && i < units.length-1){ n /= 1024; i++; }
  return `${n.toFixed(i===0?0:1)} ${units[i]}`;
}

function render(){
  listEl.innerHTML = "";
  const shown = allFormats.filter(f => activeFilter === "all" ? true : f.kind === activeFilter);

  if(shown.length === 0){
    listEl.innerHTML = `<div class="small">No formats found for this filter.</div>`;
    return;
  }

  for(const f of shown){
    const label = `${f.ext?.toUpperCase() || ""} • ${f.kind}`;
    const q = f.kind === "audio"
      ? `Audio • ${Math.round(f.tbr||0)} kbps`
      : `Quality • ${f.height ? f.height+"p" : "—"} ${f.fps ? "• "+f.fps+"fps" : ""}`;

    const size = fmtSize(f.filesize);

    const a = document.createElement("a");
    a.className = "item";
    a.href = `/download?url=${encodeURIComponent(lastUrl)}&format_id=${encodeURIComponent(f.format_id)}`;
    a.target = "_blank";
    a.rel = "noreferrer";

    a.innerHTML = `
      <div class="left">
        <div class="badge">${label}</div>
        <div class="small">${q} • id: ${f.format_id}${size ? " • "+size : ""}</div>
      </div>
      <div class="dl">Download</div>
    `;
    listEl.appendChild(a);
  }
}

document.querySelectorAll(".chip").forEach(chip => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    activeFilter = chip.dataset.filter;
    render();
  });
});

clearBtn.addEventListener("click", () => {
  urlEl.value = "";
  lastUrl = "";
  allFormats = [];
  listEl.innerHTML = "";
  videoBox.classList.add("hidden");
  toolbar.classList.add("hidden");
  setStatus("");
});

btn.addEventListener("click", async () => {
  const url = urlEl.value.trim();
  if(!url){
    setStatus("Please paste a video URL.", "bad");
    return;
  }

  btn.disabled = true;
  setStatus("Fetching formats…", "");
  listEl.innerHTML = "";
  videoBox.classList.add("hidden");
  toolbar.classList.add("hidden");

  try{
    const r = await fetch("/api/formats", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({url})
    });

    const data = await r.json().catch(() => null);
    if(!data){
      setStatus("Server returned an invalid response (not JSON). Check Render logs.", "bad");
      return;
    }
    if(!r.ok || !data.ok){
      setStatus(data.error || "Failed to fetch formats.", "bad");
      return;
    }

    lastUrl = url;
    allFormats = data.formats || [];

    titleEl.textContent = data.title || "Video";
    openLinkEl.href = data.webpage_url || url;

    if(data.thumbnail){
      thumbEl.src = data.thumbnail;
      thumbEl.classList.remove("hidden");
    } else {
      thumbEl.src = "";
    }

    videoBox.classList.remove("hidden");
    toolbar.classList.remove("hidden");
    setStatus(`Found ${allFormats.length} formats.`, "good");
    render();

  } catch(e){
    setStatus("Request failed. Check network / Render service logs.", "bad");
  } finally{
    btn.disabled = false;
  }
});
