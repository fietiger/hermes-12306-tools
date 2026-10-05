# hermes-12306-tools

12306 ticket query / booking automation used by Hermes Agent.

## Layout

| Path | Purpose |
| --- | --- |
| `client.py` | Core client: QR login, SMS login, query, passengers, order flow |
| `sm4_util.py` | Native SM4 password encryption (12306 login) |
| `tools.py` | Hermes plugin tool handlers (v0.21 plugin spec) |
| `daemon_heartbeat.py` | Session keep-alive + proactive cancel of unpaid orders |
| `station_names.json` | Official station telegraphic-code mapping |
| `scripts/` | Standalone CLI experiments and one-off probes |

## Session keep-alive

12306 force-logs-out a web session when an order sits unpaid past ~20 minutes.
`daemon_heartbeat.py` polls the wallet and cancels any still-unpaid order at
the 19m30s mark, which both avoids the forced logout and keeps the session
usable for the next booking attempt.

## Credentials

`session_cookies.txt` holds a live `MozillaCookieJar` and is **gitignored**.
Any script that triggers a real booking reads its identity and itinerary from
the environment rather than hardcoding it:

```
T12306_TRAIN_CODE  T12306_TRAIN_DATE  T12306_FROM  T12306_TO  T12306_PASSENGER
```

Never commit cookies, passenger names, or ID numbers.
