"""scrollbreaker —— 把滚动的屏幕，切成能读的页。

核心问题：手机/电脑上读长内容时，一屏只能看到一小段。连续截屏会有三种噪声：
  1. 屏幕没动，重复截到同一屏（浪费 token）
  2. 内容滚动了，前后两屏有一段重叠（直接拼会重复）
  3. **换页面了**，但上一屏和这一屏恰好有相同的一行（直接拼会把两件事糊成一件）

前两个好解决，第三个才是真正会毁掉数据的问题。scrollbreaker 用四道闸门判定
「这两屏到底是不是同一页」，只有全过才拼，否则另起一条。
"""

from .config import Config, DEFAULT_CONFIG
from .pagetype import page_type, head_anchor, body_lines
from .accumulate import Accumulator, Frame, Merge, Mode
from .dedup import dhash, is_duplicate, is_blank

__all__ = [
    "Config",
    "DEFAULT_CONFIG",
    "page_type",
    "head_anchor",
    "body_lines",
    "Accumulator",
    "Frame",
    "Merge",
    "Mode",
    "dhash",
    "is_duplicate",
    "is_blank",
]

__version__ = "0.1.0"
