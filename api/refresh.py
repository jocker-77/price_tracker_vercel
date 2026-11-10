"""
api/refresh.py
POST /api/refresh
逐一检查所有活跃商品的京东价格，返回 {updated, alerts}
同时：若配置了邮件且有提醒事项，自动发送邮件
"""
import json
import os
import re
import ssl
import smtplib
import time
import requests as req
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone
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
JD_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.jd.com/",
}


def sb_get(path, params=None):
    r = req.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=HDRS, params=params, timeout=10)
    return r.json() if r.content else []


def sb_patch(path, data, params):
    r = req.patch(f"{SUPABASE_URL}/rest/v1/{path}", headers=HDRS, json=data, params=params, timeout=10)
    return r


def sb_post(path, data):
    r = req.post(f"{SUPABASE_URL}/rest/v1/{path}", headers=HDRS, json=data, timeout=10)
    return r


def jd_price(sku_id):
    api = f"https://p.3.cn/prices/mgets?skuIds=J_{sku_id}&type=1&area=1_72_2799_0"
    try:
        r = req.get(api, headers=JD_UA, timeout=8)
        data = r.json()
        if data:
            p = data[0].get("p", "")
            return float(p) if p else None
    except Exception:
        pass
    return None


def get_setting(key):
    rows = sb_get("settings", params={"key": f"eq.{key}"})
    return rows[0]["value"] if isinstance(rows, list) and rows else ""


def send_alert_email(alerts):
    smtp_host  = get_setting("smtp_host")
    smtp_port  = get_setting("smtp_port") or "465"
    email_from = get_setting("email_from")
    email_pass = get_setting("email_pass")
    email_to   = get_setting("email_to")

    if not email_from or not email_to:
        return False

    rows = ""
    for a in alerts:
        if a["type"] == "target":
            rows += (f"<tr><td>{a['name']}</td>"
                     f"<td style='color:#15803d'>达目标价</td>"
                     f"<td style='color:#e1251b;font-weight:bold'>¥{a['price']:.2f}</td>"
                     f"<td>目标 ¥{a['target']:.2f}</td></tr>")
        else:
            rows += (f"<tr><td>{a['name']}</td>"
                     f"<td style='color:#e1251b'>降价 {a['pct']:.1f}%</td>"
                     f"<td style='color:#e1251b;font-weight:bold'>¥{a['price']:.2f}</td>"
                     f"<td>原价 ¥{a['old']:.2f}</td></tr>")

    html = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto">
    <h2 style="color:#1a73e8">🔔 商品价格提醒</h2>
    <table border="1" cellpadding="8" cellspacing="0"
           style="border-collapse:collapse;width:100%">
      <tr style="background:#f3f4f6">
        <th>商品</th><th>状态</th><th>当前价格</th><th>参考</th>
      </tr>{rows}
    </table>
    <p style="color:#9ca3af;font-size:12px;margin-top:16px">来自「商品价格追踪器」</p>
    </body></html>
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔔 价格提醒：{len(alerts)} 个商品值得关注"
    msg["From"]    = email_from
    msg["To"]      = email_to
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        port = int(smtp_port)
        if port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, port, context=ctx) as s:
                s.login(email_from, email_pass)
                s.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, port) as s:
                s.starttls()
                s.login(email_from, email_pass)
                s.send_message(msg)
        return True
    except Exception:
        return False


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        products = sb_get("products",
                          params={"is_active": "eq.true",
                                  "jd_sku":    "not.is.null"})
        if not isinstance(products, list):
            products = []

        alerts, updated = [], 0

        for p in products:
            pid       = p["id"]
            name      = p["name"]
            sku       = p["jd_sku"]
            old_price = p.get("current_price")
            target    = p.get("target_price")

            new_price = jd_price(sku)
            if new_price is None:
                continue

            now = datetime.now(timezone.utc).isoformat()
            sb_patch("products",
                     {"current_price": new_price, "last_checked": now},
                     params={"id": f"eq.{pid}"})
            sb_post("price_history",
                    {"product_id": pid, "price": new_price})
            updated += 1

            if target and new_price <= float(target):
                alerts.append({"name": name, "price": new_price,
                               "target": float(target), "type": "target"})
            elif old_price and new_price < float(old_price) * 0.95:
                pct = (float(old_price) - new_price) / float(old_price) * 100
                alerts.append({"name": name, "price": new_price,
                               "old": float(old_price), "pct": pct, "type": "drop"})
            time.sleep(0.3)

        email_sent = False
        if alerts:
            email_sent = send_alert_email(alerts)

        result = {"updated": updated, "alerts": alerts, "email_sent": email_sent}
        body = json.dumps(result, ensure_ascii=False, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *args):
        pass
