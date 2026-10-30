"""扫描 XAML 中所有硬编码的英文可见文本。

可见文本出现在这些位置：
- 元素内容（<TextBlock>英文</TextBlock>）
- Text= / Content= / Watermark= / Header= / Title= / Label= / Tag= 属性
排除：绑定、资源引用、纯数字、单字符、纯符号、x:Uid 等。
"""
import glob
import re
import sys

PATTERNS = [
    # 属性位置: Text="xxx" 等
    ("attr", re.compile(
        r'(?:Text|Content|Watermark|Header|Title|Label|ToolTip|AutomationProperties\.Name)'
        r'="([^"{}][^"]*)"')),
    # 元素内容: <TextBlock ...>text</TextBlock> 等（简化：抓 >英文< 形式）
    ("content", re.compile(
        r'>\s*([A-Za-z][A-Za-z0-9 ,.\'!?%()/-]{3,})\s*</')),
]

# 忽略：XAML 内部语法、数值、格式占位等
SKIP_EXACT = {
    "x:Name", "xmlns", "*", "...", "-", "—", "0", "1", "sso",
}
SKIP_RE = [
    re.compile(r"^\d+([.,]\d+)*$"),                # 数字
    re.compile(r"^[{}%#()\[\]:;,.*-]+$"),          # 符号
    re.compile(r"^(True|False|Null)$"),            # 枚举字面量（绑定用）
    re.compile(r"^[A-Za-z]:\\"),                   # 路径
    re.compile(r"^clr-namespace"),                 # 命名空间
    re.compile(r"^\s*$"),                          # 空白
    re.compile(r"^[A-Z]{2,}([_][A-Z0-9]+)*$"),     # 常量命名
    re.compile(r"^(png|jpg|ico)$"),
    re.compile(r"[<>{}],?"),                       # 含残留标记
]


def is_user_visible(text):
    t = text.strip()
    if not t or t in SKIP_EXACT:
        return False
    for rx in SKIP_RE:
        if rx.match(t):
            return False
    # 至少包含一个小写字母 + 长度 >= 3 才像人类语言
    if not re.search(r"[a-z]{2,}", t):
        return False
    # 排除看似绑定路径/资源键的
    if re.match(r"^[A-Za-z_][A-Za-z0-9_.]*$", t) and "." in t and " " not in t:
        return False
    return True


def scan():
    hits = {}
    for path in sorted(glob.glob("**/*.xaml", recursive=True)):
        if path.endswith("Strings.xaml") or path.endswith("Strings.zh-CN.xaml"):
            continue
        try:
            with open(path, encoding="utf-8-sig") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            print("读取失败", path, exc, file=sys.stderr)
            continue
        lines = text.split("\n")
        for kind, rx in PATTERNS:
            for i, ln in enumerate(lines, 1):
                for m in rx.finditer(ln):
                    val = m.group(1)
                    if is_user_visible(val):
                        hits.setdefault(path, []).append(
                            (i, kind, val.strip()[:120]))
    return hits


def main():
    hits = scan()
    total = 0
    for path, items in sorted(hits.items()):
        print("=== %s (%d) ===" % (path, len(items)))
        for i, kind, val in items:
            print("  %4d %-7s %s" % (i, kind, val))
            total += 1
    print("\n合计疑似硬编码文本: %d 处，涉及 %d 个文件" % (total, len(hits)))


if __name__ == "__main__":
    main()
