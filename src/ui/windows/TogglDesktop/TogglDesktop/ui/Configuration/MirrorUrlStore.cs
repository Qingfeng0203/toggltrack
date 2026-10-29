using System;
using System.IO;

namespace TogglDesktop
{
    /// <summary>
    /// 时间记录镜像推送地址的本地持久化。
    ///
    /// 为什么不存进 Toggl 云端设置：镜像地址是本机旁路备份的目标，
    /// 跟着账号同步到云端没有意义；而且一旦填错就连不上，也就没法再从云端读回来。
    ///
    /// 文件位置：%LOCALAPPDATA%\TogglDesktop\mirror-url.txt
    /// 文件内容：一行纯文本 URL；文件不存在或为空表示不启用镜像推送。
    /// </summary>
    public static class MirrorUrlStore
    {
        private const string FileName = "mirror-url.txt";

        /// <summary>读取已保存的服务器地址，没有配置时返回空字符串。</summary>
        public static string Load()
        {
            try
            {
                var path = settingsPath();
                if (path != null && File.Exists(path))
                {
                    return Normalize(File.ReadAllText(path));
                }
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
            return string.Empty;
        }

        /// <summary>保存服务器地址；传空字符串表示恢复默认（删除配置文件）。</summary>
        public static void Save(string url)
        {
            try
            {
                var path = settingsPath();
                if (path == null)
                    return;

                var normalized = Normalize(url);
                if (normalized.Length == 0)
                {
                    if (File.Exists(path))
                        File.Delete(path);
                    return;
                }

                Directory.CreateDirectory(Path.GetDirectoryName(path));
                File.WriteAllText(path, normalized);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }

        /// <summary>
        /// 规范化：去掉首尾空白和末尾斜杠；没写协议时补 https://。
        /// 库端会再规范化一次，这里做是为了让界面上显示的值就是最终生效的值。
        /// </summary>
        public static string Normalize(string url)
        {
            if (string.IsNullOrWhiteSpace(url))
                return string.Empty;

            var value = url.Trim();

            while (value.EndsWith("/", StringComparison.Ordinal))
                value = value.Substring(0, value.Length - 1);

            if (value.Length > 0 && value.IndexOf("://", StringComparison.Ordinal) < 0)
                value = "https://" + value;

            return value;
        }

        /// <summary>
        /// 校验用户输入，返回 null 表示合法，否则返回错误提示。
        /// </summary>
        public static string Validate(string url)
        {
            var value = Normalize(url);
            if (value.Length == 0)
                return null;        // 空 = 使用官方地址，合法

            var zh = Localization.IsChinese;

            if (!Uri.TryCreate(value, UriKind.Absolute, out var uri))
                return zh
                    ? "地址格式不正确，例如 http://10.104.2.133:8080"
                    : "Invalid address, for example http://10.104.2.133:8080";

            if (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps)
                return zh ? "只支持 http:// 或 https://" : "Only http:// and https:// are supported";

            if (string.IsNullOrEmpty(uri.Host))
                return zh ? "地址里缺少主机名" : "The address has no host name";

            return null;
        }

        private static string settingsPath()
        {
            var dir = Toggl.WritableAppDirPath;
            return string.IsNullOrEmpty(dir) ? null : Path.Combine(dir, FileName);
        }
    }
}
