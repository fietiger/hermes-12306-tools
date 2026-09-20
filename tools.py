"""
Hermes 12306 Tools Plugin (v0.21 standard plugin specification)
Provides tool handlers for QR login, session check, ticket queries, passengers, and booking.
"""

import os
import sys
import json
import base64
import time
from typing import Any, Dict, List, Optional

# Add /opt/data/12306 to path for Client12306 and QRManager
SYS_12306_DIR = "/opt/data/12306"
if SYS_12306_DIR not in sys.path:
    sys.path.append(SYS_12306_DIR)

from client import Client12306


# Global cached client instance
_CLIENT_INSTANCE: Optional[Client12306] = None

def get_client() -> Client12306:
    global _CLIENT_INSTANCE
    if _CLIENT_INSTANCE is None:
        _CLIENT_INSTANCE = Client12306()
    return _CLIENT_INSTANCE


def handle_train_login_qr(**kwargs) -> str:
    """
    Generate a new 12306 QR code for login, save image to disk, and return instructions.
    """
    c = get_client()
    res = c.get_login_qr()
    if not res.get("image_bytes"):
        return json.dumps({"success": False, "error": res.get("error", "无法获取12306登录二维码")}, ensure_ascii=False)
    
    # Save image to web/media accessible path
    qr_dir = "/opt/data/cache/images"
    os.makedirs(qr_dir, exist_ok=True)
    qr_filename = f"12306_login_qr_{int(time.time())}.jpg"
    qr_path = os.path.join(qr_dir, qr_filename)
    
    with open(qr_path, "wb") as f:
        f.write(res["image_bytes"])
        
    return json.dumps({
        "success": True,
        "uuid": res.get("uuid"),
        "image_path": qr_path,
        "media_marker": f"MEDIA:{qr_path}",
        "message": "请使用「铁路12306」手机 App 扫码并在手机上点击「确认登录」。扫码完成后请回复「我已确认登录」或由系统自动检查。"
    }, ensure_ascii=False)


def handle_train_check_login(uuid: Optional[str] = None, **kwargs) -> str:
    """
    Check if the QR code was scanned and confirmed on 12306 App.
    """
    c = get_client()
    res = c.check_qr_status(uuid=uuid)
    return json.dumps(res, ensure_ascii=False)


def handle_train_query_tickets(
    date: str,
    from_station: str,
    to_station: str,
    high_speed_only: bool = True,
    **kwargs
) -> str:
    """
    Query train tickets between two stations on a given date (YYYY-MM-DD).
    """
    c = get_client()
    trains = c.query_tickets(date, from_station, to_station)
    if not trains:
        return json.dumps({"success": False, "count": 0, "message": f"未查询到 {date} 从 {from_station} 到 {to_station} 的列车信息。"}, ensure_ascii=False)
    
    results = []
    for t in trains:
        code = t.get("train_code", "")
        if high_speed_only and not (code.startswith("G") or code.startswith("D") or code.startswith("C")):
            continue
        
        results.append({
            "train_code": code,
            "from_station": t.get("from_station"),
            "to_station": t.get("to_station"),
            "start_time": t.get("start_time"),
            "arrive_time": t.get("arrive_time"),
            "duration": t.get("duration"),
            "can_buy": t.get("can_buy"),
            "second_class": t.get("second_class_seat", "--"),
            "first_class": t.get("first_class_seat", "--"),
            "business_seat": t.get("business_seat", "--"),
            "train_no": t.get("train_no")
        })
        
    return json.dumps({
        "success": True,
        "date": date,
        "from": from_station,
        "to": to_station,
        "count": len(results),
        "trains": results[:20]  # top 20 trains
    }, ensure_ascii=False)


def handle_train_list_passengers(**kwargs) -> str:
    """
    List common passengers bound to the logged-in 12306 account.
    """
    c = get_client()
    res = c.get_passengers()
    return json.dumps(res, ensure_ascii=False)


def handle_train_order_ticket(
    train_code: str,
    date: str,
    from_station: str,
    to_station: str,
    seat_type: str,
    passenger_names: List[str],
    **kwargs
) -> str:
    """
    Submit a ticket booking order for specified train, date, seat, and passengers.
    """
    c = get_client()
    res = c.order_ticket(
        train_code=train_code,
        train_date=date,
        from_station=from_station,
        to_station=to_station,
        seat_type=seat_type,
        passenger_names=passenger_names
    )
    return json.dumps(res, ensure_ascii=False)


# ==============================================================================
# JSON Schemas
# ==============================================================================
TRAIN_LOGIN_QR_SCHEMA = {
    "type": "object",
    "properties": {},
    "description": "生成12306登录二维码，用于用户使用手机12306 App扫码授权登录Hermes。"
}

TRAIN_CHECK_LOGIN_SCHEMA = {
    "type": "object",
    "properties": {
        "uuid": {
            "type": "string",
            "description": "可选。登录请求返回的二维码UUID，若不传则检测最后一次生成的二维码状态。"
        }
    },
    "description": "检查12306二维码登录状态（是否已扫码或已确认授权）。"
}

TRAIN_QUERY_TICKETS_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {
            "type": "string",
            "description": "出发日期，格式为 YYYY-MM-DD，例如 '2026-09-25'"
        },
        "from_station": {
            "type": "string",
            "description": "出发城市或车站名称，例如 '深圳' 或 '深圳北'"
        },
        "to_station": {
            "type": "string",
            "description": "到达城市或车站名称，例如 '长沙' 或 '长沙南'"
        },
        "high_speed_only": {
            "type": "boolean",
            "description": "是否仅查询高铁/动车（G/D/C字头车次），默认为 true",
            "default": True
        }
    },
    "required": ["date", "from_station", "to_station"],
    "description": "查询指定日期两地之间的12306火车余票与车次时刻信息。"
}

TRAIN_LIST_PASSENGERS_SCHEMA = {
    "type": "object",
    "properties": {},
    "description": "获取当前已登录12306账号的常用联系人乘车人列表。"
}

TRAIN_ORDER_TICKET_SCHEMA = {
    "type": "object",
    "properties": {
        "train_code": {
            "type": "string",
            "description": "车次号，例如 'G5892'"
        },
        "date": {
            "type": "string",
            "description": "出发日期，格式为 YYYY-MM-DD"
        },
        "from_station": {
            "type": "string",
            "description": "出发站名称，例如 '深圳北'"
        },
        "to_station": {
            "type": "string",
            "description": "到达站名称，例如 '长沙南'"
        },
        "seat_type": {
            "type": "string",
            "description": "坐席类型，如 '二等座', '一等座', '商务座', '硬卧', '软卧'",
            "default": "二等座"
        },
        "passenger_names": {
            "type": "array",
            "items": {"type": "string"},
            "description": "乘车人姓名列表，例如 ['程子越']"
        }
    },
    "required": ["train_code", "date", "from_station", "to_station", "seat_type", "passenger_names"],
    "description": "向12306提交锁座下单请求。锁定席位后会生成待支付订单，需用户在12306 App中完成支付。"
}

ALL_TOOLS = (
    ("train_login_qr", TRAIN_LOGIN_QR_SCHEMA, handle_train_login_qr, "🎫"),
    ("train_check_login", TRAIN_CHECK_LOGIN_SCHEMA, handle_train_check_login, "🔍"),
    ("train_query_tickets", TRAIN_QUERY_TICKETS_SCHEMA, handle_train_query_tickets, "🚄"),
    ("train_list_passengers", TRAIN_LIST_PASSENGERS_SCHEMA, handle_train_list_passengers, "👥"),
    ("train_order_ticket", TRAIN_ORDER_TICKET_SCHEMA, handle_train_order_ticket, "📝"),
)

def register_tools(ctx) -> None:
    """Standard Hermes v0.21 entrypoint for tool discovery."""
    for name, schema, handler, emoji in ALL_TOOLS:
        try:
            ctx.register_tool(
                name=name,
                toolset="12306_tools",
                schema=schema,
                handler=handler,
                emoji=emoji,
            )
        except Exception:
            pass
