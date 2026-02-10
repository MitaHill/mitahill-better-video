import ipaddress
import re
from typing import Iterable, List, Optional


_FORWARD_PAIR_RE = re.compile(r'\s*([a-zA-Z]+)="?([^;,"]+)"?\s*')


def _strip_port(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith("[") and "]" in raw:
        return raw[1 : raw.index("]")]
    if raw.count(":") == 1 and "." in raw:
        host, _port = raw.rsplit(":", 1)
        return host
    return raw


def _normalize_ip(value: str) -> Optional[str]:
    token = _strip_port(value)
    if not token:
        return None
    if token.lower() == "unknown":
        return None
    try:
        return str(ipaddress.ip_address(token))
    except ValueError:
        return None


def parse_forwarded_for(header_value: str) -> List[str]:
    if not header_value:
        return []
    out = []
    for part in header_value.split(","):
        ip_val = _normalize_ip(part)
        if ip_val:
            out.append(ip_val)
    return out


def parse_forwarded_header(header_value: str) -> List[str]:
    """Parse RFC 7239 Forwarded header and return ordered for= values."""
    if not header_value:
        return []
    out = []
    for section in header_value.split(","):
        for kv in section.split(";"):
            match = _FORWARD_PAIR_RE.match(kv)
            if not match:
                continue
            key, value = match.groups()
            if key.lower() != "for":
                continue
            val = value.strip()
            if val.startswith("[") and "]" in val:
                val = val[1 : val.index("]")]
            ip_val = _normalize_ip(val)
            if ip_val:
                out.append(ip_val)
    return out


def parse_trusted_proxies(raw: str) -> List[ipaddress._BaseNetwork]:
    nets = []
    for token in (raw or "").split(","):
        item = token.strip()
        if not item:
            continue
        try:
            nets.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            continue
    return nets


def _is_trusted(ip_value: str, trusted_nets: Iterable[ipaddress._BaseNetwork]) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_value)
    except ValueError:
        return False
    for net in trusted_nets:
        if ip_obj.version != net.version:
            continue
        if ip_obj in net:
            return True
    return False


def resolve_client_ip(request, trusted_proxy_nets: Iterable[ipaddress._BaseNetwork]) -> str:
    """Resolve client IP with proxy-chain awareness.

    Strategy:
    1) Build chain from Forwarded/X-Forwarded-For/X-Real-IP + remote_addr
    2) If trusted proxies configured, walk from right to left and skip trusted hops
    3) Fallback to first valid candidate, else remote_addr, else "unknown"
    """

    candidates: List[str] = []

    forwarded = request.headers.get("Forwarded", "")
    candidates.extend(parse_forwarded_header(forwarded))

    xff = request.headers.get("X-Forwarded-For", "")
    candidates.extend(parse_forwarded_for(xff))

    x_real_ip = _normalize_ip(request.headers.get("X-Real-IP", ""))
    if x_real_ip:
        candidates.append(x_real_ip)

    remote_ip = _normalize_ip(request.remote_addr or "")
    if remote_ip:
        candidates.append(remote_ip)

    if not candidates:
        return "unknown"

    trusted = list(trusted_proxy_nets or [])
    if trusted:
        for hop in reversed(candidates):
            if _is_trusted(hop, trusted):
                continue
            return hop

    return candidates[0]


def describe_ip(ip_text: str):
    try:
        ip_obj = ipaddress.ip_address(ip_text)
    except ValueError:
        return {
            "ip": ip_text,
            "version": 0,
            "is_private": False,
            "is_loopback": False,
            "is_global": False,
            "is_multicast": False,
            "is_reserved": False,
            "scope": "invalid",
        }

    is_private = bool(ip_obj.is_private)
    is_loopback = bool(ip_obj.is_loopback)
    is_global = bool(ip_obj.is_global)
    is_multicast = bool(ip_obj.is_multicast)
    is_reserved = bool(ip_obj.is_reserved)

    if is_loopback:
        scope = "loopback"
    elif is_private:
        scope = "lan"
    elif is_multicast:
        scope = "multicast"
    elif is_reserved:
        scope = "reserved"
    elif is_global:
        scope = "public"
    else:
        scope = "other"

    return {
        "ip": str(ip_obj),
        "version": ip_obj.version,
        "is_private": is_private,
        "is_loopback": is_loopback,
        "is_global": is_global,
        "is_multicast": is_multicast,
        "is_reserved": is_reserved,
        "scope": scope,
    }
