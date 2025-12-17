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

    // Validate CAPTCHA if visible
    const captchaResponse = grecaptcha.getResponse();
    if(document.getElementById("captcha-box").style.display === "block" && !captchaResponse){
        status.innerText = "❌ Please verify that you are not a robot";
        return;
    }

    progress.style.width = "30%";
    status.innerText = "⏳ Processing...";

    fetch("/download",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({
            url: url,
            quality: quality,
            format: format,
            captcha: captchaResponse || ""
        })
    })
    .then(res => res.json())
    .then(data => {
        if(data.error){
            status.innerText = "❌ "+data.error;
            progress.style.width = "0%";

            // Show CAPTCHA for restricted videos
            if(data.error.includes("restricted") || data.error.includes("login required")){
                document.getElementById("captcha-box").style.display = "block";
            }
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
