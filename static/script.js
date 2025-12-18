function $(id){ return document.getElementById(id); }

function resValue(res){
  if(!res) return 0;
  const m = String(res).match(/(\d{3,4})/g);
  if(!m) return 0;
  return parseInt(m[m.length-1], 10) || 0;
}

function setStatus(text){ $("status").innerText = text; }
function setProgress(p){ $("progress").style.width = p + "%"; }

function showCaptcha(){
  const box = $("captcha-box");
  if(box) box.style.display = "block";
}

function hideCaptcha(){
  const box = $("captcha-box");
  if(box) box.style.display = "none";
  if(window.grecaptcha) grecaptcha.reset();
}

function captchaToken(){
  if(!window.grecaptcha) return "";
  return grecaptcha.getResponse() || "";
}

function clearFormats(){
  const box = $("formats-box");
  box.style.display = "none";
  box.innerHTML = "";
}

function renderTitle(box, text){
  const h = document.createElement("h3");
  h.innerText = text;
  h.style.marginTop = "14px";
  h.style.fontSize = "16px";
  h.style.textAlign = "left";
  box.appendChild(h);
}

function renderButton(box, label, onClick, tagText){
  const btn = document.createElement("button");
  btn.type = "button";
  btn.style.marginTop = "8px";
  btn.style.background = "#f1f1f1";
  btn.style.color = "#000";
  btn.style.borderRadius = "8px";
  btn.style.padding = "10px";
  btn.style.width = "100%";
  btn.style.border = "none";
  btn.style.cursor = "pointer";
  btn.style.textAlign = "left";

  btn.onmouseenter = () => { btn.style.background = "#007BFF"; btn.style.color = "#fff"; };
  btn.onmouseleave = () => { btn.style.background = "#f1f1f1"; btn.style.color = "#000"; };

  const row = document.createElement("div");
  row.style.display = "flex";
  row.style.justifyContent = "space-between";
  row.style.alignItems = "center";
  row.style.gap = "10px";

  const left = document.createElement("div");
  left.innerText = label;
  left.style.fontSize = "14px";
  left.style.fontWeight = "600";

  const tag = document.createElement("span");
  tag.innerText = tagText || "";
  tag.style.fontSize = "12px";
  tag.style.padding = "4px 8px";
  tag.style.borderRadius = "999px";
  tag.style.background = "rgba(0,0,0,0.06)";
  tag.style.whiteSpace = "nowrap";

  row.appendChild(left);
  if(tagText) row.appendChild(tag);

  btn.appendChild(row);
  btn.onclick = onClick;

  box.appendChild(btn);
}

function renderActions(box){
  const wrap = document.createElement("div");
  wrap.style.marginTop = "12px";
  wrap.style.display = "flex";
  wrap.style.gap = "10px";

  const retry = document.createElement("button");
  retry.type = "button";
  retry.innerText = "🔁 Retry";
  retry.style.flex = "1";
  retry.style.padding = "10px";
  retry.style.borderRadius = "8px";
  retry.style.border = "none";
  retry.style.cursor = "pointer";
  retry.style.background = "#28a745";
  retry.style.color = "#fff";
  retry.onclick = () => startDownload(true);

  const clear = document.createElement("button");
  clear.type = "button";
  clear.innerText = "🧹 Clear";
  clear.style.flex = "1";
  clear.style.padding = "10px";
  clear.style.borderRadius = "8px";
  clear.style.border = "none";
  clear.style.cursor = "pointer";
  clear.style.background = "#6c757d";
  clear.style.color = "#fff";
  clear.onclick = () => { hideCaptcha(); clearFormats(); setStatus(""); setProgress(0); };

  wrap.appendChild(retry);
  wrap.appendChild(clear);
  box.appendChild(wrap);
}

let lastUrl = "";

function startDownload(isRetry=false){
  const url = $("url").value.trim();
  if(!url){
    setStatus("❌ Please enter a URL");
    return;
  }

  lastUrl = url;
  clearFormats();

  if(isRetry){
    // retry requires captcha
    showCaptcha();
    const t = captchaToken();
    if(!t){
      setStatus("❌ Please verify CAPTCHA first");
      return;
    }
  } else {
    hideCaptcha();
  }

  setProgress(20);
  setStatus("🔍 Fetching available formats...");

  fetch("/formats", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ url })
  })
  .then(r => r.json().then(j => ({ok:r.ok, json:j})))
  .then(({ok, json}) => {
    if(!ok){
      // restricted flow
      if(json && json.restricted){
        setProgress(0);
        setStatus("⚠️ Restricted/login detected. Complete CAPTCHA and press Retry.");
        showCaptcha();

        const box = $("formats-box");
        box.style.display = "block";
        renderTitle(box, "⚠️ Restricted Video");
        const p = document.createElement("p");
        p.innerText = "This video may require login. CAPTCHA cannot bypass login, but you can retry for public videos.";
        p.style.textAlign = "left";
        p.style.fontSize = "13px";
        p.style.color = "#444";
        p.style.marginTop = "6px";
        box.appendChild(p);

        renderActions(box);
        return;
      }

      setProgress(0);
      setStatus("❌ " + (json.error || "Failed to fetch formats"));
      return;
    }

    setProgress(60);
    setStatus("✅ Select a format to download");

    const box = $("formats-box");
    box.style.display = "block";
    box.innerHTML = "";

    if(json.title){
      const titleLine = document.createElement("p");
      titleLine.innerText = "🎬 " + json.title;
      titleLine.style.textAlign = "left";
      titleLine.style.fontWeight = "700";
      titleLine.style.marginTop = "6px";
      titleLine.style.marginBottom = "4px";
      box.appendChild(titleLine);
    }

    const formats = Array.isArray(json.formats) ? json.formats : [];

    const videos = formats
      .filter(f => f.vcodec && f.vcodec !== "none")
      .map(f => ({...f, h: resValue(f.resolution)}))
      .sort((a,b) => (b.h - a.h) || ((b.filesize||0) - (a.filesize||0)));

    const audios = formats
      .filter(f => f.vcodec === "none")
      .map(f => ({...f, abr: Number(f.abr || 0)}))
      .sort((a,b) => (b.abr - a.abr) || ((b.filesize||0) - (a.filesize||0)));

    renderTitle(box, "📹 Video Formats");
    if(videos.length === 0){
      const p = document.createElement("p");
      p.innerText = "No video formats found.";
      p.style.textAlign = "left";
      p.style.fontSize = "13px";
      p.style.color = "#444";
      box.appendChild(p);
    } else {
      videos.forEach(v => {
        const ext = (v.ext || "").toUpperCase();
        const res = v.resolution || "Video";
        const size = (v.filesize != null) ? `${v.filesize} MB` : "";
        const label = `${ext} | ${res} | ${size}`;
        const tag = v.h ? `${v.h}p` : ext;
        renderButton(box, label, () => downloadSelected(lastUrl, v.format_id), tag);
      });
    }

    renderTitle(box, "🎵 Audio Formats");
    if(audios.length === 0){
      const p = document.createElement("p");
      p.innerText = "No audio formats found.";
      p.style.textAlign = "left";
      p.style.fontSize = "13px";
      p.style.color = "#444";
      box.appendChild(p);
    } else {
      audios.forEach(a => {
        const ext = (a.ext || "").toUpperCase();
        const abr = a.abr ? `${a.abr} kbps` : "Audio";
        const size = (a.filesize != null) ? `${a.filesize} MB` : "";
        const label = `${ext} | ${abr} | ${size}`;
        const tag = a.abr ? `${a.abr} kbps` : ext;
        renderButton(box, label, () => downloadSelected(lastUrl, a.format_id), tag);
      });
    }

    renderActions(box);
    setProgress(80);
  })
  .catch(() => {
    setProgress(0);
    setStatus("❌ Server error");
  });
}

function downloadSelected(url, format_id){
  setProgress(85);
  setStatus("⬇ Downloading...");

  const token = captchaToken();
  const payload = { url, format_id, captcha: token };

  fetch("/download", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  })
  .then(r => r.json().then(j => ({ok:r.ok, json:j})))
  .then(({ok, json}) => {
    if(!ok){
      if(json && json.restricted){
        setProgress(0);
        setStatus("⚠️ Restricted/login detected. Complete CAPTCHA and press Retry.");
        showCaptcha();
        return;
      }
      setProgress(0);
      setStatus("❌ " + (json.error || "Download failed"));
      return;
    }

    setProgress(100);
    setStatus("✅ Download ready!");
    window.location = "/file?path=" + encodeURIComponent(json.file);
  })
  .catch(() => {
    setProgress(0);
    setStatus("❌ Download failed");
  });
}
