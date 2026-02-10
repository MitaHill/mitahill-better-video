# Real IP Deployment Guide (Nginx / FRP / Proxy Protocol)

## 1. Backend .env settings

建议在 `config/.env` 中配置：

```env
# 管理初始密码（首次启动时写入数据库哈希）
ADMIN_INITIAL_PASSWORD=please_change_this_password

# 管理会话有效期（小时）
ADMIN_SESSION_TTL_HOURS=24

# 受信任代理网段（逗号分隔，CIDR）
REAL_IP_TRUSTED_PROXIES=127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7

# Worker -> API 事件鉴权令牌（可选但推荐）
EVENTS_SHARED_TOKEN=replace_with_random_token
```

说明：
- `REAL_IP_TRUSTED_PROXIES` 是默认值，启动后会写入数据库。
- 你可以在“后端管理 -> 受信代理配置”中在线修改，修改后立即生效。

## 2. Nginx standard reverse proxy

```nginx
server {
    listen 443 ssl;
    server_name your.domain;

    location / {
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8501;
    }
}
```

## 3. Nginx with Proxy Protocol (FRP/L4 forwarding)

当上游（如 FRP）启用 `proxyProtocolVersion` 时，Nginx 需显式接收并回写真实IP：

```nginx
server {
    listen 443 ssl proxy_protocol;
    server_name your.domain;

    # 信任 FRP 服务端出口IP
    set_real_ip_from 203.0.113.10;
    real_ip_header proxy_protocol;
    real_ip_recursive on;

    location / {
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8501;
    }
}
```

## 4. FRP side notes

- FRP 服务端与 Nginx 之间若传递 Proxy Protocol，必须保证版本匹配。
- 若链路包含多级代理，请把每一级代理出口网段加入 `REAL_IP_TRUSTED_PROXIES`。
- 程序会自动识别 IPv4/IPv6、局域网地址、回环地址，并用于后端管理页统计。

## 5. Validation checklist

1. 访问前端后创建任务，进入“后端管理”。
2. 在任务表中确认 `client_ip` 与公网访问地址一致。
3. 在 IP 统计中确认 IPv4/IPv6、局域网/公网分类正确。
4. 使用错误管理密码应被拒绝（401）。
5. 修改密码后，旧 Token 应失效并需重新登录。
