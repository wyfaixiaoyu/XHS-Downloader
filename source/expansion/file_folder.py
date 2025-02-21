from contextlib import suppress
from pathlib import Path

def file_switch(path: Path) -> None:
    if path.exists():
        path.unlink()
    else:
        path.touch()

def remove_empty_directories(path: Path) -> None:
    exclude = {
        "\\.",
        "\\_",
        "\\__",
    }
    # 遍历所有目录
    for sub_path in path.rglob(''):
        if sub_path.is_dir():
            if any(i in str(sub_path) for i in exclude):
                continue
            # 检查目录是否为空
            if not any(sub_path.iterdir()):
                with suppress(OSError):
                    sub_path.rmdir()
