from app.src.Config import settings as config
from app.src.Database import admin as db_admin
from app.src.Utils.client_ip import parse_trusted_proxies, resolve_client_ip


def get_trusted_proxies_raw() -> str:
    return db_admin.get_real_ip_trusted_proxies(config.REAL_IP_TRUSTED_PROXIES_RAW)


def get_trusted_proxy_nets():
    return parse_trusted_proxies(get_trusted_proxies_raw())


def resolve_request_client_ip(request) -> str:
    return resolve_client_ip(request, get_trusted_proxy_nets())


def update_trusted_proxies_raw(raw: str):
    text = (raw or "").strip()
    if not text:
        raise ValueError("trusted_proxies cannot be empty")
    parsed = parse_trusted_proxies(text)
    if not parsed:
        raise ValueError("trusted_proxies must include at least one valid CIDR")
    db_admin.update_real_ip_trusted_proxies(text)
    return text
