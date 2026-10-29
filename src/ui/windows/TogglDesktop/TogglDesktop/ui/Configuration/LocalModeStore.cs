using System;
using System.IO;

namespace TogglDesktop
{
    /// <summary>
    /// 本地模式（免登录）开关的本地持久化。
    ///
    /// 打开后应用启动时不再要求账号密码，直接在本地数据库上工作：
    /// 同步、时间线上传、websocket、更新检查、站内信全部关闭，
    /// 不会向任何服务器发出请求（镜像推送除外，见 MirrorUrlStore）。
    ///
    /// 文件位置：%LOCALAPPDATA%\TogglDesktop\local-mode.txt
    /// 文件内容：1 = 本地模式，0 = 正常登录模式。
    /// 文件不存在时默认按本地模式处理（这是本分支的默认行为）。
    /// </summary>
    public static class LocalModeStore
    {
        private const string FileName = "local-mode.txt";

        private static bool? overrideValue;

        /// <summary>
        /// 命令行是否强制指定了模式。必须在任何请求发出前调用，
        /// 运行时切换只影响下次启动。
        /// </summary>
        public static void ApplyCommandLine(string[] args)
        {
            if (args == null)
                return;

            foreach (var arg in args)
            {
                if (arg == "--online" || arg == "--no-local-mode")
                {
                    overrideValue = false;
                    return;
                }
                if (arg == "--local-mode")
                {
                    overrideValue = true;
                    return;
                }
            }
        }

        /// <summary>当前是否使用本地模式。</summary>
        public static bool IsEnabled
        {
            get
            {
                if (overrideValue.HasValue)
                    return overrideValue.Value;

                try
                {
                    var path = settingsPath();
                    if (path != null && File.Exists(path))
                    {
                        var text = File.ReadAllText(path).Trim();
                        if (text.Length > 0)
                            return text != "0";
                    }
                }
                catch (IOException)
                {
                }
                catch (UnauthorizedAccessException)
                {
                }

                // 默认开启：这个版本的目标就是免登录可用
                return true;
            }
        }

        /// <summary>持久化开关；下次启动生效。</summary>
        public static void SetEnabled(bool enabled)
        {
            try
            {
                var path = settingsPath();
                if (path == null)
                    return;

                Directory.CreateDirectory(Path.GetDirectoryName(path));
                File.WriteAllText(path, enabled ? "1" : "0");
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }

        private static string settingsPath()
        {
            var dir = Toggl.WritableAppDirPath;
            return string.IsNullOrEmpty(dir) ? null : Path.Combine(dir, FileName);
        }
    }
}
