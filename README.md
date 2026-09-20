# Hermes 12306 Tools Plugin

A standard, native tool plugin for Hermes Agent v0.21+ that enables natural language interaction with China Railway 12306.

## Features
- **`train_login_qr`**: Generates a 12306 QR code and pushes it as a WeChat native media image to authorize Hermes.
- **`train_check_login`**: Verifies whether the QR code was scanned and confirmed.
- **`train_query_tickets`**: Real-time high-speed & regular train ticket availability, schedules, and seat prices.
- **`train_list_passengers`**: Retrieves verified passenger contacts from the authorized 12306 account.
- **`train_order_ticket`**: Locks seats and creates a pending order on 12306 for secure mobile app payment.

## Architecture
- Complies with the Hermes Agent v0.21 plugin specification (`register_tools(ctx)`).
- Placed under `/opt/data/plugins/tools/12306_tools/` for zero-downtime hot-loading.
