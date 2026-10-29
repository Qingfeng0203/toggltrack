using System;
using System.Linq;
using System.Windows;

namespace TogglDesktop
{
partial class App
{
    public App()
    {
        InitializeComponent();
    }

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // 必须在建窗口之前：窗口里的 {DynamicResource} 要能立刻解析到
        Localization.Initialize(this);

        var mainWindow = new MainWindow();
        var startMinimized = Environment.GetCommandLineArgs().Contains("--minimize");
        mainWindow.Show();
        if (startMinimized)
        {
            mainWindow.Hide();
        }
    }
}
}