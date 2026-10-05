import ssl
import urllib.request
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    'https://kyfw.12306.cn/otn/leftTicket/init',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
)

with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
    html = resp.read().decode('utf-8', errors='ignore')
    print("HTML length:", len(html))
    match = re.findall(r'leftTicket/query[A-Za-z0-9_]*', html)
    print("Found query endpoints:", set(match))
    var_matches = re.findall(r'var CUrl = [^;]+;', html)
    print("CUrl matches:", var_matches)
