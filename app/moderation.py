import json
from html import escape
from pathlib import Path

from aiohttp import web

from app.storage import UserStorage


API_KEYS = [
    "localhost",
    "96D0C1491615C82B9A54D9989779DF825B690748224C2B04F500F370D51827CE2644D8D4A82C18184D73AB8530BB8ED537269603F61DB0D03D2104ABF789970B",
    "127.0.0.1",
    "A7BCFA5D490B351BE0754130DF03A068F855DB4333D43921125B9CF2670EF6A40370C646B90401955E1F7BC9CDBF59CE0B2C5467D820BE189C845D0B79CFC96F",
]


class ModerationServer:
    def __init__(self, storage: UserStorage, host: str, port: int) -> None:
        self.storage = storage
        self.host = host
        self.port = port
        self.runner: web.AppRunner | None = None

    def create_draft(self, telegram_id: int, tnved: str, gtin: str) -> str:
        payload = {"operation": "PRODUCT_MODERATION", "tnved": tnved, "gtin": gtin}
        token = self.storage.create_moderation_draft(telegram_id, payload)
        return f"http://{self.host}:{self.port}/sign/{token}"

    async def start(self) -> None:
        app = web.Application(client_max_size=5 * 1024 * 1024)
        app.router.add_get("/e-imzo.js", self.eimzo_js)
        app.router.add_get("/sign/{token}", self.sign_page)
        app.router.add_post("/sign/{token}", self.receive_signature)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        await web.TCPSite(self.runner, self.host, self.port).start()

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    async def eimzo_js(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(Path(__file__).with_name("e-imzo.js"))

    async def sign_page(self, request: web.Request) -> web.Response:
        token = request.match_info["token"]
        draft = self.storage.get_moderation_draft(token)
        if not draft:
            return web.Response(text="Havola yaroqsiz yoki muddati tugagan.", status=404)
        payload_text = json.dumps(draft["payload"], ensure_ascii=False, sort_keys=True)
        html = (
            SIGN_PAGE.replace("__TOKEN__", escape(token))
            .replace("__PAYLOAD_DISPLAY__", escape(payload_text))
            .replace("__PAYLOAD_JSON__", json.dumps(payload_text))
            .replace("__API_KEYS__", json.dumps(API_KEYS))
        )
        return web.Response(text=html, content_type="text/html")

    async def receive_signature(self, request: web.Request) -> web.Response:
        token = request.match_info["token"]
        body = await request.json()
        signature = body.get("pkcs7")
        if not isinstance(signature, str) or len(signature) < 100:
            raise web.HTTPBadRequest(text="PKCS#7 imzo noto'g'ri.")
        if not self.storage.sign_moderation_draft(token, signature):
            raise web.HTTPConflict(text="Draft topilmadi yoki avval imzolangan.")
        return web.json_response(
            {
                "ok": True,
                "message": (
                    "ERI imzo olindi. Draft imzolangan va yuborishga tayyor. "
                    "xTrace kartochka yaratish API endpointi berilgach avtomatik yuboriladi."
                ),
            }
        )


SIGN_PAGE = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8"><title>Moderatsiya ERI tasdiqlash</title>
<script src="/e-imzo.js"></script>
<style>body{font-family:Arial;max-width:760px;margin:40px auto;padding:20px}button,select{padding:12px;margin:8px 0;width:100%}pre{white-space:pre-wrap;background:#f5f5f5;padding:14px}.ok{color:green}.err{color:#b00020}</style>
</head><body>
<h2>Moderatsiya draftini ERI bilan tasdiqlash</h2>
<pre id="payload">__PAYLOAD_DISPLAY__</pre>
<button onclick="loadKeys()">ERI kalitlarini yuklash</button>
<select id="keys"><option>Avval kalitlarni yuklang</option></select>
<button onclick="sign()">ERI bilan imzolash</button>
<div id="status"></div>
<script>
const token="__TOKEN__", payload=__PAYLOAD_JSON__, apiKeys=__API_KEYS__;
const status=(t,c="")=>{document.getElementById("status").className=c;document.getElementById("status").textContent=t};
const call=(plugin,name,args)=>new Promise((ok,fail)=>CAPIWS.callFunction({plugin:plugin,name:name,arguments:args},(e,d)=>d.success?ok(d):fail(d.reason||"E-IMZO xatosi"),fail));
function loadKeys(){status("E-IMZO ulanmoqda...");CAPIWS.apikey(apiKeys,async(e,d)=>{try{if(!d.success)throw d.reason;const r=await call("pfx","list_all_certificates",[]);const s=document.getElementById("keys");s.innerHTML="";(r.certificates||[]).forEach((x,i)=>{const o=document.createElement("option");o.value=i;o.textContent=(x.alias||x.name||"ERI kalit");o.dataset.cert=JSON.stringify(x);s.appendChild(o)});status("Kalitni tanlang.","ok")}catch(x){status(String(x),"err")}},x=>status(String(x),"err"))}
async function sign(){try{const o=document.getElementById("keys").selectedOptions[0];if(!o||!o.dataset.cert)throw "ERI kalit tanlanmagan";const c=JSON.parse(o.dataset.cert);const k=await call("pfx","load_key",[c.disk,c.path,c.name,c.alias]);const data64=Base64.encode(payload);const signed=await call("pkcs7","create_pkcs7",[data64,k.id,"no"]);const r=await fetch("/sign/"+token,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({pkcs7:signed.pkcs7_64})});const j=await r.json();if(!r.ok)throw j.message||"Yuborish xatosi";status(j.message,"ok")}catch(x){status(String(x),"err")}}
</script></body></html>"""
