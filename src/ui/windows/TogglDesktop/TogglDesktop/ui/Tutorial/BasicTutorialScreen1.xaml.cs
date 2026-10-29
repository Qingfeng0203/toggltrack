
using System.Windows;

namespace TogglDesktop.Tutorial
{
    public partial class BasicTutorialScreen1
    {
        public BasicTutorialScreen1()
        {
            this.InitializeComponent();
        }

        protected override void initialise()
        {
            this.fillDummies();

            Toggl.Stop();
            Toggl.SetManualMode(false);
            Toggl.ViewTimeEntryList();
        }

        private void fillDummies()
        {
            // 教程页展示的是示例数据，也走本地化，否则中文界面里会夹着英文示例
            this.dayHeaderDummy.DisplayDummy(Localization.GetString("s_today"));
            this.cellDummy0.Display(new Toggl.TogglTimeEntryView
            {
                Description = Localization.GetString("s_meeting"),
                ProjectLabel = Localization.GetString("s_internal"),
                Color = "#6ac4fc",
            });
            this.cellDummy1.Display(new Toggl.TogglTimeEntryView
            {
                Description = Localization.GetString("s_research_for_presentation"),
                ProjectLabel = Localization.GetString("s_consulting"),
                ClientLabel = Localization.GetString("s_toy_factory"),
                Color = "#d086ac",
            });
            this.cellDummy2.Display(new Toggl.TogglTimeEntryView
            {
                Description = Localization.GetString("s_code_review"),
                ProjectLabel = Localization.GetString("s_frontend"),
                ClientLabel = Localization.GetString("s_toy_factory"),
                Color = "#69c600",
            });
        }

        protected override void cleanup()
        {
        }

        private void nextButtonClick(object sender, RoutedEventArgs e)
        {
            this.activateScreen<BasicTutorialScreen2>();
        }
    }
}
