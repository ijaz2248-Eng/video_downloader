const el = (id) => document.getElementById(id);

const videoUrl = el("videoUrl");
const btnFormats = el("btnFormats");
const alertBox = el("alertBox");

const previewCard = el("previewCard");
const thumb = el("thumb");
const videoTitle = el("videoTitle");
const metaLine = el("metaLine");

const formatsWrap = el("formatsWrap");
const formatsList = el("formatsList");
const countLabel = el("countLabel");

const filterAll = el("filterAll");
const filterVideoAudio = el("filterVideoAudio");
const filterVideoOnly = el("filterVideoOnly");
const filterAudioOnly = el("filterAudioOnly");
const btnClear = el("btnClear");

let allFormats = [];
let lastUrl = "";
let currentFilter = "all";

function showAlert(type, msg){
  alertBox.className = `alert alert-${type}`;
  alertBox.textContent = msg;
  alertBox.classList.remove("d-none");
}
function hideAlert(){
  alertBox.classList.add("d-none");
}

function bytesToSize(bytes){
  if(!bytes || isNaN(bytes)) return "—";
  const sizes = ["B","KB","MB","GB"];
  let i = 0;
  let num = bytes;
  while(num >= 1024 && i < sizes.length-1){ num/=1024; i++; }
  return `${num.toFixed(i===0?0:1)} ${sizes[i]}`;
}

function classifyFormat(f){
  // Works with yt-dlp style fields.
  const vcodec = (f.vcodec || "").toLowerCase();
  const acodec = (f.acodec || "").toLowerCase();

  const hasVideo = vcodec && vcodec !== "none";
  const hasAudio = acodec && acodec !== "none";

  if(hasVideo && hasAudio) return "va";
  if(hasVideo && !hasAudio) return "v";
  if(!hasVideo && hasAudio) return "a";
  return "other";
}

function applyFilter(){
  let list = allFormats;
  if(currentFilter === "va") list = allFormats.filter(f => classifyFormat(f) === "va");
  if(currentFilter === "v")  list = allFormats.filter(f => classifyFormat(f) === "v");
  if(currentFilter === "a")  list = allFormats.filter(f => classifyFormat(f) === "a");

  renderFormats(list);
}

function renderFormats(list){
  formatsList.innerHTML = "";
  countLabel.textContent = `${list.length} items`;

  if(list.length === 0){
    formatsList.innerHTML = `<div class="format-item">No formats found for this filter.</div>`;
    return;
  }

  for(const f of list){
    const fmt = f.format_id ?? f.formatId ?? "";
    const ext = f.ext ?? "—";
    const res = f.resolution ?? (f.height ? `${f.height}p` : "—");
    const fps = f.fps ? `${f.fps}fps` : "—";
    const vcodec = f.vcodec ?? "—";
    const acodec = f.acodec ?? "—";
    const abr = f.abr ? `${Math.round(f.abr)}kbps` : "—";
    const vbr = f.vbr ? `${Math.round(f.vbr)}kbps` : "—";
    const size = bytesToSize(f.filesize || f.filesize_approx);

    const kind = classifyFormat(f);
    const badge =
      kind === "va" ? "Video+Audio" :
      kind === "v"  ? "Video Only" :
      kind === "a"  ? "Audio Only" : "Format";

    const downloadUrl = `/download?url=${encodeURIComponent(lastUrl)}&format_id=${encodeURIComponent(fmt)}`;

    const item = document.createElement("div");
    item.className = "format-item";
    item.innerHTML = `
      <div class="format-top">
        <div class="fw-bold">${badge} • <span class="text-white-50">${ext.toUpperCase()}</span></div>
        <a class="btn btn-primary btn-sm px-3" href="${downloadUrl}">Download</a>
      </div>
      <div class="kv">
        <span>Format: ${fmt}</span>
        <span>Resolution: ${res}</span>
        <span>FPS: ${fps}</span>
        <span>Size: ${size}</span>
        <span>V: ${vcodec}</span>
        <span>A: ${acodec}</span>
        <span>VBR: ${vbr}</span>
        <span>ABR: ${abr}</span>
      </div>
    `;
    formatsList.appendChild(item);
  }
}

async function getFormats(){
  hideAlert();
  const url = videoUrl.value.trim();
  if(!url){
    showAlert("warning", "Please paste a video URL.");
    return;
  }

  btnFormats.disabled = true;
  btnFormats.textContent = "Loading…";

  try{
    const res = await fetch("/formats", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ url })
    });

    const data = await res.json();
    if(!res.ok){
      showAlert("danger", data.error || "Failed to fetch formats.");
      return;
    }

    lastUrl = url;

    // Expecting yt-dlp style response (adjust if your backend uses different keys)
    const title = data.title || "Video";
    const uploader = data.uploader || data.channel || "";
    const duration = data.duration ? `${Math.round(data.duration)}s` : "";
    const webpage = data.webpage_url || url;

    videoTitle.textContent = title;
    metaLine.textContent = [uploader, duration, webpage].filter(Boolean).join(" • ");

    if(data.thumbnail){
      thumb.src = data.thumbnail;
      thumb.classList.remove("d-none");
    }else{
      thumb.classList.add("d-none");
    }

    allFormats = (data.formats || []).slice();

    // Sort: higher resolution first, then bitrate
    allFormats.sort((a,b) => {
      const ah = a.height || 0, bh = b.height || 0;
      if(bh !== ah) return bh - ah;
      const av = a.vbr || 0, bv = b.vbr || 0;
      if(bv !== av) return bv - av;
      const aa = a.abr || 0, ba = b.abr || 0;
      return ba - aa;
    });

    previewCard.classList.remove("d-none");
    formatsWrap.classList.remove("d-none");
    currentFilter = "all";
    applyFilter();

  }catch(e){
    showAlert("danger", "Server error: " + (e?.message || e));
  }finally{
    btnFormats.disabled = false;
    btnFormats.textContent = "Get formats";
  }
}

function clearAll(){
  hideAlert();
  videoUrl.value = "";
  lastUrl = "";
  allFormats = [];
  formatsList.innerHTML = "";
  formatsWrap.classList.add("d-none");
  previewCard.classList.add("d-none");
  thumb.classList.add("d-none");
  videoTitle.textContent = "—";
  metaLine.textContent = "—";
}

btnFormats.addEventListener("click", getFormats);
videoUrl.addEventListener("keydown", (e) => {
  if(e.key === "Enter") getFormats();
});

filterAll.addEventListener("click", ()=>{ currentFilter="all"; applyFilter(); });
filterVideoAudio.addEventListener("click", ()=>{ currentFilter="va"; applyFilter(); });
filterVideoOnly.addEventListener("click", ()=>{ currentFilter="v"; applyFilter(); });
filterAudioOnly.addEventListener("click", ()=>{ currentFilter="a"; applyFilter(); });
btnClear.addEventListener("click", clearAll);
