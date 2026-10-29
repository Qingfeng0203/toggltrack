# 修复：内容位置 {DynamicResource} 不会被 WPF 求值，显示为原始文本。
# 只做三类保守转换，属性位置的用法一律不动：
#   A) <Hyperlink ...>{DynamicResource k}</Hyperlink>     -> 内嵌 <Run Text="..."/>
#   B) 纯内容的简单元素（TextBlock/CheckBox/RadioButton/Button/
#      ComboBoxItem/mah:ToggleSwitch）                    -> 改为 Content/Text 属性
#   C) TextBlock 富文本里散落的 {DynamicResource k}        -> <Run Text="..."/>
import re
import sys

BASE = r"D:/Download/toggldesktop-7.5.363/src/ui/windows/TogglDesktop/TogglDesktop"

FILES = [
    "ui/Tutorial/BasicTutorialScreen1.xaml",
    "ui/Tutorial/BasicTutorialScreen2.xaml",
    "ui/Tutorial/BasicTutorialScreen3.xaml",
    "ui/Tutorial/BasicTutorialScreen4.xaml",
    "ui/Tutorial/BasicTutorialScreen5.xaml",
    "ui/Tutorial/BasicTutorialScreen6.xaml",
    "ui/Tutorial/BasicTutorialScreen7.xaml",
    "ui/controls/DaysOfWeekSelector.xaml",
    "ui/views/EditView.xaml",
    "ui/views/LoginView.xaml",
    "ui/views/OverlayView.xaml",
    "ui/views/SSOLoginView.xaml",
    "ui/views/Timeline.xaml",
    "ui/windows/AboutWindow.xaml",
    "ui/windows/PreferencesWindow.xaml",
]

KEY = r"\{DynamicResource\s+(s_[A-Za-z0-9_]+)\}"

# A) Hyperlink 纯内容 -> Run
rule_hyperlink = re.compile(
    r"(<Hyperlink\b[^>]*?>)\s*" + KEY + r"\s*(</Hyperlink>)")

# B) 纯内容简单元素 -> Content/Text 属性（自闭合）
PURE_ELEMENTS = [
    ("TextBlock", "Text"),
    ("CheckBox", "Content"),
    ("RadioButton", "Content"),
    ("Button", "Content"),
    ("ComboBoxItem", "Content"),
    ("mah:ToggleSwitch", "Content"),
]

# C) 富文本里散落的引用 -> Run（跳过属性位置）
rule_loose = re.compile(KEY)


def to_attr(attrs, prop, key):
    # 去掉 attrs 末尾多余的空白，追加属性，自闭合
    return "<%s %s %s=\"{DynamicResource %s}\"/>" % (
        tagname, attrs.strip(), prop, key)


def convert(text, fname):
    n_total = 0

    # A
    def rep_hyperlink(m):
        return "%s<Run Text=\"{DynamicResource %s}\"/>%s" % (
            m.group(1), m.group(2), m.group(3))
    text, n = rule_hyperlink.subn(rep_hyperlink, text)
    n_total += n

    # B
    for tagname, prop in PURE_ELEMENTS:
        pat = re.compile(
            r"<(%s)\b([^>]*?)>\s*" % re.escape(tagname)
            + KEY + r"\s*(</%s>)" % re.escape(tagname))
        def rep_pure(m, prop=prop, tagname=tagname):
            return "<%s%s %s=\"{DynamicResource %s}\"/>" % (
                tagname, m.group(2), prop, m.group(3))
        text, n = pat.subn(rep_pure, text)
        n_total += n

    # C：逐个检查剩余的内容位置引用
    out = []
    last = 0
    for m in rule_loose.finditer(text):
        before = text[:m.start()]
        # 属性位置判定：本行内、引用之前最后一个非空白片段以 =" 结尾
        line_start = before.rfind("\n")
        line_before = before[line_start + 1:].rstrip()
        if line_before.endswith('="'):
            continue  # 属性位置，保留
        out.append(text[last:m.start()])
        out.append('<Run Text="{DynamicResource %s}"/>' % m.group(1))
        last = m.end()
        n_total += 1
    out.append(text[last:])
    text = "".join(out)
    return text, n_total


grand = 0
for f in FILES:
    path = "%s/%s" % (BASE, f)
    raw = open(path, "rb").read()
    crlf = b"\r\n" in raw
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    new, n = convert(text, f)
    if n:
        data = new.encode("utf-8")
        if not new.endswith("\n"):
            pass
        open(path, "wb").write(data)
        print("%-45s %2d 处已修复 (CRLF=%s BOM=%s)" % (f, n, crlf, bom))
        grand += n
    else:
        print("%-45s  0 处" % f)
print("合计: %d 处" % grand)
