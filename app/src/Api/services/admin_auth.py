from app.src.Config import settings as config
from app.src.Database import admin as db_admin


def parse_admin_token(request):
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("X-Admin-Token") or "").strip()


def get_admin_session(request):
    token = parse_admin_token(request)
    if not token:
        return None, "missing admin token"
    session = db_admin.get_admin_session_by_token(token)
    if not session:
        return None, "invalid or expired admin token"
    return session, None


def validate_new_password(password: str):
    pwd = (password or "").strip()
    if len(pwd) < 8:
        return None, "new password must be at least 8 characters"
    if len(pwd) > 128:
        return None, "new password is too long"
    return pwd, None


def login(password: str, client_ip: str, user_agent: str):
    if not db_admin.verify_admin_password(password):
        return None, "invalid password"
    session = db_admin.create_admin_session(client_ip, user_agent, config.ADMIN_SESSION_TTL_HOURS)
    return session, None


def change_password(old_password: str, new_password: str):
    if not db_admin.verify_admin_password(old_password):
        return "old password is incorrect"
    safe_pwd, err = validate_new_password(new_password)
    if err:
        return err
    db_admin.update_admin_password(safe_pwd)
    db_admin.delete_all_sessions()
    return None
