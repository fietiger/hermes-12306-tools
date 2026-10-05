import sys
import time
import json
import os

sys.path.append('/opt/data/plugins/tools/12306_tools')
from client import Client12306

def main():
    c = Client12306()
    qr_data = c.create_qr()
    if not qr_data or qr_data.get("result_code") != "0":
        print(json.dumps({"success": False, "error": "无法生成二维码"}))
        return
    
    uuid = qr_data.get("uuid")
    image_b64 = qr_data.get("image")
    qr_path = f"/opt/data/cache/images/12306_login_qr_{int(time.time())}.jpg"
    c.save_qr_image(image_b64, qr_path)
    
    print(f"QR_GENERATED:{qr_path}:{uuid}", flush=True)
    
    # Do NOT poll for the first 10 seconds! Let user scan in peace.
    time.sleep(10.0)
    
    confirmed = False
    for i in range(15):
        time.sleep(1.5)
        res = c.check_qr(uuid)
        code = res.get("result_code")
        print(f"checkqr {i}: {code}", flush=True)
        if code == "2":
            uamtk = res.get("uamtk")
            ok, msg = c.complete_login(uamtk)
            if ok:
                confirmed = True
                print("LOGIN_SUCCESS", flush=True)
                break
        elif code == "3":
            print("QR_EXPIRED", flush=True)
            break
            
    if not confirmed:
        print("LOGIN_FAILED", flush=True)
        return

    # Once logged in, book the configured train. Identity/trip values are
    # intentionally left blank -- this repo is public, never commit real
    # passenger names or a real itinerary here.
    print("BOOKING_START", flush=True)
    TRAIN_CODE = os.environ.get('T12306_TRAIN_CODE', '')
    TRAIN_DATE = os.environ.get('T12306_TRAIN_DATE', '')
    FROM_STATION = os.environ.get('T12306_FROM', '')
    TO_STATION = os.environ.get('T12306_TO', '')
    PASSENGER = os.environ.get('T12306_PASSENGER', '')
    if not all([TRAIN_CODE, TRAIN_DATE, FROM_STATION, TO_STATION, PASSENGER]):
        print("BOOKING_SKIPPED: missing T12306_* env config", flush=True)
        return
    res_book = c.order_ticket(
        train_code=TRAIN_CODE,
        train_date=TRAIN_DATE,
        from_station=FROM_STATION,
        to_station=TO_STATION,
        seat_type='二等座',
        passenger_names=[PASSENGER]
    )
    print("BOOKING_RESULT:" + json.dumps(res_book, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
