import sys
import time
import os
from client import Client12306

def main():
    c = Client12306()
    qr_path = '/opt/data/cache/images/qr_stream.png'
    print("STARTING_STREAM_LOOP")
    
    # Run a continuous loop generating new QR codes when they expire,
    # updating the exact same image file on disk!
    while True:
        qr = c.create_qr()
        uuid = qr.get('uuid')
        if not uuid:
            time.sleep(2)
            continue
            
        c.save_qr_image(qr['image'], qr_path)
        print(f"NEW_QR_READY: {uuid}")
        
        # Poll this UUID until confirmed or expired
        start = time.time()
        confirmed = False
        while time.time() - start < 35:
            res = c.check_qr(uuid)
            code = str(res.get('result_code'))
            if code == '1':
                print(f"SCANNED_WAITING_CONFIRM")
            elif code == '2':
                uamtk = res.get('uamtk')
                ok, msg = c.complete_login(uamtk)
                print(f"LOGIN_COMPLETED: {ok} {msg}")
                if ok:
                    confirmed = True
                    return
            elif code == '3':
                print(f"QR_EXPIRED_REFRESHING")
                break
            time.sleep(1.5)
            
        if confirmed:
            break

if __name__ == '__main__':
    main()
