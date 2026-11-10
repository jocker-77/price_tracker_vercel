"""
api/history.py
GET /api/history?product_id=123
返回某商品的价格历史记录（用于走势图）
"""
import json
import os
import requests as req
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

HDRS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        qs  = parse_qs(urlparse(self.path).query)
        pid = qs.get("product_id", [None])[0]
        if not pid:
            self._json(400, {"error": "missing product_id"})
            return

        r = req.get(
            f"{SUPABASE_URL}/rest/v1/price_history",
            headers=HDRS,
            params={"product_id": f"eq.{pid}", "order": "checked_at.asc"},
            timeout=10,
        )
        rows = r.json() if r.content else []
        self._json(200, rows if isinstance(rows, list) else [])

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
