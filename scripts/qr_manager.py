import base64
import os
import subprocess
import sys
import time
from client import Client12306

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
QR_IMAGE_PATH = os.path.join(DATA_DIR, "12306_login_qr.png")

def push_qr_to_weixin(image_path: str):
    cmd = ["hermes", "send", "--to", "weixin", f"【12306 登录】请使用 12306 官方手机 App 扫描下方二维码确认登录：\nMEDIA:{image_path}"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        print("Pushed QR to weixin:", res.stdout, res.stderr)
        return res.returncode == 0
    except Exception as e:
        print("Failed to push to weixin:", e)
        return False

def push_message_to_weixin(text: str):
    cmd = ["hermes", "send", "--to", "weixin", text]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except Exception as e:
        print("Failed to push text to weixin:", e)

def trigger_login_flow():
    client = Client12306()
    print("Checking existing login status...")
    check = client.check_user()
    if isinstance(check, dict) and check.get('data', {}).get('flag') is True:
        msg = "12306 当前已处于登录状态！"
        print(msg)
        return True, msg

    qr_res = client.create_qr()
    if not isinstance(qr_res, dict) or str(qr_res.get('result_code')) != '0':
        err = f"获取 12306 二维码失败: {qr_res}"
        print(err)
        return False, err

    uuid = qr_res['uuid']
    b64_img = qr_res['image']
    client.save_qr_image(b64_img, QR_IMAGE_PATH)

    print(f"QR code created. UUID={uuid}. Pushing to Weixin...")
    push_qr_to_weixin(QR_IMAGE_PATH)

    start = time.time()
    while time.time() - start < 120:
        st = client.check_qr(uuid)
        code = str(st.get('result_code'))
        if code == '2':
            uamtk = st.get('uamtk')
            ok, login_msg = client.complete_login(uamtk)
            if ok:
                passengers = client.get_passengers()
                p_names = [p.get('passenger_name') for p in passengers]
                succ_text = f"✅ 12306 扫码登录成功！\n常用乘车人：{', '.join(p_names)}"
                push_message_to_weixin(succ_text)
                return True, succ_text
            else:
                fail_text = f"❌ 12306 登录授权交换失败: {login_msg}"
                push_message_to_weixin(fail_text)
                return False, fail_text
        elif code == '3':
            exp_text = "⚠️ 12306 登录二维码已过期，请重新发起登录。"
            push_message_to_weixin(exp_text)
            return False, exp_text
        time.sleep(3)

    timeout_text = "⚠️ 12306 登录扫码超时（2分钟未扫码）。"
    push_message_to_weixin(timeout_text)
    return False, timeout_text

if __name__ == '__main__':
    trigger_login_flow()
