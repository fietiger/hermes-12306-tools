import json
import os
import ssl
import sys
import urllib.parse
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://kyfw.12306.cn/otn/resources/login.html',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
}

def test_qr():
    data = urllib.parse.urlencode({'appid': 'otn'}).encode('utf-8')
    req = urllib.request.Request('https://kyfw.12306.cn/passport/web/create-qr64', data=data, headers=HEADERS)
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print("QR test result:", res.get("result_code"), "UUID length:", len(res.get("uuid", "")))
        return res

if __name__ == '__main__':
    test_qr()
