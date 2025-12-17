function startDownload(){
    const url = document.getElementById("url").value;
    const quality = document.getElementById("quality").value;
    const format = document.getElementById("format").value;
    const status = document.getElementById("status");
    const progress = document.getElementById("progress");

    if(!url){
        status.innerText = "❌ Please enter a URL";
        return;
    }

    progress.style.width = "30%";
    status.innerText = "⏳ Processing...";

    fetch("/download",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({url, quality, format})
    })
    .then(res => res.json())
    .then(data => {
        if(data.error){
            status.innerText = "❌ "+data.error;
            progress.style.width = "0%";
        }else{
            progress.style.width = "100%";
            status.innerText = "✅ Download ready!";
            window.location = "/file?path="+encodeURIComponent(data.file);
        }
    })
    .catch(()=>{
        status.innerText = "❌ Server error";
        progress.style.width = "0%";
    });
}
