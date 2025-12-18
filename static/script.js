const $ = (id) => document.getElementById(id);

function fmtBytes(n){
  if(!n) return "";
  const units = ["B","KB","MB","GB"];
  let i=0, v=n;
  while(v>=1024 && i<units.length-1){ v/=1024; i++; }
  return `${v.toFixed(i===0?0:1)} ${units[i]}`;
}

function formatLabel(f){
  const h = f.height ? `${f.height}p` : "audio/unknown";
  const ext = f.ext || "";
  const note = f.format_note ? ` • ${f.format_note}` : "";
  return `${h} • ${ext}${note}`;
}

function badges(f){
  const b = [];
  if (f.vcodec && f.vcodec !== "none") b.push(`v: ${f.vcodec}`);
  if (f.acodec && f.acodec !== "none") b.push(`a: ${f.acodec}`);
  if (f.fps) b.push(`${f.fps} fps`);
  if (f.tbr) b.push(`${Math.round(f.tbr)} kbps`);
  if (f.filesize) b.push(fmtBytes(f.filesize));
  return b;
}

function setStatus(msg, isError=false){
  const el = $("status");
  el.classList.remove("hidden");
  el.textContent = msg;
  el.style.borderColor = isError ? "rgba(255,90,90,.55)" : "rgba(255,255,255,.12)";
}

function clearAll(){
  $("result").classList.add("hidden");
  $("formats").innerHTML = "";
  $("title").textContent = "";
  $("thumb").classList.add("hidden");
  $("src").href = "#";
  $("status").classList.add("hidden");
}

$("clear").addEventListener("click", clearAll);

$("btn").addEventListener("click", async () => {
  const url = $("url").value.trim();
  if(!url){ setStatus("Please paste a video URL.", true); return; }

  $("btn").disabled = true;
  setStatus("Fetching formats…");

  try{
    const res = await fetch("/api/formats", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({url})
    });

    const data = await res.json().catch(() => null);
    if(!data || !data.ok){
      const msg = (data && data.error) ? data.error : `Request failed (${res.status}).`;
      setStatus(msg, true);
      $("btn").disabled = false;
      return;
    }

    $("result").classList.remove("hidden");
    $("title").textContent = data.title || "";
    if (data.thumbnail){
      $("thumb").src = data.thumbnail;
      $("thumb").classList.remove("hidden");
    }
    $("src").href = data.webpage_url || url;

    const list = $("formats");
    list.innerHTML = "";

    if(!data.formats || data.formats.length === 0){
      setStatus("No formats returned. This usually means the extractor failed for this link.", true);
      $("btn").disabled = false;
      return;
    }

    data.formats.forEach((f) => {
      const div = document.createElement("div");
      div.className = "item";

      const left = document.createElement("div");
      left.className = "left";

      const main = document.createElement("div");
      main.style.fontWeight = "700";
      main.textContent = formatLabel(f);

      const bd = document.createElement("div");
      bd.className = "badges";
      badges(f).forEach(x => {
        const s = document.createElement("span");
        s.className = "badge";
        s.textContent = x;
        bd.appendChild(s);
      });

      left.appendChild(main);
      left.appendChild(bd);

      const right = document.createElement("div");
      right.className = "right";

      const a = document.createElement("a");
      a.className = "btn";
      a.style.textDecoration = "none";
      a.textContent = "Download";
      a.href = `/api/download?url=${encodeURIComponent(url)}&format_id=${encodeURIComponent(f.format_id)}`;

      right.appendChild(a);

      div.appendChild(left);
      div.appendChild(right);
      list.appendChild(div);
    });

    setStatus(`Found ${data.formats.length} formats.`);
  } catch(e){
    setStatus(String(e), true);
  } finally{
    $("btn").disabled = false;
  }
});
