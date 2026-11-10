"""
api/products.py
GET    /api/products          → 返回全部活跃商品列表
POST   /api/products  body={} → 新增商品（自动获取京东价格）
DELETE /api/products?id=123   → 软删除
"""
import re
import json
import os
import requests as req
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

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


def sb(method, path, **kw):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = getattr(req, method)(url, headers=HDRS, timeout=10, **kw)
    return r.json() if r.content else []


def extract_sku(url):
    m = re.search(r"item\.jd\.com[/\\](\d+)", url or "")
    return m.group(1) if m else None


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


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        rows = sb("get", "products",
                  params={"is_active": "eq.true", "order": "added_at.desc"})
        self._json(200, rows if isinstance(rows, list) else [])

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        sku = extract_sku(body.get("jd_url", ""))
        price = jd_price(sku) if sku else None
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "name":          body.get("name", "未命名"),
            "jd_url":        body.get("jd_url") or None,
            "jd_sku":        sku,
            "store_type":    body.get("store_type", "自营"),
            "taobao_url":    body.get("taobao_url") or None,
            "pdd_url":       body.get("pdd_url") or None,
            "target_price":  body.get("target_price") or None,
            "notes":         body.get("notes") or None,
            "current_price": price,
            "last_checked":  now if price else None,
            "is_active":     True,
        }
        result = sb("post", "products", json=record)
        created = result[0] if isinstance(result, list) and result else result or {}

        # 记录价格历史
        if price and created.get("id"):
            sb("post", "price_history",
               json={"product_id": created["id"], "price": price})

        created["current_price"] = price
        self._json(200, created)

    def do_DELETE(self):
        qs  = parse_qs(urlparse(self.path).query)
        pid = qs.get("id", [None])[0]
        if not pid:
            self._json(400, {"error": "missing id"})
            return
        sb("patch", "products",
           json={"is_active": False},
           params={"id": f"eq.{pid}"})
        self._json(200, {"ok": True})

    def do_OPTIONS(self):
        self._json(200, {})

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
