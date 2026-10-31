"""四道闸门的回归测试。

这三条断言是踩过坑才写出来的，改动 accumulate.py 前后必须跑：

  1. 同一聊天窗口滚动 → ROLL（能拼）
  2. 聊天页和文章页之间重合 6 行 → NEW（不许拼，这是当年数据被污染的那次）
  3. 文章页滚动，页头变了但类型相同 → ROLL（标题滚出屏幕不算换页）
"""

import pytest

from scrollbreaker import Accumulator, Frame, Mode
from scrollbreaker.pagetype import page_type

CHAT_A = ["张三: 明天那批货先别发", "李四: 为什么", "张三: 客户改图纸了"]
CHAT_B = ["李四: 为什么", "张三: 客户改图纸了", "李四: 那我去停一下"]
CHAT_OTHER = ["王五: 好的", "赵六: 正常", "王五: 收到"]

ARTICLE_1 = ["如何理解滚动采集", "很多人以为截图就是采集", "其实难点在分页", "+关注 写留言 阅读原文"]
ARTICLE_2 = ["其实难点在分页", "两屏重合不代表同页", "要判类型和页头", "+关注 写留言 阅读原文"]
ARTICLE_3 = ["要判类型和页头", "四道闸门全过才拼", "否则另起一条", "+关注 写留言 阅读原文"]


def test_page_type_basic():
    assert page_type(CHAT_A) == "chat"
    assert page_type(ARTICLE_1) == "article"
    # 文章特征 + 聊天特征同屏 = 切页中间态
    assert page_type(ARTICLE_1 + ["张三: 在吗", "李四: 在"]) == "mixed"


def test_same_chat_rolls():
    acc = Accumulator()
    m1 = acc.push(Frame(CHAT_A, ts=1000))
    assert m1.mode is Mode.NEW
    m2 = acc.push(Frame(CHAT_B, ts=1030))
    assert m2.mode is Mode.ROLL, "同一聊天窗口滚动必须能拼"
    assert "明天那批货先别发" in m2.text
    assert m2.overlap >= 2


def test_different_chat_not_merged_even_with_overlap():
    """不同会话，即使有重合行也必须断开。"""
    acc = Accumulator()
    acc.push(Frame(CHAT_A, ts=1000))
    m2 = acc.push(Frame(CHAT_OTHER, ts=1030))
    assert m2.mode is Mode.NEW


def test_article_to_chat_never_merged():
    """核心回归：文章页与聊天页重合 6 行，仍必须判 NEW。

    历史事故：旧逻辑只看重合行数，把公众号文章和车间聊天拼成了一条。
    """
    article = [
        "正常", "好的", "收到", "在看", "+关注",
        "这是文章正文第一段", "这是文章正文第二段",
    ]
    chat = ["正常", "好的", "收到", "张三: 机台停一下", "李四: 马上"]
    acc = Accumulator()
    m1 = acc.push(Frame(article, ts=1000))
    assert m1.page == "article"
    m2 = acc.push(Frame(chat, ts=1030))
    assert m2.overlap >= 2, "本用例前提：两屏确实有重合行"
    assert m2.mode is Mode.NEW, "类型不同绝不许拼"


def test_article_scroll_ignores_anchor():
    """文章滚动时首行（标题）会变，但类型相同 → 仍应拼。"""
    acc = Accumulator()
    m1 = acc.push(Frame(ARTICLE_1, ts=1000))
    m2 = acc.push(Frame(ARTICLE_2, ts=1030))
    assert m2.mode is Mode.ROLL
    assert "很多人以为截图就是采集" in m2.text


def test_window_expired_starts_new():
    acc = Accumulator()
    acc.push(Frame(CHAT_A, ts=1000))
    m2 = acc.push(Frame(CHAT_B, ts=1000 + 181))
    assert m2.mode is Mode.NEW, "超过时间窗应另起一条"


def test_article_banner_stripped():
    """文章页顶部的消息横幅不能被拼进正文。"""
    banner = ["张三", "正常", "在吗"]
    acc = Accumulator()
    acc.push(Frame(ARTICLE_1, ts=1000))
    m = acc.push(
        Frame(banner + ["其实难点在分页，两屏重合不代表同页", "要判类型和页头才能拼", "+关注 写留言"], ts=1030)
    )
    assert "在吗" not in m.text


def test_mixed_never_accumulates():
    mixed = ARTICLE_1 + ["张三: 在吗", "李四: 在"]
    acc = Accumulator()
    m1 = acc.push(Frame(mixed, ts=1000))
    assert m1.page == "mixed"
    m2 = acc.push(Frame(ARTICLE_2, ts=1030))
    assert m2.mode is Mode.NEW, "mixed 屏不能被当作累积起点"


def test_max_lines_truncated():
    acc = Accumulator(cfg=__import__("scrollbreaker").Config(max_lines=5))
    big = [f"line {i}" for i in range(12)]
    acc.push(Frame(big, ts=1000))
    m = acc.push(Frame(big[8:] + ["line 12"], ts=1030))
    assert m.line_count <= 5
