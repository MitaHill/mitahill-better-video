import zipfile


def zip_paths(paths, zip_path, root_dir):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            if not path.exists():
                continue
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(root_dir)))
                continue
            for child in path.rglob("*"):
                if child.is_file():
                    zf.write(child, arcname=str(child.relative_to(root_dir)))
