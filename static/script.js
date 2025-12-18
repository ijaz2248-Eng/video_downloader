(() => {
  const $ = (id) => document.getElementById(id);

  const videoUrl = $("videoUrl");
  const btnFormats = $("btnFormats");
  const btnClear = $("btnClear");
  const toast = $("toast");

  const resultsSection = $("resultsSection");
  const formatsGrid = $("formatsGrid");
  const videoTitle = $("videoTitle");
  const videoInfo = $("videoInfo");

  const tabs = Array.from(document.querySelectorAll(".tab"));

  const FORMATS_ENDPOINT = "/api/formats";
  const DOWNLOAD_ENDPOINT = "/download"; // <-- change if your route is different

  let lastPayload = null;
  let currentTab = "all";

  function showToast(message, type = "ok") {
    toast.textContent = message;
    toast.className = `toast show ${type === "err" ? "err" : "ok"}`;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => {
      toast.className = "toast";
      toast.style.display = "none";
    }, 3500);
    toast.style.display = "block";
  }

  function setLoading(isLoading) {
    btnFormats.disabled = isLoading;
    btnFormats.querySelector(".spinner").style.display = isLoading ? "inline-block" : "none";
    btnFormats.querySelector(".btn-text").textContent = isLoading ? "Loading..." : "Get formats";
  }

  function isAudioOnly(f) {
    // yt-dlp: vcodec == "none" => audio-only
    return f && f.vcodec === "none" && f.acodec && f.acodec !== "none";
  }

  function isVideoFormat(f) {
    // includes video-only OR video+audio
    return f && f.vcodec && f.vcodec !== "none";
  }

  function fmtBytes(n) {
    if (!n || isNaN(n)) return "";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0, x = n;
    while (x >= 1024 && i < units.length - 1) { x /= 1024; i++; }
    return `${x.toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
  }

  function formatLabel(f) {
    const ext = f.ext ? f.ext.toUpperCase() : "FILE";
    const h = f.height ? `${f.height}p` : "";
    const fps = f.fps ? `${f.fps}fps` : "";
    const abr = f.abr ? `${Math.round(f.abr)}kbps` : "";
    const note = f.format_note || "";
    const size = fmtBytes(f.filesize || f.filesize_approx);

    const left = [ext, h, fps].filter(Boolean).join(" • ");
    const right = [note, abr, size].filter(Boolean).join(" • ");
    return { left, right };
  }

  function buildDownloadLink(url, formatId) {
    const u = new URL(DOWNLOAD_ENDPOINT, window.location.origin);
    u.searchParams.set("url", url);
    u.searchParams.set("format_id", formatId);
    return u.toString();
  }

  function renderFormats(payload) {
    const url = payload._inputUrl || videoUrl.value.trim();
    const title = payload.title || "Formats";
    const extractor = payload.extractor_key || payload.extractor || payload.webpage_url_domain || "";

    const formats = Array.isArray(payload.formats) ? payload.formats : [];
    if (!formats.length) {
      formatsGrid.innerHTML = "";
      resultsSection.classList.remove("hidden");
      videoTitle.textContent = "No formats found";
      videoInfo.textContent = "Try another public link, or the platform may be blocking requests from hosting servers.";
      showToast("No formats returned by server.", "err");
      return;
    }

    // filter out weird/incomplete entries
    const clean = formats
      .filter(f => f && f.format_id && f.ext)
      .filter(f => (f.filesize || f.filesize_approx || f.tbr || f.abr || f.height));

    // sort by quality (height then bitrate)
    clean.sort((a, b) => {
      const ah = a.height || 0, bh = b.height || 0;
      if (bh !== ah) return bh - ah;
      const at = a.tbr || a.abr || 0, bt = b.tbr || b.abr || 0;
      return bt - at;
    });

    lastPayload = { ...payload, formats: clean, _inputUrl: url };

    resultsSection.classList.remove("hidden");
    videoTitle.textContent = title;
    videoInfo.textContent = extractor ? `Source: ${extractor}` : "";

    applyTabFilter();
    showToast("Formats loaded ✅", "ok");
  }

  function applyTabFilter() {
    if (!lastPayload) return;
    formatsGrid.innerHTML = "";

    const url = lastPayload._inputUrl;
    const formats = lastPayload.formats || [];

    const filtered = formats.filter(f => {
      if (currentTab === "audio") return isAudioOnly(f);
      if (currentTab === "video") return isVideoFormat(f);
      return true;
    });

    if (!filtered.length) {
      formatsGrid.innerHTML = `<div class="muted small">No formats in this category.</div>`;
      return;
    }

    const frag = document.createDocumentFragment();

    filtered.forEach((f) => {
      const { left, right } = formatLabel(f);

      const card = document.createElement("div");
      card.className = "item";

      const typePill = isAudioOnly(f) ? "Audio" : (f.acodec && f.acodec !== "none" ? "Video+Audio" : "Video only");

      const v = f.vcodec && f.vcodec !== "none" ? f.vcodec : "";
      const a = f.acodec && f.acodec !== "none" ? f.acodec : "";

      card.innerHTML = `
        <div class="top">
          <span class="pill">${typePill}</span>
          <span class="pill">${left || "Format"}</span>
        </div>
        <h3>${left || (f.format_note || f.ext || "Format")}</h3>
        <div class="meta">
          ${right ? `<div>${right}</div>` : ""}
          <div>${[v ? `V: ${v}` : "", a ? `A: ${a}` : ""].filter(Boolean).join(" • ")}</div>
          <div class="small">ID: ${f.format_id}</div>
        </div>
        <div class="actions">
          <a class="dl primary" href="${buildDownloadLink(url, f.format_id)}">Download</a>
        </div>
      `;

      frag.appendChild(card);
    });

    formatsGrid.appendChild(frag);
  }

  async function fetchFormats() {
    const url = videoUrl.value.trim();
    if (!url) return showToast("Paste a video URL first.", "err");

    setLoading(true);

    try {
      const res = await fetch(FORMATS_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });

      const ct = res.headers.get("content-type") || "";
      const data = ct.includes("application/json") ? await res.json() : { error: await res.text() };

      if (!res.ok) {
        throw new Error(data.error || `Request failed (${res.status})`);
      }

      // keep original url for download building
      data._inputUrl = url;

      renderFormats(data);
    } catch (e) {
      console.error(e);
      showToast(e.message || "Failed to get formats.", "err");
      resultsSection.classList.remove("hidden");
      videoTitle.textContent = "Error";
      videoInfo.textContent = e.message || "Could not fetch formats.";
      formatsGrid.innerHTML = "";
    } finally {
      setLoading(false);
    }
  }

  function clearAll() {
    lastPayload = null;
    formatsGrid.innerHTML = "";
    resultsSection.classList.add("hidden");
    videoTitle.textContent = "Formats";
    videoInfo.textContent = "";
    showToast("Cleared.", "ok");
  }

  // events
  btnFormats.addEventListener("click", fetchFormats);
  btnClear.addEventListener("click", clearAll);
  videoUrl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") fetchFormats();
  });

  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      tabs.forEach(x => x.classList.remove("active"));
      t.classList.add("active");
      currentTab = t.dataset.tab;
      applyTabFilter();
    });
  });
})();
