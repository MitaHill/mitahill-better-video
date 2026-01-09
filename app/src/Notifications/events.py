import requests
from app.src.Config import settings as config


def send_event(payload):
    if not config.EVENTS_ENDPOINT:
        return
    try:
        requests.post(config.EVENTS_ENDPOINT, json=payload, timeout=0.5)
    except Exception:
        pass
