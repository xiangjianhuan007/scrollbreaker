"""静屏去重：屏幕没动就别重复上报。

两种「没动」：
  1. 内容完全一样 → dHash 汉明距离极小
  2. 状态栏时间跳了一分钟，但正文一个字没变 → 整段归一化后完全一致

第一种在截图层挡掉（省 OCR），第二种在文本层挡掉（省 token）。
"""

from __future__ import annotations

import io
from typing import Optional, Sequence

from .config import Config, DEFAULT_CONFIG


def _to_gray(image_bytes: bytes):
    """把图片字节转成 9x8 灰度二维列表（dHash 只要这个）。"""
    from PIL import Image  # 延迟导入：只用文本链路的人不必装 Pillow

    im = Image.open(io.BytesIO(image_bytes)).convert("L").resize((9, 8))
    px = list(im.getdata())
    return [px[i * 9:(i + 1) * 9] for i in range(8)]


def dhash(image_bytes: bytes) -> int:
    """差分哈希（dHash）。

    做法：缩到 9x8，逐行比较相邻像素大小关系，得到 8x8=64 位。
    相比 aHash，dHash 对整体亮度变化不敏感——状态栏变亮变暗不会误判成「新画面」。
    """
    grid = _to_gray(image_bytes)
    bits = 0
    for row in grid:
        for x in range(8):
            bits = (bits << 1) | (1 if row[x] > row[x + 1] else 0)
    return bits


def hamming(a: int, b: int) -> int:
    """两个哈希的差异位数。"""
    return bin(a ^ b).count("1")


def is_duplicate(new_hash: int, prev_hash: Optional[int],
                 cfg: Config = DEFAULT_CONFIG) -> bool:
    """这一屏和上一屏是不是基本同一屏。"""
    if prev_hash is None:
        return False
    return hamming(new_hash, prev_hash) <= cfg.same_bits


def is_blank(image_bytes: bytes, cfg: Config = DEFAULT_CONFIG) -> tuple[bool, float, float]:
    """空白屏判定（息屏 / 纯色 / 全白）。

    返回 (is_blank, mean, std)。
    黑屏时 OCR 输出 0 段是**正常现象**，不能判为采集失败——早期版本把它
    当错误处理，日志里全是不存在的「OCR 失败」。
    """
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(image_bytes)).convert("L").resize((48, 48))
        px = list(im.getdata())
        n = len(px)
        mean = sum(px) / n
        var = sum((p - mean) ** 2 for p in px) / n
        std = var ** 0.5
        return (mean < cfg.blank_mean or std < cfg.blank_std), mean, std
    except Exception:
        return False, -1.0, -1.0


class Deduper:
    """按场景记忆「最后一屏」，供循环里反复调用。"""

    def __init__(self, cfg: Config = DEFAULT_CONFIG):
        self.cfg = cfg
        self._last_px_hash: Optional[int] = None
        self._last_norm: Optional[str] = None

    def seen_pixels(self, image_bytes: bytes) -> tuple[bool, int]:
        """像素层去重：返回 (是否重复, 本次哈希)。"""
        h = dhash(image_bytes)
        dup = is_duplicate(h, self._last_px_hash, self.cfg)
        self._last_px_hash = h
        return dup, h

    def seen_text(self, normalized: str) -> bool:
        """文本层去重：归一化后与上次完全一致即视为重复。"""
        dup = normalized == self._last_norm
        self._last_norm = normalized
        return dup

    def reset(self) -> None:
        self._last_px_hash = None
        self._last_norm = None


def dedup_lines(lines: Sequence[str]) -> list[str]:
    """同一屏内的完全重复行只保留第一次出现（保序）。"""
    seen: set[str] = set()
    out: list[str] = []
    for l in lines:
        if l in seen:
            continue
        seen.add(l)
        out.append(l)
    return out
