"""
api/settings.py
GET  /api/settings          → 返回当前邮件配置
POST /api/settings body={…} → 保存配置（若含 _action:test 则发测试邮件）
"""
import json
import os
import ssl
import smtplib
import requests as req
from http.server import BaseHTTPRequestHandler
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

HDRS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

KEYS = ["smtp_host", "smtp_port", "email_from", "email_pass", "email_to"]


def get_all():
    r = req.get(f"{SUPABASE_URL}/rest/v1/settings",
                headers=HDRS, params={"key": f"in.({','.join(KEYS)})"}, timeout=10)
    rows = r.json() if r.content else []
    return {row["key"]: row["value"] for row in rows} if isinstance(rows, list) else {}


def upsert(key, value):
    req.post(f"{SUPABASE_URL}/rest/v1/settings",
             headers={**HDRS, "Prefer": "resolution=merge-duplicates,return=representation"},
             json={"key": key, "value": value}, timeout=10)


def send_test(cfg):
    host = cfg.get("smtp_host", "")
    port = int(cfg.get("smtp_port") or 465)
    frm  = cfg.get("email_from", "")
    pw   = cfg.get("email_pass", "")
    to   = cfg.get("email_to", "")
    if not frm or not to:
        return False, "未填写发件或收件邮箱"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "✅ 商品价格追踪器 — 邮件配置测试"
    msg["From"]    = frm
    msg["To"]      = to
    msg.attach(MIMEText(
        "<html><body><h2>✅ 邮件配置成功！</h2>"
        "<p>商品降价时你将收到这样的提醒邮件。</p></body></html>",
        "html", "utf-8"
    ))
    try:
        if port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=ctx) as s:
                s.login(frm, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as s:
                s.starttls()
                s.login(frm, pw)
                s.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        cfg = get_all()
        # 不返回密码明文（前端只是判断是否配置了）
        safe = {k: v for k, v in cfg.items()}
        safe["email_pass"] = "***" if cfg.get("email_pass") else ""
        self._json(200, safe)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

        action = body.pop("_action", None)

        # 保存配置
        for k in KEYS:
            if k in body:
                # 如果密码字段传来的是掩码，不覆盖
                if k == "email_pass" and body[k] == "***":
                    continue
                upsert(k, body[k])

        if action == "test":
            cfg = get_all()
            # 若前端传来了明文密码，用前端的（刚才已 upsert）
            ok, err = send_test(cfg)
            self._json(200, {"sent": ok, "error": err})
        else:
            self._json(200, {"ok": True})

    def do_OPTIONS(self):
        self._json(200, {})

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
