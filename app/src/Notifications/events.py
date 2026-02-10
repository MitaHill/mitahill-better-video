import requests
from app.src.Config import settings as config


def send_event(payload):
    if not config.EVENTS_ENDPOINT:
        return
    headers = {}
    if config.EVENTS_SHARED_TOKEN:
        headers["X-Event-Token"] = config.EVENTS_SHARED_TOKEN
    try:
        requests.post(config.EVENTS_ENDPOINT, json=payload, timeout=0.5, headers=headers)
    except Exception:
        pass
