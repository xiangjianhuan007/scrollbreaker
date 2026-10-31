"""OCR 适配层：本项目不绑定任何 OCR 引擎。

设计原则：**OCR 是可替换的**。滚动分页逻辑才是这个项目的价值，
所以这里只定义一个极小的协议，你想用哪个引擎都行。

自带三种：
  NullOCR      —— 不做 OCR，直接把传入的文本当结果（写测试/离线回放用）
  CmdOCR       —— 调任意命令行 OCR（tesseract / paddleocr-cli / 自建服务）
  CallableOCR  —— 传一个 Python 函数进来

如果你的引擎返回带坐标的结果，按行分组后传进来即可 —— 本项目只关心「行」。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Protocol, Sequence


class OCR(Protocol):
    def read(self, image_bytes: bytes) -> str:  # pragma: no cover - protocol
        ...


class NullOCR:
    """不识别，返回空串（或一个固定文本，便于测试）。"""

    def __init__(self, fixed: str = ""):
        self.fixed = fixed

    def read(self, image_bytes: bytes) -> str:
        return self.fixed


class CallableOCR:
    """包装一个 (bytes) -> str 的函数。"""

    def __init__(self, fn: Callable[[bytes], str]):
        self.fn = fn

    def read(self, image_bytes: bytes) -> str:
        return self.fn(image_bytes)


class CmdOCR:
    """调命令行 OCR。

    tesseract 例子：
        CmdOCR(["tesseract", "{img}", "stdout", "-l", "chi_sim+eng", "--psm", "6"])

    `{img}` 会被替换成临时图片路径。输出里的行顺序即屏幕顺序。
    """

    def __init__(self, argv: Sequence[str], timeout: float = 30.0, cleanup: bool = True):
        self.argv = list(argv)
        self.timeout = timeout
        self.cleanup = cleanup

    def available(self) -> bool:
        if not self.argv:
            return False
        if shutil.which(self.argv[0]) is None:
            return False
        return True

    def read(self, image_bytes: bytes) -> str:
        if not self.available():
            raise RuntimeError(f"OCR 可执行文件不存在: {self.argv[0] if self.argv else '(empty)'}")
        suffix = ".png"
        if image_bytes[:2] == b"\xff\xd8":
            suffix = ".jpg"
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            with open(fd, "wb") as f:
                f.write(image_bytes)
            argv = [a.replace("{img}", path) for a in self.argv]
            out = subprocess.run(argv, capture_output=True, timeout=self.timeout)
            if out.returncode != 0:
                raise RuntimeError(out.stderr.decode("utf-8", "ignore")[:300])
            return out.stdout.decode("utf-8", "ignore")
        finally:
            if self.cleanup:
                Path(path).unlink(missing_ok=True)


def tesseract(lang: str = "chi_sim+eng") -> CmdOCR:
    """tesseract 的常用配置（psm 6 = 假设一列文本，屏幕识别通常最稳）。"""
    return CmdOCR(["tesseract", "{img}", "stdout", "-l", lang, "--psm", "6"])
