"""
12306 Session Keep-Alive & Auto-Cancel Guard Daemon
1. Maintains 12306 login session active in the background.
2. Monitors uncompleted orders and checks at the 19-minute mark (remaining ~60s).
   If the order is still unpaid, cancels it proactively to prevent 12306 official session termination.
"""
import time
import sys
import os
import datetime

sys.path.append('/opt/data/12306')
from client import Client12306

CST_TZ = datetime.timezone(datetime.timedelta(hours=8))

def parse_time_str(t_str: str) -> float:
    """Parse format '2026-09-20 20:48:16' (Beijing Time CST UTC+8) to timestamp."""
    try:
        dt = datetime.datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=CST_TZ)
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
                # Ping endpoints for session activity
                c._request('https://kyfw.12306.cn/otn/login/conf', method='POST', data={'_json_att': ''})
                c._request('https://kyfw.12306.cn/passport/web/auth/uamtk', method='POST', data={'appid': 'otn'})

                # 2. Check uncompleted orders to auto-cancel at 19-minute mark
                res_order = c.query_no_complete_order()
                if isinstance(res_order, dict):
                    orders = res_order.get('data', {}).get('orderDBList', [])
                    now_ts = time.time()
                    for order in orders:
                        seq_no = order.get('sequence_no')
                        tickets = order.get('tickets', [])
                        if not tickets:
                            continue
                        
                        # Check ticket status: 'i' means 待支付 (unpaid)
                        status_code = tickets[0].get('ticket_status_code', '')
                        pay_limit_str = tickets[0].get('pay_limit_time', '')
                        limit_ts = parse_time_str(pay_limit_str)
                        if limit_ts > 0:
                            remaining_secs = limit_ts - now_ts
                            # 12306 total window is 20m (1200s).
                            # At 19 minutes elapsed, remaining_secs is around 60s.
                            # If order is still unpaid and remaining <= 65s, cancel it!
                            if status_code == 'i' and 0 < remaining_secs <= 65:
                                print(f"[{time.strftime('%X')}] Order {seq_no} reached 19-minute mark (unpaid, remaining {remaining_secs:.1f}s). Cancelling proactively...", flush=True)
                                cancel_res = c.cancel_no_complete_order(seq_no)
                                print(f"[{time.strftime('%X')}] Proactive cancel result: {cancel_res}", flush=True)
                                c._save_cookies()
        except Exception as e:
            pass
        
        # Check every 15 seconds
        time.sleep(15)

if __name__ == '__main__':
    run_daemon()
