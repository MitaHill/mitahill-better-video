import zipfile
import struct
import shutil


def zip_paths(paths, zip_path, root_dir):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            if not path.exists():
                continue
            if path.is_file():
                info = zipfile.ZipInfo.from_file(path, arcname=str(path.relative_to(root_dir)), strict_timestamps=False)
                # UT 扩展用 UTC 保存秒级 mtime，避免 ZIP 的本地时区和 2 秒精度限制。
                timestamp = int(path.stat().st_mtime)
                if 0 <= timestamp <= 0xffffffff:
                    info.extra += struct.pack('<HHBI', 0x5455, 5, 1, timestamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                with path.open('rb') as source, zf.open(info, 'w') as target:
                    shutil.copyfileobj(source, target)
                continue
            for child in path.rglob("*"):
                if child.is_file():
                    zf.write(child, arcname=str(child.relative_to(root_dir)))
