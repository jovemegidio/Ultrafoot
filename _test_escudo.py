"""Test: can pywebview load file:// URLs for images?"""
import webview, os, json, base64

BASE = os.path.dirname(os.path.abspath(__file__))
URL = "file:///" + BASE.replace(os.sep, "/")

HTML = """<!DOCTYPE html>
<html><body style="background:#222;color:#fff;font-family:monospace;padding:20px;">
<h2>Escudo Loading Test</h2>
<p id="info">Loading...</p>
<div style="display:flex;gap:30px;margin-top:20px;">
  <div>
    <p>1) file:// URL</p>
    <img id="t1" style="width:80px;height:80px;border:2px solid red;" alt="file">
  </div>
  <div>
    <p>2) data: base64</p>
    <img id="t2" style="width:80px;height:80px;border:2px solid blue;" alt="b64">
  </div>
  <div>
    <p>3) relative path</p>
    <img id="t3" style="width:80px;height:80px;border:2px solid green;" alt="rel">
  </div>
</div>
<script>
window.addEventListener('pywebviewready', async () => {
    const info = document.getElementById('info');
    const base = await window.pywebview.api.get_base();
    info.textContent = 'Base: ' + base;

    // Test 1: file:// URL
    const img1 = document.getElementById('t1');
    const fileUrl = base + '/teams/escudos/corinthians_bra.png';
    img1.src = fileUrl;
    img1.onload = () => { info.textContent += ' | FILE:OK'; };
    img1.onerror = () => { info.textContent += ' | FILE:FAIL(' + fileUrl + ')'; };

    // Test 2: base64
    const b64 = await window.pywebview.api.get_b64();
    if (b64) {
        document.getElementById('t2').src = b64;
        info.textContent += ' | B64:OK';
    } else {
        info.textContent += ' | B64:NULL';
    }

    // Test 3: relative path
    const img3 = document.getElementById('t3');
    img3.src = 'teams/escudos/corinthians_bra.png';
    img3.onload = () => { info.textContent += ' | REL:OK'; };
    img3.onerror = () => { info.textContent += ' | REL:FAIL'; };
});
</script>
</body></html>"""


class TestAPI:
    def get_base(self):
        return URL

    def get_b64(self):
        path = os.path.join(BASE, "teams", "escudos", "corinthians_bra.png")
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()


w = webview.create_window("Escudo Test", html=HTML, js_api=TestAPI(), width=700, height=350)
webview.start()
