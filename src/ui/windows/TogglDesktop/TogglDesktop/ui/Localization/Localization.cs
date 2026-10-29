using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Windows;

namespace TogglDesktop
{
    /// <summary>
    /// 界面语言选项。<see cref="DisplayName"/> 用该语言自己的写法，
    /// 这样在切换到该语言之前用户也能认出它。
    /// </summary>
    public sealed class LanguageOption
    {
        public string Code { get; }
        public string DisplayName { get; }

        public LanguageOption(string code, string displayName)
        {
            this.Code = code;
            this.DisplayName = displayName;
        }

        public override string ToString() => this.DisplayName;
    }

    /// <summary>
    /// 运行时切换界面语言。
    ///
    /// 做法：把文案从 XAML 里抽到 <c>ui/Resources/Localization/Strings*.xaml</c>，
    /// XAML 侧统一用 <c>{DynamicResource s_xxx}</c> 引用。
    ///
    /// 英文字典（Strings.xaml）**常驻**在 MergedDictionaries 里充当回落，
    /// 其它语言的字典叠在它上面 —— MergedDictionaries 里后加载的优先级更高，
    /// 所以只要中文字典缺了某个 key，就会自动回落到英文，不会显示空白。
    /// </summary>
    public static class Localization
    {
        public const string English = "en";
        public const string ChineseSimplified = "zh-CN";

        public static readonly IReadOnlyList<LanguageOption> SupportedLanguages =
            new[]
            {
                new LanguageOption(English, "English"),
                new LanguageOption(ChineseSimplified, "简体中文"),
            };

        private const string DictionaryPath = "ui/Resources/Localization/Strings";
        private const string SettingsFileName = "ui-language.txt";

        private static ResourceDictionary fallbackDictionary;   // 英文，常驻
        private static ResourceDictionary overlayDictionary;    // 非英文时才加载

        /// <summary>当前语言代码，例如 "en" / "zh-CN"</summary>
        public static string CurrentLanguage { get; private set; } = English;

        /// <summary>语言变更后触发。需要重建内容的窗口可以监听它。</summary>
        public static event EventHandler LanguageChanged;

        public static bool IsChinese => CurrentLanguage == ChineseSimplified;

        /// <summary>
        /// 应用启动时调用一次：加载上次保存的语言（没有就用英文）。
        /// </summary>
        public static void Initialize(Application app)
        {
            if (app == null)
                return;

            // 英文永远先加载并留在集合里，作为回落层
            fallbackDictionary = loadDictionary(English);
            if (fallbackDictionary != null)
                app.Resources.MergedDictionaries.Add(fallbackDictionary);

            apply(loadSavedLanguage(), app);
        }

        /// <summary>
        /// 切换到指定语言。保存偏好并立即刷新所有 DynamicResource。
        /// </summary>
        public static void SetLanguage(string code)
        {
            var app = Application.Current;
            if (app == null)
                return;

            apply(code, app);
            save(code);
        }

        /// <summary>
        /// C# 代码里取文案。查不到就回落到英文，再查不到就返回 key 本身，
        /// 保证界面上永远不会出现空白。
        /// </summary>
        public static string GetString(string key)
        {
            var app = Application.Current;
            if (app != null)
            {
                // 必须用 TryFindResource：ResourceDictionary.Contains 只查字典自身，
                // 不会递归查 MergedDictionaries，用它会让 C# 侧永远取到英文。
                if (app.TryFindResource(key) is string found)
                    return found;
            }

            return fallback(key);
        }

        private static string fallback(string key)
        {
            if (fallbackDictionary != null && fallbackDictionary.Contains(key)
                && fallbackDictionary[key] is string en)
                return en;

            // 最后一层：纯 C# 的英文表。
            // C# 里有些文案写在静态字段初始化器中，可能在 Application 建好之前就求值，
            // 那时上面两层都还没有 —— 用它兜底，界面上才不会出现 "s_xxx" 这种 key 名。
            if (LocalizationFallback.English.TryGetValue(key, out var text))
                return text;

            return key;
        }

        // ------------------------------------------------------------------ 内部

        private static void apply(string code, Application app)
        {
            if (!isSupported(code))
                code = English;

            var merged = app.Resources.MergedDictionaries;

            if (overlayDictionary != null)
            {
                merged.Remove(overlayDictionary);
                overlayDictionary = null;
            }

            if (code != English)
            {
                var dict = loadDictionary(code);
                if (dict != null)
                {
                    // 后加入的优先级更高，所以这层会覆盖英文的同名 key
                    merged.Add(dict);
                    overlayDictionary = dict;
                }
                else
                {
                    code = English;      // 字典缺失，退回英文
                }
            }

            CurrentLanguage = code;
            setUiCulture(code);

            LanguageChanged?.Invoke(null, EventArgs.Empty);
        }

        private static ResourceDictionary loadDictionary(string code)
        {
            var suffix = code == English ? "" : "." + code;
            try
            {
                return new ResourceDictionary
                {
                    Source = new Uri(DictionaryPath + suffix + ".xaml",
                                     UriKind.Relative)
                };
            }
            catch (Exception)
            {
                // 字典缺失不应让应用起不来
                return null;
            }
        }

        private static void setUiCulture(string code)
        {
            try
            {
                var culture = new CultureInfo(code);
                System.Threading.Thread.CurrentThread.CurrentUICulture = culture;
                CultureInfo.DefaultThreadCurrentUICulture = culture;
            }
            catch (CultureNotFoundException)
            {
            }
        }

        private static bool isSupported(string code)
        {
            foreach (var l in SupportedLanguages)
            {
                if (string.Equals(l.Code, code, StringComparison.OrdinalIgnoreCase))
                    return true;
            }
            return false;
        }

        // ------------------------------------------------------- 偏好持久化
        // 存成普通文本文件，放在 Toggl 自己的可写目录里。
        // 不塞进 Toggl 云端设置，因为语言是本机 UI 偏好，不该跟着账号同步。

        private static string settingsPath()
        {
            var dir = Toggl.WritableAppDirPath;
            return string.IsNullOrEmpty(dir)
                ? null
                : Path.Combine(dir, SettingsFileName);
        }

        private static string loadSavedLanguage()
        {
            try
            {
                var path = settingsPath();
                if (path != null && File.Exists(path))
                {
                    var code = File.ReadAllText(path).Trim();
                    if (isSupported(code))
                        return code;
                }
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
            return English;
        }

        private static void save(string code)
        {
            try
            {
                var path = settingsPath();
                if (path == null)
                    return;
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                File.WriteAllText(path, code);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }
}
