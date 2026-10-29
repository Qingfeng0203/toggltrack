using System;
using System.Collections.Generic;
using System.Reactive.Linq;
using System.Windows;
using System.Windows.Input;
using MahApps.Metro.Controls;
using ReactiveUI;
using ReactiveUI.Fody.Helpers;
using ReactiveUI.Validation.Extensions;
using ReactiveUI.Validation.Helpers;
using ValidationHelper = ReactiveUI.Validation.Helpers.ValidationHelper;
using static TogglDesktop.MessageBox;
using DynamicData.Binding;

namespace TogglDesktop.ViewModels
{
    public class PreferencesWindowViewModel : ReactiveValidationObject<PreferencesWindowViewModel>
    {
        private readonly ShowMessageBoxDelegate _showMessageBox;
        private readonly Action _closePreferencesWindow;

        private readonly Dictionary<HotKey, string> _knownShortcuts =
            new Dictionary<HotKey, string>
            {
                { new HotKey(Key.N, ModifierKeys.Control), Localization.GetString("s_new_time_entry") },
                { new HotKey(Key.O, ModifierKeys.Control), Localization.GetString("s_continue_last_entry") },
                { new HotKey(Key.S, ModifierKeys.Control), Localization.GetString("s_stop_time_entry") },
                { new HotKey(Key.W, ModifierKeys.Control), Localization.GetString("s_hide_toggl_track") },
                { new HotKey(Key.R, ModifierKeys.Control), Localization.GetString("s_sync") },
                { new HotKey(Key.E, ModifierKeys.Control), Localization.GetString("s_edit_time_entry") },
                { new HotKey(Key.D, ModifierKeys.Control), Localization.GetString("s_toggle_manual_mode") },
                { new HotKey(Key.V, ModifierKeys.Control), Localization.GetString("s_new_time_entry_from_clipboard") },
            };

        // 原来是 const，但文案改成本地化查表后必须是运行期求值，故改为 static readonly
        private static readonly string ShowHideTogglDescription = Localization.GetString("s_show_hide_toggl_track");
        private static readonly string ContinueStopTimerDescription = Localization.GetString("s_continue_stop_timer");

        private HotKey _continueStopTimerSaved;
        private HotKey _showHideTogglSaved;
        private String _proxyHostSaved;

        private readonly ValidationHelper _showHideTogglValidation;
        private readonly ValidationHelper _continueStopTimerValidation;
        private readonly ValidationHelper _proxyHostValidation;

        public PreferencesWindowViewModel(ShowMessageBoxDelegate showMessageBox, Action closePreferencesWindow)
        {
            _showMessageBox = showMessageBox;
            _closePreferencesWindow = closePreferencesWindow;
            var isLoggedIn = Observable.FromEvent<Toggl.DisplayLogin, bool>(
                onNext => (open, userId) => { onNext(userId != 0); },
                x => Toggl.OnLogin += x,
                x => Toggl.OnLogin -= x);
            ClearCacheCommand = ReactiveCommand.Create(ClearCache, isLoggedIn.ObserveOnDispatcher());

            this.WhenAnyValue(x => x.ShowHideToggl)
                .Buffer(2, 1)
                .Subscribe(b => UpdateKnownShortcuts(b[0], b[1], ShowHideTogglDescription));
            this.WhenAnyValue(x => x.ContinueStopTimer)
                .Buffer(2, 1)
                .Subscribe(b => UpdateKnownShortcuts(b[0], b[1], ContinueStopTimerDescription));

            _showHideTogglValidation = this.ValidationRule(
                vm => vm.ShowHideToggl,
                hotKey => IsHotKeyValid(hotKey, ShowHideTogglDescription),
                hotKey => $"This shortcut is already taken by {_knownShortcuts[hotKey]}");
            _continueStopTimerValidation = this.ValidationRule(
                vm => vm.ContinueStopTimer,
                hotKey => IsHotKeyValid(hotKey, ContinueStopTimerDescription),
                hotKey => $"This shortcut is already taken by {_knownShortcuts[hotKey]}");
            _proxyHostValidation = this.ValidationRule(
                x => x.ProxyHost,
                proxyHost => Uri.CheckHostName(proxyHost) != UriHostNameType.Unknown,
                Localization.GetString("s_please_enter_a_valid_host"));
            Toggl.OnDisplayTimelineUI += isEnabled => IsTimelineViewEnabled = isEnabled;
        }

        public ICommand ClearCacheCommand { get; }

        [Reactive]
        public HotKey ShowHideToggl { get; set; }
        public HotKey GetShowHideTogglIfChanged() =>
            !object.Equals(ShowHideToggl, _showHideTogglSaved) ? (ShowHideToggl ?? new HotKey(Key.None)) : null;

        [Reactive]
        public HotKey ContinueStopTimer { get; set; }
        public HotKey GetContinueStopTimerIfChanged() =>
            !object.Equals(ContinueStopTimer, _continueStopTimerSaved) ? (ContinueStopTimer ?? new HotKey(Key.None)) : null;

        [Reactive]
        public string ProxyHost { get; set; }

        [Reactive]
        public bool IsTimelineViewEnabled { get; private set; }

        [Reactive]
        public bool IsIgnoreCertEnabled { get; set; }

        public void ResetRecordedShortcuts()
        {
            ShowHideToggl = _showHideTogglSaved;
            ContinueStopTimer = _continueStopTimerSaved;
            ProxyHost = _proxyHostSaved;
        }

        public void LoadShortcutsFromSettings()
        {
            _showHideTogglSaved = LoadHotKey(Toggl.GetKeyShow, Toggl.GetKeyModifierShow);
            ShowHideToggl = _showHideTogglSaved;
            _continueStopTimerSaved = LoadHotKey(Toggl.GetKeyStart, Toggl.GetKeyModifierStart);
            ContinueStopTimer = _continueStopTimerSaved;
        }

        public void SetSavedProxyHost(String savedProxyHost)
        {
            _proxyHostSaved = savedProxyHost;
        }

        public void ResetPropsWithErrorsToPreviousValues()
        {
            if (!_showHideTogglValidation.IsValid) ShowHideToggl = _showHideTogglSaved;
            if (!_continueStopTimerValidation.IsValid) ContinueStopTimer = _continueStopTimerSaved;
            if (!_proxyHostValidation.IsValid) ProxyHost = _proxyHostSaved;
        }

        private bool IsHotKeyValid(HotKey hotKey, string hotKeyDescription)
        {
            return hotKey.IsNullOrNone() || _knownShortcuts[hotKey] == hotKeyDescription;
        }

        private void UpdateKnownShortcuts(HotKey previousValue, HotKey newValue, string hotKeyDescription)
        {
            if (!previousValue.IsNullOrNone() && _knownShortcuts.ContainsKey(previousValue))
            {
                if (_knownShortcuts[previousValue] == hotKeyDescription)
                {
                    _knownShortcuts.Remove(previousValue);
                }
            }
            if (!newValue.IsNullOrNone())
            {
                if (!_knownShortcuts.ContainsKey(newValue))
                {
                    _knownShortcuts.Add(newValue, hotKeyDescription);
                }
            }
        }

        private static HotKey LoadHotKey(Func<Key> getKey, Func<ModifierKeys> getModifiers)
        {
            var key = getKey();
            return new HotKey(key, key == Key.None ? ModifierKeys.None : getModifiers());
        }

        private void ClearCache()
        {
            var result = _showMessageBox(
                "This will remove your Toggl user data from this PC and log you out of the Toggl Track app. " +
                "Any unsynced data will be lost.\n\nDo you want to continue?", Localization.GetString("s_clear_cache"),
                MessageBoxButton.OKCancel, Localization.GetString("s_clear_cache"));

            if (result == MessageBoxResult.OK)
            {
                Toggl.ClearCache();
                _closePreferencesWindow();
            }
        }
    }
}