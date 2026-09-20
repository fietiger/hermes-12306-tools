"""
12306 Session Keep-Alive Daemon
Maintains 12306 login session active in the background.
"""
import time
import sys
import os

sys.path.append('/opt/data/12306')
from client import Client12306

def run_heartbeat():
    c = Client12306()
    while True:
        try:
            # Check user login status
            res = c.check_user()
            flag = res.get('data', {}).get('flag', False) if isinstance(res, dict) else False
            if flag:
                # Active! Ping user login conf
                c._request('https://kyfw.12306.cn/otn/login/conf', method='POST', data={'_json_att': ''})
                # Attempt to refresh token if needed
                c._request('https://kyfw.12306.cn/passport/web/auth/uamtk', method='POST', data={'appid': 'otn'})
        except Exception:
            pass
        # Sleep 90 seconds between pings
        time.sleep(90)

if __name__ == '__main__':
    run_heartbeat()
