import os
import sys
import time
from client import Client12306

def main():
    client = Client12306()
    print("Checking login status...")
    user_status = client.check_user()
    print("checkUser response:", user_status)

    if isinstance(user_status, dict) and user_status.get('data', {}).get('flag') is True:
        print("Already logged in! Getting passengers...")
        passengers = client.get_passengers()
        print(f"Passengers found ({len(passengers)}):")
        for p in passengers:
            print(f"- {p.get('passenger_name')} ({p.get('passenger_id_type_name')}: {p.get('passenger_id_no')})")
        return

    print("\nNot logged in or session expired. Initiating QR login...")
    qr_res = client.create_qr()
    if not isinstance(qr_res, dict) or qr_res.get('result_code') != 0:
        print("Failed to get QR code:", qr_res)
        return

    uuid = qr_res['uuid']
    img_b64 = qr_res['image']
    qr_file = os.path.join(os.path.dirname(__file__), "12306_login_qr.png")
    client.save_qr_image(img_b64, qr_file)
    print(f"QR code saved to: {qr_file}")
    print(f"UUID: {uuid}")
    print("Please scan this QR code with 12306 mobile app.")

    # Poll QR code
    start_time = time.time()
    while time.time() - start_time < 120:
        status_res = client.check_qr(uuid)
        code = status_res.get('result_code')
        msg = status_res.get('result_message')
        print(f"[{int(time.time() - start_time)}s] QR status: code={code}, msg={msg}")

        if str(code) == '2': # Success
            uamtk = status_res.get('uamtk')
            print(f"\nScan confirmed! Exchanging tokens with uamtk: {uamtk}...")
            ok, login_msg = client.complete_login(uamtk)
            print("Login outcome:", ok, login_msg)
            if ok:
                passengers = client.get_passengers()
                print(f"Passengers found ({len(passengers)}):")
                for p in passengers:
                    print(f"- {p.get('passenger_name')} ({p.get('passenger_id_type_name')}: {p.get('passenger_id_no')})")
            break
        elif str(code) == '3': # Expired
            print("QR code expired! Please run again.")
            break
        elif str(code) == '1': # Scanned, waiting confirm
            print("QR code scanned by user, awaiting confirmation on phone...")

        time.sleep(3)

if __name__ == '__main__':
    main()
