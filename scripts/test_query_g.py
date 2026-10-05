import ssl
import urllib.request
import json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://kyfw.12306.cn/otn/leftTicket/queryG?leftTicketDTO.train_date=2026-09-25&leftTicketDTO.from_station=SZQ&leftTicketDTO.to_station=CSQ&purpose_codes=ADULT"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init',
    'Cookie': '_jc_save_fromStation=%u6DF1%u5733%2CSZQ; _jc_save_toStation=%u957F%u6C92%2CCSQ; _jc_save_fromDate=2026-09-25; _jc_save_toDate=2026-09-25; _jc_save_wfdc_flag=dc'
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        print("Status code:", resp.status)
        data = resp.read().decode('utf-8')
        print("Body preview:", data[:300])
        res = json.loads(data)
        print("Count results:", len(res.get('data', {}).get('result', [])))
        if res.get('data', {}).get('result'):
            print("First train raw:", res['data']['result'][0].split('|')[:12])
except Exception as e:
    print("Error:", e)
