const urlEl = document.getElementById("url");
const btn = document.getElementById("btnFetch");
const btnText = btn.querySelector(".btnText");
const spinner = btn.querySelector(".spinner");

const alertBox = document.getElementById("alert");

const meta = document.getElementById("meta");
const thumb = document.getElementById("thumb");
const titleEl = document.getElementById("title");
const openLink = document.getElementById("openLink");

const results = document.getElementById("results");
const list = document.getElementById("list");
const tabs = Array.from(document.querySelectorAll(".tab"));

let lastData = null;
let activeTab = "progressive";

function showAlert(msg, type = "error"){
  alertBox.textContent = msg;
  alertBox.classList.remove("hidden");
  alertBox.classList.toggle("error", type === "error");
}

function hideAlert(){
  alertBox.classList.add("hidden");
  alertBox.textContent = "";
  alertBox.classList.remove("error");
}

function setLoading(on){
  btn.disabled = on;
  spinner.classList.toggle("hidden", !on);
  btnText.textContent = on ? "Loading..." : "Get formats";
}

function fmtSize(mb){
  if (mb === null || mb === undefined) return "";
  return `${mb} MB`;
}

function buildList(groupKey){
  list.innerHTML = "";

  const items = (lastData?.groups?.[groupKey] || []);
  if (!items.length){
    const div = document.createElement("div");
    div.className = "alert";
    div.textContent = "No formats found in this category.";
    list.appendChild(div);
    return;
  }

  for (const f of items){
    const item = document.createElement("div");
    item.className = "item";

    const left = document.createElement("div");
    left.className = "left";

    const label = document.createElement("div");
    label.className = "label";
    label.textContent = f.display || f.format_id;

    const small = document.createElement("div");
    small.className = "small";
    const sizeTxt = fmtSize(f.filesize_mb);
    small.textContent = [f.format_id ? `ID: ${f.format_id}` : "", sizeTxt].filter(Boolean).join(" • ");

    left.appendChild(label);
    left.appendChild(small);

    const a = document.createElement("a");
    a.className = "dl";
    a.textContent = "Download";
    const qUrl = encodeURIComponent(lastData.webpage_url || "");
    const qFmt = encodeURIComponent(f.format_id || "");
    a.href = `/download?url=${qUrl}&format_id=${qFmt}&kind=${encodeURIComponent(groupKey)}`;

    item.appendChild(left);
    item.appendChild(a);
    list.appendChild(item);
  }
}

tabs.forEach(t => {
  t.addEventListener("click", () => {
    tabs.forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    activeTab = t.dataset.tab;
    if (lastData) buildList(activeTab);
  });
});

btn.addEventListener("click", async () => {
  hideAlert();
  meta.classList.add("hidden");
  results.classList.add("hidden");
  list.innerHTML = "";
  lastData = null;

  const url = urlEl.value.trim();
  if (!url){
    showAlert("Please paste a video URL.");
    return;
  }

  setLoading(true);
  try{
    const res = await fetch("/api/formats", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({url})
    });
    const data = await res.json();

    if (!data.ok){
      showAlert(data.error || "Failed to get formats.");
      return;
    }

    lastData = data;

    // Meta
    titleEl.textContent = data.title || "Video";
    openLink.href = data.webpage_url || url;
    if (data.thumbnail){
      thumb.src = data.thumbnail;
      thumb.classList.remove("hidden");
    } else {
      thumb.classList.add("hidden");
    }
    meta.classList.remove("hidden");

    // Results
    results.classList.remove("hidden");
    buildList(activeTab);

  }catch(e){
    showAlert("Network error. Please try again.");
  }finally{
    setLoading(false);
  }
});
