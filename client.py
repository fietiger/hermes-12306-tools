import base64
import http.cookiejar
import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(DATA_DIR, "session_cookies.txt")
STATION_FILE = os.path.join(DATA_DIR, "station_names.json")

COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

class Client12306:
    def __init__(self):
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

        self.cookie_jar = http.cookiejar.MozillaCookieJar(COOKIE_FILE)
        if os.path.exists(COOKIE_FILE):
            try:
                self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
            except Exception:
                pass

        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            urllib.request.HTTPSHandler(context=self.ssl_ctx)
        )
        self._ensure_device_id()
        self.station_map: Dict[str, str] = {}
        self.reverse_station_map: Dict[str, str] = {}
        self.query_path: str = "queryG"
        self._load_stations()
        self._detect_query_endpoint()

    def _save_cookies(self):
        try:
            self.cookie_jar.save(ignore_discard=True, ignore_expires=True)
        except Exception:
            pass

    def _ensure_device_id(self):
        has_device = any(ck.name == 'RAIL_DEVICEID' for ck in self.cookie_jar)
        if not has_device:
            import http.cookiejar
            import time
            exp_val = int((time.time() + 86400 * 365) * 1000)
            c_dev = http.cookiejar.Cookie(
                version=0, name='RAIL_DEVICEID', value='ng8GWpVBAs1dnOxtsAEnQ1EyfbEuCIGetci8OLRrXAtY_grSokW5WZb10aDdNS_Je4KbKlgf3fPtO4cZJGCox4ORGXGZ8Fhcq6TDWW1iuLlaU2kLccvL22V_HBd49idoCqL0dJEbfl3Plhhno73VZqQY5aKeAHHJ',
                port=None, port_specified=False, domain='kyfw.12306.cn',
                domain_specified=True, domain_initial_dot=False, path='/',
                path_specified=True, secure=False, expires=int(time.time() + 86400 * 365),
                discard=False, comment=None, comment_url=None, rest={'HttpOnly': None}
            )
            c_exp = http.cookiejar.Cookie(
                version=0, name='RAIL_EXPIRATION', value=str(exp_val),
                port=None, port_specified=False, domain='kyfw.12306.cn',
                domain_specified=True, domain_initial_dot=False, path='/',
                path_specified=True, secure=False, expires=int(time.time() + 86400 * 365),
                discard=False, comment=None, comment_url=None, rest={'HttpOnly': None}
            )
            self.cookie_jar.set_cookie(c_dev)
            self.cookie_jar.set_cookie(c_exp)
            self._save_cookies()

    def _request(self, url: str, method: str = 'GET', data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        req_headers = COMMON_HEADERS.copy()
        if headers:
            req_headers.update(headers)

        encoded_data = None
        if data is not None:
            if req_headers.get('Content-Type') == 'application/json':
                encoded_data = json.dumps(data).encode('utf-8')
            else:
                encoded_data = urllib.parse.urlencode(data).encode('utf-8')

        req = urllib.request.Request(url, data=encoded_data, headers=req_headers, method=method)
        with self.opener.open(req, timeout=15) as resp:
            content_type = resp.headers.get('Content-Type', '')
            raw_body = resp.read()
            self._save_cookies()
            if 'json' in content_type or raw_body.startswith(b'{') or raw_body.startswith(b'['):
                try:
                    return json.loads(raw_body.decode('utf-8'))
                except Exception:
                    return raw_body.decode('utf-8', errors='ignore')
            return raw_body.decode('utf-8', errors='ignore')

    def _load_stations(self):
        if os.path.exists(STATION_FILE):
            try:
                with open(STATION_FILE, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    self.station_map = cached.get('name_to_code', {})
                    self.reverse_station_map = cached.get('code_to_name', {})
                    if self.station_map:
                        return
            except Exception:
                pass
        self.refresh_stations()

    def refresh_stations(self) -> bool:
        url = 'https://kyfw.12306.cn/otn/resources/js/framework/station_name.js'
        try:
            resp = self._request(url)
            match = re.search(r"'(.*)'", resp)
            if not match:
                return False
            raw_data = match.group(1)
            records = raw_data.strip('@').split('@')
            name_to_code = {}
            code_to_name = {}
            for rec in records:
                parts = rec.split('|')
                if len(parts) >= 3:
                    name = parts[1]
                    code = parts[2]
                    name_to_code[name] = code
                    code_to_name[code] = name
            self.station_map = name_to_code
            self.reverse_station_map = code_to_name
            with open(STATION_FILE, 'w', encoding='utf-8') as f:
                json.dump({'name_to_code': name_to_code, 'code_to_name': code_to_name}, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Failed to refresh stations: {e}")
            return False

    def _detect_query_endpoint(self):
        try:
            html = self._request('https://kyfw.12306.cn/otn/leftTicket/init')
            match = re.findall(r'leftTicket/query[A-Za-z0-9_]*', html)
            if match:
                ep = match[0].split('/')[-1]
                self.query_path = ep
        except Exception:
            self.query_path = "queryG"

    def get_station_code(self, station_name: str) -> Optional[str]:
        return self.station_map.get(station_name)

    def get_station_name(self, station_code: str) -> Optional[str]:
        return self.reverse_station_map.get(station_code)

    def query_tickets(self, train_date: str, from_station: str, to_station: str, purpose_codes: str = 'ADULT') -> List[Dict[str, Any]]:
        from_code = self.get_station_code(from_station) or from_station
        to_code = self.get_station_code(to_station) or to_station

        url = f"https://kyfw.12306.cn/otn/leftTicket/{self.query_path}?leftTicketDTO.train_date={train_date}&leftTicketDTO.from_station={from_code}&leftTicketDTO.to_station={to_code}&purpose_codes={purpose_codes}"
        headers = {
            'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init',
            'Accept': '*/*',
            'Cookie': f'_jc_save_fromStation={urllib.parse.quote(from_station)},{from_code}; _jc_save_toStation={urllib.parse.quote(to_station)},{to_code}; _jc_save_fromDate={train_date}; _jc_save_toDate={train_date}; _jc_save_wfdc_flag=dc'
        }
        res = self._request(url, method='GET', headers=headers)
        if isinstance(res, dict) and res.get('httpstatus') == 200 and res.get('data'):
            raw_results = res['data'].get('result', [])
            station_map_resp = res['data'].get('map', {})
            parsed = []
            for item in raw_results:
                fields = item.split('|')
                if len(fields) < 35:
                    continue
                secret_str = fields[0]
                remark = fields[1]
                train_no = fields[2]
                station_train_code = fields[3]
                start_station_code = fields[4]
                end_station_code = fields[5]
                from_station_code = fields[6]
                to_station_code = fields[7]
                start_time = fields[8]
                arrive_time = fields[9]
                duration = fields[10]
                can_web_buy = fields[11]
                yp_info = fields[12]
                start_train_date = fields[13]
                train_seat_feature = fields[14]
                location_code = fields[15]
                seat_types = fields[35] if len(fields) > 35 else ""

                parsed.append({
                    'secret_str': urllib.parse.unquote(secret_str) if secret_str else '',
                    'remark': remark,
                    'train_code': station_train_code,
                    'train_no': train_no,
                    'from_station': station_map_resp.get(from_station_code, self.get_station_name(from_station_code) or from_station_code),
                    'to_station': station_map_resp.get(to_station_code, self.get_station_name(to_station_code) or to_station_code),
                    'from_station_code': from_station_code,
                    'to_station_code': to_station_code,
                    'start_time': start_time,
                    'arrive_time': arrive_time,
                    'duration': duration,
                    'can_buy': (can_web_buy == 'Y'),
                    'business_seat': fields[32] or fields[25] or '--',
                    'first_class_seat': fields[31] or '--',
                    'second_class_seat': fields[30] or '--',
                    'soft_sleeper': fields[23] or '--',
                    'hard_sleeper': fields[28] or '--',
                    'hard_seat': fields[29] or '--',
                    'no_seat': fields[26] or '--',
                    'yp_info': yp_info,
                    'train_seat_feature': train_seat_feature,
                    'location_code': location_code,
                    'start_train_date': start_train_date,
                    'seat_types': seat_types
                })
            return parsed
        return []

    def create_qr(self) -> Dict[str, Any]:
        url = 'https://kyfw.12306.cn/passport/web/create-qr64'
        data = {'appid': 'otn'}
        headers = {
            'Referer': 'https://kyfw.12306.cn/otn/resources/login.html',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        res = self._request(url, method='POST', data=data, headers=headers)
        return res

    def save_qr_image(self, base64_data: str, output_path: str) -> bool:
        try:
            img_bytes = base64.b64decode(base64_data)
            with open(output_path, 'wb') as f:
                f.write(img_bytes)
            return True
        except Exception as e:
            print(f"Error saving QR image: {e}")
            return False

    def check_qr(self, uuid: str) -> Dict[str, Any]:
        url = 'https://kyfw.12306.cn/passport/web/checkqr'
        data = {'appid': 'otn', 'uuid': uuid}
        headers = {
            'Referer': 'https://kyfw.12306.cn/otn/resources/login.html',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return self._request(url, method='POST', data=data, headers=headers)

    def complete_login(self, uamtk: str) -> Tuple[bool, str]:
        url_uamtk = 'https://kyfw.12306.cn/passport/web/auth/uamtk'
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        headers = {
            'User-Agent': ua,
            'Referer': 'https://kyfw.12306.cn/otn/resources/login.html',
            'Origin': 'https://kyfw.12306.cn',
            'Host': 'kyfw.12306.cn',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        res1 = self._request(url_uamtk, method='POST', data={'appid': 'otn'}, headers=headers)
        if not isinstance(res1, dict) or res1.get('result_code') != 0:
            return False, f"uamtk verification failed: {res1}"

        newapptk = res1.get('newapptk') or res1.get('apptk')
        if not newapptk:
            return False, "No newapptk returned in uamtk"

        url_client = 'https://kyfw.12306.cn/otn/uamauthclient'
        headers_client = {
            'User-Agent': ua,
            'Referer': 'https://kyfw.12306.cn/otn/passport?param=/otn/resources/login.html',
            'Origin': 'https://kyfw.12306.cn',
            'Host': 'kyfw.12306.cn',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        res2 = self._request(url_client, method='POST', data={'tk': newapptk}, headers=headers_client)
        if isinstance(res2, dict) and res2.get('result_code') == 0:
            user_name = res2.get('username', 'Unknown')
            self._save_cookies()
            return True, f"Login success for user: {user_name}"
        return False, f"uamauthclient failed: {res2}"

    def check_user(self) -> Dict[str, Any]:
        url = 'https://kyfw.12306.cn/otn/login/checkUser'
        data = {'_json_att': ''}
        headers = {
            'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return self._request(url, method='POST', data=data, headers=headers)

    def get_passengers(self) -> List[Dict[str, Any]]:
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/getPassengerDTOs'
        data = {'_json_att': ''}
        headers = {
            'Referer': 'https://kyfw.12306.cn/otn/confirmPassenger/initDc',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        res = self._request(url, method='POST', data=data, headers=headers)
        if isinstance(res, dict) and res.get('status') and res.get('data'):
            return res['data'].get('normal_passengers', [])
        return []

    # ==================== 订票流程封装 (Order Flow) ====================

    def submit_order_request(self, secret_str: str, train_date: str, back_train_date: str, tour_flag: str, purpose_codes: str, from_station_name: str, to_station_name: str) -> Dict[str, Any]:
        url = 'https://kyfw.12306.cn/otn/leftTicket/submitOrderRequest'
        data = {
            'secretStr': secret_str,
            'train_date': train_date,
            'back_train_date': back_train_date,
            'tour_flag': tour_flag,
            'purpose_codes': purpose_codes,
            'query_from_station_name': from_station_name,
            'query_to_station_name': to_station_name,
            'undefined': ''
        }
        headers = {
            'Referer': f'https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return self._request(url, method='POST', data=data, headers=headers)

    def init_dc(self) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/initDc'
        data = {'_json_att': ''}
        headers = {
            'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        html = self._request(url, method='POST', data=data, headers=headers)
        token_match = re.search(r"var globalRepeatSubmitToken = '([^']+)';", html)
        ticket_info_match = re.search(r'var ticketInfoForPassengerForm = ({.*?});', html, re.DOTALL)
        token = token_match.group(1) if token_match else None
        ticket_info = None
        if ticket_info_match:
            try:
                ticket_info = json.loads(ticket_info_match.group(1).replace("'", '"'))
            except Exception:
                pass
        return token, ticket_info

    def check_order_info(self, passenger_ticket_str: str, old_passenger_str: str, repeat_submit_token: str, tour_flag: str = 'dc') -> Dict[str, Any]:
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/checkOrderInfo'
        data = {
            'cancel_flag': '2',
            'bed_level_order_num': '000000000000000000000000000000',
            'passengerTicketStr': passenger_ticket_str,
            'oldPassengerStr': old_passenger_str,
            'tour_flag': tour_flag,
            'randCode': '',
            'whatsSelect': '1',
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': repeat_submit_token
        }
        headers = {
            'Referer': 'https://kyfw.12306.cn/otn/confirmPassenger/initDc',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return self._request(url, method='POST', data=data, headers=headers)

    def get_queue_count(self, train_date: str, train_no: str, station_train_code: str, seat_type: str, from_station_telecode: str, to_station_telecode: str, left_ticket: str, repeat_submit_token: str) -> Dict[str, Any]:
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/getQueueCount'
        data = {
            'train_date': time.strftime("%a %b %d %Y 00:00:00 GMT+0800 (中国标准时间)", time.strptime(train_date, "%Y-%m-%d")),
            'train_no': train_no,
            'stationTrainCode': station_train_code,
            'seatType': seat_type,
            'fromStationTelecode': from_station_telecode,
            'toStationTelecode': to_station_telecode,
            'leftTicket': left_ticket,
            'purpose_codes': '00',
            'train_location': 'Q7',
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': repeat_submit_token
        }
        headers = {
            'Referer': 'https://kyfw.12306.cn/otn/confirmPassenger/initDc',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return self._request(url, method='POST', data=data, headers=headers)

    def confirm_single_for_queue(self, passenger_ticket_str: str, old_passenger_str: str, repeat_submit_token: str, key_check_is_change: str, left_ticket_str: str, train_location: str, choose_seats: str = '') -> Dict[str, Any]:
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/confirmSingleForQueue'
        data = {
            'passengerTicketStr': passenger_ticket_str,
            'oldPassengerStr': old_passenger_str,
            'randCode': '',
            'purpose_codes': '00',
            'key_check_isChange': key_check_is_change,
            'leftTicketStr': left_ticket_str,
            'train_location': train_location,
            'choose_seats': choose_seats,
            'seatDetailType': '000',
            'is_jy': 'N',
            'is_cj': 'N',
            'encryptedData': '',
            'whatsSelect': '1',
            'roomType': '00',
            'dwAll': 'N',
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': repeat_submit_token
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://kyfw.12306.cn/otn/confirmPassenger/initDc',
            'Origin': 'https://kyfw.12306.cn',
            'Host': 'kyfw.12306.cn',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return self._request(url, method='POST', data=data, headers=headers)

    def query_no_complete_order(self) -> Dict[str, Any]:
        url = 'https://kyfw.12306.cn/otn/queryOrder/queryMyOrderNoComplete'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://kyfw.12306.cn/otn/view/train_order.html',
            'Origin': 'https://kyfw.12306.cn',
            'Host': 'kyfw.12306.cn',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return self._request(url, method='POST', data={'_json_att': ''}, headers=headers)

    def cancel_no_complete_order(self, sequence_no: str) -> Dict[str, Any]:
        url = 'https://kyfw.12306.cn/otn/queryOrder/cancelNoCompleteMyOrder'
        data = {
            'sequence_no': sequence_no,
            'cancel_flag': 'cancel_order',
            '_json_att': ''
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://kyfw.12306.cn/otn/view/train_order.html',
            'Origin': 'https://kyfw.12306.cn',
            'Host': 'kyfw.12306.cn',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return self._request(url, method='POST', data=data, headers=headers)

    def send_sms_code(self, username: str, cast_num: str) -> Dict[str, Any]:
        """
        Request SMS verification code:
        cast_num is the last 4 digits of ID card or full ID card number.
        """
        # Ensure login context is pre-initialized
        self.check_login_verify(username)
        url = 'https://kyfw.12306.cn/passport/web/getMessageCode'
        data = {
            'appid': 'otn',
            'username': username,
            'castNum': cast_num
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://kyfw.12306.cn/otn/resources/login.html',
            'Origin': 'https://kyfw.12306.cn',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return self._request(url, method='POST', data=data, headers=headers)

    def check_login_verify(self, username: str) -> Dict[str, Any]:
        url = 'https://kyfw.12306.cn/passport/web/checkLoginVerify'
        data = {
            'appid': 'otn',
            'username': username
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://kyfw.12306.cn/otn/resources/login.html',
            'Origin': 'https://kyfw.12306.cn',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return self._request(url, method='POST', data=data, headers=headers)

    def login_with_sms(self, username: str, password: str, sms_code: str) -> Tuple[bool, str]:
        """
        Complete login with username, raw password, and SMS code.
        """
        try:
            from .sm4_util import encrypt_12306_password
        except ImportError:
            try:
                from sm4_util import encrypt_12306_password
            except ImportError:
                import sys
                sys.path.append('/opt/data/12306')
                from sm4_util import encrypt_12306_password

        encrypted_pwd = encrypt_12306_password(password)
        form_data = {
            'sessionId': '',
            'sig': '',
            'if_check_slide_passcode_token': '',
            'scene': '',
            'checkMode': '0',
            'randCode': sms_code,
            'username': username,
            'password': encrypted_pwd,
            'appid': 'otn'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://kyfw.12306.cn/otn/resources/login.html',
            'Origin': 'https://kyfw.12306.cn',
            'Host': 'kyfw.12306.cn',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        res = self._request('https://kyfw.12306.cn/passport/web/login', method='POST', data=form_data, headers=headers)
        if not res or res.get('result_code') != 0:
            msg = res.get('result_message') if res else '登录请求失败'
            return False, msg

        uamtk = res.get('uamtk')
        return self.complete_login(uamtk)

    def query_order_wait_time(self, repeat_submit_token: str, tour_flag: str = 'dc') -> Dict[str, Any]:
        url = f"https://kyfw.12306.cn/otn/confirmPassenger/queryOrderWaitTime?random={int(time.time()*1000)}&tourFlag={tour_flag}&_json_att=&REPEAT_SUBMIT_TOKEN={repeat_submit_token}"
        headers = {
            'Referer': 'https://kyfw.12306.cn/otn/confirmPassenger/initDc'
        }
        return self._request(url, method='GET', headers=headers)

    def order_ticket(self, train_code: str, train_date: str, from_station: str, to_station: str, seat_type: str = '二等座', passenger_names: Optional[List[str]] = None, choose_seats: str = '') -> Dict[str, Any]:
        """
        Complete ticket booking workflow for specified train, date, stations, seat, and passengers.
        """
        import urllib.parse
        import re
        import ast

        # 1. Map seat type to 12306 seat code
        seat_code_map = {
            '商务座': '9', '特等座': 'P', '一等座': 'M', '二等座': 'O',
            '高级软卧': '6', '软卧': '4', '动卧': 'F', '硬卧': '3',
            '软座': '2', '硬座': '1', '无座': '1'
        }
        seat_code = seat_code_map.get(seat_type, seat_type)

        # 2. Query tickets to find the target train and secret_str
        trains = self.query_tickets(train_date, from_station, to_station)
        target = None
        for t in trains:
            if t.get('train_code') == train_code:
                # If specific stations matched or from_station matches
                if (from_station in t.get('from_station') or not from_station) and (to_station in t.get('to_station') or not to_station):
                    target = t
                    break
        if not target:
            # Fallback search by train_code only
            for t in trains:
                if t.get('train_code') == train_code:
                    target = t
                    break
        if not target:
            return {'success': False, 'message': f'未找到 {train_date} 车次 {train_code}'}

        secret_str = urllib.parse.unquote(target['secret_str'])

        # 3. Submit order request
        submit_res = self.submit_order_request(
            secret_str=secret_str,
            train_date=train_date,
            back_train_date=train_date,
            tour_flag='dc',
            purpose_codes='ADULT',
            from_station_name=target['from_station'],
            to_station_name=target['to_station']
        )

        # 4. Request initDc to get globalRepeatSubmitToken and ticketInfo
        url_init = 'https://kyfw.12306.cn/otn/confirmPassenger/initDc'
        html = self._request(url_init, method='POST', data={'_json_att': ''}, headers={
            'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        })
        if not html:
            return {'success': False, 'message': '获取订单确认页面失败'}

        token_match = re.search(r"globalRepeatSubmitToken\s*=\s*'([^']+)'", html)
        if not token_match:
            # Check if there is an existing uncompleted order
            no_comp = self.query_no_complete_order()
            orders = no_comp.get('data', {}).get('orderDBList', [])
            if orders:
                return {'success': False, 'message': '当前已有未完成支付的订单，请先支付或取消原订单后再购买', 'unpaid_order': orders[0].get('sequence_no')}
            return {'success': False, 'message': '未能解析到订单 Token，请重试'}

        token = token_match.group(1)

        ticket_match = re.search(r"ticketInfoForPassengerForm\s*=\s*({.*?});\s*var", html, re.DOTALL)
        if not ticket_match:
            return {'success': False, 'message': '未能解析到车票详情数据'}

        text_py = ticket_match.group(1).replace('null', 'None').replace('true', 'True').replace('false', 'False')
        ticket_info = ast.literal_eval(text_py)

        left_ticket_str = ticket_info.get('leftTicketStr')
        key_check_is_change = ticket_info.get('key_check_isChange')
        train_location = ticket_info.get('train_location')
        purpose_codes = ticket_info.get('purpose_codes', '00')

        # 5. Build passenger strings
        passengers = self.get_passengers()
        if not passengers:
            # Try auth refresh
            self.complete_login('')
            passengers = self.get_passengers()
        if not passengers:
            return {'success': False, 'message': '未能获取到乘车人列表'}

        if not passenger_names:
            passenger_names = ['程文涛']

        selected_passengers = [p for p in passengers if p.get('passenger_name') in passenger_names]
        if not selected_passengers:
            return {'success': False, 'message': f'未在常用联系人中找到指定的乘车人: {passenger_names}'}

        p_tickets = []
        old_ps = []
        for p in selected_passengers:
            p_ticket = f"{seat_code},0,1,{p['passenger_name']},1,{p['passenger_id_no']},{p['mobile_no']},N,{p['allEncStr']}"
            old_p = f"{p['passenger_name']},1,{p['passenger_id_no']},1_"
            p_tickets.append(p_ticket)
            old_ps.append(old_p)

        passenger_ticket_str = '_'.join(p_tickets)
        old_passenger_str = ''.join(old_ps)

        # 6. Check order info
        res_chk = self.check_order_info(passenger_ticket_str, old_passenger_str, token)
        if not res_chk or not res_chk.get('data', {}).get('submitStatus'):
            err = res_chk.get('data', {}).get('errMsg') if res_chk else '订单信息预校验未通过'
            return {'success': False, 'message': err}

        # 7. Confirm queue
        res_q = self.confirm_single_for_queue(
            passenger_ticket_str=passenger_ticket_str,
            old_passenger_str=old_passenger_str,
            repeat_submit_token=token,
            key_check_is_change=key_check_is_change,
            left_ticket_str=left_ticket_str,
            train_location=train_location,
            choose_seats=choose_seats
        )
        if not res_q or not res_q.get('data', {}).get('submitStatus'):
            err = res_q.get('data', {}).get('errMsg') if res_q else '提交排队失败'
            # If contains unpaid order:
            if '包含未付款' in str(err):
                # Query the order id
                no_comp = self.query_no_complete_order()
                orders = no_comp.get('data', {}).get('orderDBList', [])
                if orders:
                    seq = orders[0].get('sequence_no')
                    return {'success': True, 'order_id': seq, 'message': '已存在待支付订单', 'order_detail': orders[0]}
            return {'success': False, 'message': err}

        # 8. Query order wait time until assigned
        order_id = None
        for _ in range(20):
            time.sleep(1)
            res_wait = self.query_order_wait_time(token)
            data = res_wait.get('data', {})
            order_id = data.get('orderId')
            wait_time = data.get('waitTime')
            if order_id:
                break
            if wait_time == -1 and not order_id:
                break

        if not order_id:
            # Fallback to query_no_complete_order
            no_comp = self.query_no_complete_order()
            orders = no_comp.get('data', {}).get('orderDBList', [])
            if orders:
                order_id = orders[0].get('sequence_no')

        if order_id:
            # Query order detail
            no_comp = self.query_no_complete_order()
            orders = no_comp.get('data', {}).get('orderDBList', [])
            order_info = orders[0] if orders else {}
            return {
                'success': True,
                'order_id': order_id,
                'train_code': train_code,
                'train_date': train_date,
                'from_station': target['from_station'],
                'to_station': target['to_station'],
                'order_info': order_info
            }
        else:
            return {'success': False, 'message': '排队处理超时或未能获取到订单号，请在12306 App查看'}

