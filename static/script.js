const urlEl = document.getElementById("url");
const btnFetch = document.getElementById("btnFetch");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const titleEl = document.getElementById("title");
const thumbEl = document.getElementById("thumb");
const platformBadge = document.getElementById("platformBadge");
const btnClear = document.getElementById("btnClear");

const listsWrap = document.getElementById("lists");
const listEls = {
  progressive: document.querySelector('[data-list="progressive"]'),
  video_only: document.querySelector('[data-list="video_only"]'),
  audio_only: document.querySelector('[data-list="audio_only"]'),
};

const tabs = Array.from(document.querySelectorAll(".tab"));

function setStatus(msg, isError=false){
  statusEl.classList.remove("hidden");
  statusEl.classList.toggle("error", isError);
  statusEl.textContent = msg;
}
function clearStatus(){
  statusEl.classList.add("hidden");
  statusEl.classList.remove("error");
  statusEl.textContent = "";
}

function escapeHtml(s){
  return (s||"").replace(/[&<>"']/g, m => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[m]));
}

function formatLabel(f){
  const res = f.resolution || "—";
  const ext = (f.ext || "").toUpperCase();
  const fps = f.fps ? `${f.fps}fps` : "";
  const size = f.filesize_h || "";
  const v = f.vcodec && f.vcodec !== "none" ? f.vcodec : "";
  const a = f.acodec && f.acodec !== "none" ? f.acodec : "";
  const note = f.format_note || "";
  return { res, ext, fps, size, v, a, note };
}

function buildItem(url, f){
  const {res, ext, fps, size, v, a, note} = formatLabel(f);
  const line1 = `${res} ${note ? "• " + note : ""}`.trim();
  const line2parts = [];
  if (ext) line2parts.push(ext);
  if (fps) line2parts.push(fps);
  if (size) line2parts.push(size);
  if (v) line2parts.push(`v:${v}`);
  if (a) line2parts.push(`a:${a}`);
  const line2 = line2parts.join(" • ");

  const downloadUrl = `/download?url=${encodeURIComponent(url)}&format_id=${encodeURIComponent(f.format_id)}`;

  const div = document.createElement("div");
  div.className = "item";
  div.innerHTML = `
    <div class="itemLeft">
      <div class="line1">${escapeHtml(line1)} <span class="pill">${escapeHtml(f.format_id)}</span></div>
      <div class="line2">${escapeHtml(line2 || " ")}</div>
    </div>
    <a class="btn downloadBtn" href="${downloadUrl}">Download</a>
  `;
  return div;
}

function renderList(url, key, items){
  const el = listEls[key];
  el.innerHTML = "";
  if (!items || items.length === 0){
    const empty = document.createElement("div");
    empty.className = "status";
    empty.textContent = "No formats found in this category.";
    el.appendChild(empty);
    return;
  }
  items.forEach(f => el.appendChild(buildItem(url, f)));
}

function setActiveTab(tabKey){
  tabs.forEach(t => t.classList.toggle("active", t.dataset.tab === tabKey));
  Object.entries(listEls).forEach(([k, el]) => {
    el.classList.toggle("hidden", k !== tabKey);
  });
}

tabs.forEach(t => t.addEventListener("click", () => setActiveTab(t.dataset.tab)));

btnClear.addEventListener("click", () => {
  urlEl.value = "";
  resultEl.classList.add("hidden");
  clearStatus();
});

btnFetch.addEventListener("click", async () => {
  const url = (urlEl.value || "").trim();
  if (!url) return setStatus("Please paste a video URL.", true);

  clearStatus();
  setStatus("Fetching formats…");

  try{
    const res = await fetch("/info", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({url})
    });
    const data = await res.json();

    if (!data.ok){
      setStatus(data.error || "Failed to fetch formats.", true);
      resultEl.classList.add("hidden");
      return;
    }

    platformBadge.textContent = data.platform || "Video";
    titleEl.textContent = data.title || "Untitled";
    if (data.thumbnail){
      thumbEl.src = data.thumbnail;
      thumbEl.style.display = "";
    } else {
      thumbEl.style.display = "none";
    }

    renderList(url, "progressive", data.progressive);
    renderList(url, "video_only", data.video_only);
    renderList(url, "audio_only", data.audio_only);

    resultEl.classList.remove("hidden");
    setActiveTab("progressive");
    clearStatus();
  }catch(e){
    setStatus("Server error. Please try again.\n\n" + e, true);
    resultEl.classList.add("hidden");
  }
});
