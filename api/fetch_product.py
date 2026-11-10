"""
api/fetch_product.py
GET /api/fetch_product?url=<京东商品链接>
返回: {name, price, sku_id} 或 {error}
"""
import re
import json
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

JD_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.jd.com/",
}


def extract_sku(url: str):
    m = re.search(r"item\.jd\.com[/\\](\d+)", url)
    return m.group(1) if m else None


def fetch_price(sku_id: str):
    api = f"https://p.3.cn/prices/mgets?skuIds=J_{sku_id}&type=1&area=1_72_2799_0"
    try:
        r = requests.get(api, headers=JD_UA, timeout=8)
        data = r.json()
        if data:
            p = data[0].get("p", "")
            return float(p) if p else None
    except Exception:
        pass
    return None


def fetch_name(sku_id: str) -> str:
    url = f"https://item.jd.com/{sku_id}.html"
    try:
        r = requests.get(url, headers=JD_UA, timeout=12)
        r.encoding = "utf-8"
        m = re.search(r"<title>(.*?)</title>", r.text, re.I)
        if m:
            t = re.sub(r"【京东】|_?-?京东$|商品详情", "", m.group(1)).strip()
            return t[:60]
    except Exception:
        pass
    return f"京东商品 {sku_id}"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        url = qs.get("url", [""])[0]
        sku = extract_sku(url)
        if not sku:
            body = json.dumps({"error": "无法解析京东商品链接，请复制完整链接"}).encode()
        else:
            name  = fetch_name(sku)
            price = fetch_price(sku)
            body  = json.dumps({"name": name, "price": price, "sku_id": sku},
                               ensure_ascii=False).encode()
        self._respond(200, body)

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
