const $ = (id) => document.getElementById(id);

function setMsg(text, kind="info") {
  const el = $("msg");
  el.className = "msg " + kind;
  el.textContent = text || "";
}

function getRecaptchaToken() {
  if (!window.APP_ENABLE_RECAPTCHA) return "";
  if (typeof grecaptcha === "undefined") return "";
  // For v2 checkbox, token is in hidden textarea named g-recaptcha-response
  const t = document.querySelector("textarea[name='g-recaptcha-response']");
  return (t && t.value) ? t.value.trim() : "";
}

function resetRecaptcha() {
  if (!window.APP_ENABLE_RECAPTCHA) return;
  if (typeof grecaptcha === "undefined") return;
  try { grecaptcha.reset(); } catch (e) {}
}

function hideResult() {
  $("result").classList.add("hidden");
  $("formats").innerHTML = "";
}

function showResult(title, thumb, formats) {
  $("title").textContent = title || "";
  const img = $("thumb");
  if (thumb) {
    img.src = thumb;
    img.style.display = "block";
  } else {
    img.style.display = "none";
  }

  const wrap = $("formats");
  wrap.innerHTML = "";

  formats.forEach(f => {
    const btn = document.createElement("button");
    btn.className = "fmt";
    btn.innerHTML = `<div class="lbl">${f.label}</div>
                     <div class="sub">${f.format_id}</div>`;
    btn.onclick = () => startDownload(f.format_id);
    wrap.appendChild(btn);
  });

  $("result").classList.remove("hidden");
}

async function fetchInfo() {
  hideResult();
  setMsg("");

  const url = $("url").value.trim();
  if (!url) return setMsg("Please paste a video URL.", "err");

  const recaptcha = getRecaptchaToken();
  if (window.APP_ENABLE_RECAPTCHA && !recaptcha) {
    return setMsg("Verification expired. Check the checkbox again.", "err");
  }

  $("btnInfo").disabled = true;
  setMsg("Fetching formats...", "info");

  try {
    const r = await fetch("/api/info", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ url, recaptcha })
    });
    const data = await r.json();

    if (!data.ok) {
      setMsg(data.error || "Failed.", "err");
      // if server says token is expired, force user to re-check
      resetRecaptcha();
      return;
    }

    setMsg("Formats loaded. Choose one below.", "ok");
    showResult(data.title, data.thumbnail, data.formats);
    // reset checkbox after successful action so next request gets a fresh token
    resetRecaptcha();

  } catch (e) {
    setMsg("Network error. Try again.", "err");
    resetRecaptcha();
  } finally {
    $("btnInfo").disabled = false;
  }
}

function startDownload(format_id) {
  const url = $("url").value.trim();
  const recaptcha = getRecaptchaToken();

  if (window.APP_ENABLE_RECAPTCHA && !recaptcha) {
    return setMsg("Verification expired. Check the checkbox again, then click the format.", "err");
  }

  setMsg("Starting download...", "info");

  fetch("/api/download", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ url, format_id, recaptcha })
  }).then(async (res) => {
    if (!res.ok) {
      let j = null;
      try { j = await res.json(); } catch {}
      setMsg((j && j.error) ? j.error : "Download failed.", "err");
      resetRecaptcha();
      return;
    }

    // Stream file
    const blob = await res.blob();
    const a = document.createElement("a");
    const dlUrl = window.URL.createObjectURL(blob);
    a.href = dlUrl;

    // try get filename from headers
    const cd = res.headers.get("Content-Disposition") || "";
    const m = cd.match(/filename="(.+?)"/);
    a.download = m ? m[1] : "video";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(dlUrl);

    setMsg("Download started.", "ok");
    resetRecaptcha();
  }).catch(() => {
    setMsg("Network error. Try again.", "err");
    resetRecaptcha();
  });
}

$("btnInfo").addEventListener("click", fetchInfo);
