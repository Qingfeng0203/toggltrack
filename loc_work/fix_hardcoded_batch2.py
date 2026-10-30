"""补齐第二批硬编码英文的汉化：新增词条 + 替换 XAML 引用。

保持 BOM + CRLF 字节级兼容。
"""
import io
import re

BASE = "src/ui/windows/TogglDesktop/TogglDesktop/"

# 新词条：key -> (英文, 中文)
NEW_ENTRIES = {
    "s_email_address": ("Email address", "邮箱地址"),
    "s_work_email_address": ("Work email address", "工作邮箱地址"),
    "s_description": ("Description", "描述"),
    "s_please_specify_topic": ("Please specify the topic", "请选择主题"),
    "s_record_shortcut": ("Record shortcut", "录制快捷键"),
    "s_no_project_selected": ("No project selected", "未选择项目"),
    "s_timeline_data_hint": (
        "You'll have a timeline of all activity on your computer with a "
        "breakdown of time spent on applications and websites. Only you can "
        "access this data.",
        "将记录你电脑上的所有活动，并按应用和网站统计时间分布。这些数据只有你自己能查看。",
    ),
    "s_clear_local_data_warning": (
        "This will clear all Toggl local data and log you out. To avoid "
        "losing any time entries, please make sure they are successfully synced.",
        "此操作将清空所有 Toggl 本地数据并退出登录。为避免丢失时间记录，请先确认它们已成功同步。",
    ),
    "s_autotracker_hint": (
        "Autotracker helps to make time tracking faster by triggering "
        "customized suggestions. When a selected app is open in the "
        "foreground, you'll get one of the prefilled suggestions.",
        "自动跟踪助手能在你使用指定应用时给出预置建议，让计时更省事。"
        "当所选应用位于前台时，你会收到相应的建议。",
    ),
    "s_mirror_watermark": ("http://10.104.2.133:8080", "http://服务器地址:8080"),
}

# 复用已有词条：文件 -> [(原文, 词条key)]
REUSE = {
    "ui/controls/AutotrackerSettings.xaml": [
        ("Keyword", "s_keyword"),
        ("Select project", "s_select_project"),
    ],
    "ui/views/EditView.xaml": [
        ("Description", "s_description"),
        ("Select project", "s_select_project"),
        ("Project name", "s_project_name"),
        ("No client", "s_no_client"),
    ],
    "ui/views/LoginView.xaml": [
        ("Email address", "s_email_address"),
        ("Password", "s_password"),
        ("Select country", "s_please_select_country"),
    ],
    "ui/views/SSOLoginView.xaml": [
        ("Work email address", "s_work_email_address"),
    ],
    "ui/windows/FeedbackWindow.xaml": [
        ("Please specify the topic", "s_please_specify_topic"),
    ],
    "ui/windows/PreferencesWindow.xaml": [
        ("Record shortcut", "s_record_shortcut"),
        ("No project selected", "s_no_project_selected"),
        ("You'll have a timeline of all activity on your computer with a "
         "breakdown of time spent on applications and websites. Only you can "
         "access this data.", "s_timeline_data_hint"),
        ("This will clear all Toggl local data and log you out. To avoid "
         "losing any time entries, please make sure they are successfully "
         "synced.", "s_clear_local_data_warning"),
        ("Autotracker helps to make time tracking faster by triggering "
         "customized suggestions. When a selected app is open in the "
         "foreground, you'll get one of the prefilled suggestions.",
         "s_autotracker_hint"),
        ("http://10.104.2.133:8080", "s_mirror_watermark"),
    ],
}

EN_FILE = BASE + "ui/Resources/Localization/Strings.xaml"
ZH_FILE = BASE + "ui/Resources/Localization/Strings.zh-CN.xaml"


def read(path):
    return io.open(path, "r", encoding="utf-8-sig", newline="").read()


def write(path, text):
    # 保留原文件的 BOM 与换行风格
    io.open(path, "w", encoding="utf-8-sig", newline="").write(text)


def existing_keys(text):
    return set(re.findall(r'x:Key="(s_[A-Za-z0-9_]+)"', text))


def add_entries(path, lang_index):
    text = read(path)
    keys = existing_keys(text)
    additions = []
    for key, pair in NEW_ENTRIES.items():
        if key in keys:
            print("  已存在，跳过:", key)
            continue
        value = pair[lang_index]
        additions.append(
            '    <system:String x:Key="%s">%s</system:String>' % (key, value))
    if not additions:
        return
    # 插到最后一个词条之后（</ResourceDictionary> 前）
    idx = text.rindex("</ResourceDictionary>")
    # 找它前面那一行的缩进
    block = "\n".join(additions) + "\n"
    text = text[:idx] + block + text[idx:]
    write(path, text)
    print("  +", len(additions), "条 ->", path)


def replace_refs(path, pairs):
    text = read(path)
    n = 0
    for original, key in pairs:
        for attr in ("Text", "Content", "Watermark", "Header"):
            old = '%s="%s"' % (attr, original)
            new = '%s="{DynamicResource %s}"' % (attr, key)
            if old in text:
                text = text.replace(old, new)
                n += text.count(new)
                break
        else:
            print("  !! 未找到:", path, attr, original[:50])
    write(path, text)
    print("  替换 %d 处 -> %s" % (n, path))


def main():
    print("== 新增词条 ==")
    add_entries(EN_FILE, 0)
    add_entries(ZH_FILE, 1)

    print("== 替换引用 ==")
    for rel, pairs in REUSE.items():
        replace_refs(BASE + rel, pairs)


if __name__ == "__main__":
    main()
