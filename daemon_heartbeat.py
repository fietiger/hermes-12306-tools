"""
12306 Session Keep-Alive & Auto-Cancel Guard Daemon
1. Maintains 12306 login session active in the background.
2. Monitors uncompleted orders and automatically cancels them at 19m30s to prevent official session termination.
"""
import time
import sys
import os
import datetime

sys.path.append('/opt/data/12306')
from client import Client12306

def parse_time_str(t_str: str) -> float:
    """Parse format '2026-09-20 20:48:16' to timestamp."""
    try:
        dt = datetime.datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
        return dt.timestamp()
    except Exception:
        return 0.0

def run_daemon():
    c = Client12306()
    while True:
        try:
            # 1. Heartbeat check
            res_user = c.check_user()
            flag = res_user.get('data', {}).get('flag', False) if isinstance(res_user, dict) else False
            if flag:
                # Ping endpoints
                c._request('https://kyfw.12306.cn/otn/login/conf', method='POST', data={'_json_att': ''})
                c._request('https://kyfw.12306.cn/passport/web/auth/uamtk', method='POST', data={'appid': 'otn'})

                # 2. Check uncompleted orders to auto-cancel before official 20m timeout
                res_order = c.query_no_complete_order()
                if isinstance(res_order, dict):
                    orders = res_order.get('data', {}).get('orderDBList', [])
                    now_ts = time.time()
                    for order in orders:
                        seq_no = order.get('sequence_no')
                        tickets = order.get('tickets', [])
                        if not tickets:
                            continue
                        # pay_limit_time: e.g. '2026-09-20 20:48:16'
                        pay_limit_str = tickets[0].get('pay_limit_time', '')
                        limit_ts = parse_time_str(pay_limit_str)
                        if limit_ts > 0:
                            remaining_secs = limit_ts - now_ts
                            # 12306 total window is ~20m (1200s).
                            # If remaining time is less than 30s (i.e. elapsed > 19m30s), cancel proactively!
                            if 0 < remaining_secs <= 35:
                                print(f"[{time.strftime('%X')}] Auto-cancelling unpaid order {seq_no} at 19m30s threshold (remaining {remaining_secs:.1f}s)...", flush=True)
                                cancel_res = c.cancel_no_complete_order(seq_no)
                                print(f"[{time.strftime('%X')}] Cancel result: {cancel_res}", flush=True)
        except Exception as e:
            pass
        
        # Check every 10 seconds for timely auto-cancel protection
        time.sleep(10)

if __name__ == '__main__':
    run_daemon()
