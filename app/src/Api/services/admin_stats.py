from app.src.Database import admin as db_admin


def build_overview(limit=200, offset=0, status=""):
    counts = db_admin.get_task_counts()
    tasks = db_admin.list_tasks(limit=limit, offset=offset, status=status)
    ip_stats = db_admin.get_ip_access_stats(limit=200)
    return {
        "counts": {
            "total": counts.get("TOTAL", 0),
            "pending": counts.get("PENDING", 0),
            "processing": counts.get("PROCESSING", 0),
            "completed": counts.get("COMPLETED", 0),
            "failed": counts.get("FAILED", 0),
        },
        "tasks": tasks,
        "ip_stats": ip_stats,
    }
