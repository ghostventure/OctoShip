using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Text.Json;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Threading;
using Microsoft.Win32;
using Windows.Security.Credentials.UI;

namespace FileToGitHub;

/// <summary>Application-wide privacy shield. This is not a replacement for the Windows screen lock.</summary>
public sealed class AccountSessionLock : IDisposable
{
    private readonly Application _application;
    private readonly string _path;
    private readonly AccountSessionState _state;
    private readonly DispatcherTimer _timer;
    private readonly Dictionary<Window, Shield> _shields = new();
    private readonly SessionNativeWindows _nativeWindows = new();
    private Window? _lockWindow;
    private TextBlock? _status;
    private bool _unlocking, _disposed, _allowClose;
    private bool _windowsAuthenticationRequired = true;
    private DateTimeOffset _retryAfter;
    private DateTimeOffset _lastSaved;
    private Point? _lastMousePosition;
    private TaskCompletionSource<bool>? _unlockCompletion;
    public static AccountSessionLock? Current { get; private set; }
    public bool IsLocked => _windowsAuthenticationRequired && _state.IsLocked;
    public Task WaitUntilUnlockedAsync()
    {
        Check();
        return IsLocked ? (_unlockCompletion ??= new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously)).Task : Task.CompletedTask;
    }
    public string? PersistenceError { get; private set; }
    public AccountSessionLock(Application application, string? statePath = null, bool? requireWindowsAuthentication = null)
    {
        _application = application;
        _path = statePath ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub", "session.json");
        _windowsAuthenticationRequired = requireWindowsAuthentication ?? ReadWindowsAuthenticationPreference();
        _state = AccountSessionState.Load(_path, DateTimeOffset.UtcNow);
        if (!_windowsAuthenticationRequired) _state.ResumeWithoutAuthentication(DateTimeOffset.UtcNow);
        Current = this;
        InputManager.Current.PreProcessInput += OnInput;
        SystemEvents.SessionSwitch += OnSessionSwitch;
        _timer = new DispatcherTimer(DispatcherPriority.Send) { Interval = TimeSpan.FromSeconds(1) };
        _timer.Tick += (_, _) => Check();
        _timer.Start();
        Persist();
    }
    public static void ThrowIfLocked()
    {
        if (Current is { } session)
        {
            if (session._application.Dispatcher.CheckAccess()) session.Check();
            else session._application.Dispatcher.Invoke(session.Check);
            if (session.IsLocked) throw new InvalidOperationException("OctoShip is locked. Unlock the account workspace, then review and retry this operation.");
        }
    }
    public void Check()
    {
        if (_disposed) return;
        var wasLocked = _state.IsLocked;
        if (_windowsAuthenticationRequired) _state.CheckTimeout(DateTimeOffset.UtcNow);
        if (_state.IsLocked)
        {
            if (!wasLocked) Persist();
            ShieldWindows();
            EnsureLockWindow();
            if (!_unlocking) _nativeWindows.HideDialogs(_application.Windows.Cast<Window>()
                .Select(window => new WindowInteropHelper(window).Handle).ToHashSet());
        }
        else
        {
            if (_nativeWindows.HasNewAppInput()) _state.RecordActivity(DateTimeOffset.UtcNow);
            if (DateTimeOffset.UtcNow - _lastSaved >= TimeSpan.FromSeconds(30)) Persist();
        }
    }
    public void Lock()
    {
        _state.Lock(); Persist(); Check();
    }
    public void SetWindowsAuthenticationRequired(bool required)
    {
        if (_windowsAuthenticationRequired == required) return;
        _windowsAuthenticationRequired = required;
        _state.ResumeWithoutAuthentication(DateTimeOffset.UtcNow);
        Persist();
        if (!required) _unlockCompletion?.TrySetResult(true);
        _unlockCompletion = null;
    }
    private static bool ReadWindowsAuthenticationPreference()
    {
        var path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub", "settings.json");
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path));
            var root = document.RootElement;
            return !root.TryGetProperty("requireWindowsAuthentication", out var value)
                || value.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
                || value.GetBoolean();
        }
        catch { return true; }
    }
    private void OnSessionSwitch(object sender, SessionSwitchEventArgs args)
    {
        if (_windowsAuthenticationRequired && args.Reason is (SessionSwitchReason.SessionLock or SessionSwitchReason.SessionLogoff or SessionSwitchReason.RemoteDisconnect))
            _application.Dispatcher.BeginInvoke(new Action(Lock));
    }
    private void OnInput(object sender, PreProcessInputEventArgs args)
    {
        if (_disposed) return;
        Check();
        if (IsLocked) return;
        var input = args.StagingItem.Input;
        if (input is MouseEventArgs mouse)
        {
            var point = mouse.GetPosition(null);
            if (input.RoutedEvent == Mouse.PreviewMouseMoveEvent || input.RoutedEvent == Mouse.MouseMoveEvent)
            { if (_lastMousePosition == point) return; _lastMousePosition = point; }
        }
        if (input is KeyboardEventArgs or MouseEventArgs or TouchEventArgs or StylusEventArgs)
            _state.RecordActivity(DateTimeOffset.UtcNow);
    }
    private void ShieldWindows()
    {
        foreach (Window window in _application.Windows.Cast<Window>().ToArray())
        {
            if (window == _lockWindow || _shields.ContainsKey(window)) continue;
            var original = window.Content;
            var title = window.Title;
            window.Content = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(17, 24, 39)),
                Child = new TextBlock { Text = "OctoShip is locked", Foreground = Brushes.White, FontSize = 24,
                    HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center }
            };
            window.Title = "OctoShip — Locked";
            _shields.Add(window, new Shield(original, title));
            window.Closing += PreventWorkspaceClose;
        }
    }
    private void PreventWorkspaceClose(object? sender, CancelEventArgs args) { if (IsLocked && !_allowClose) args.Cancel = true; }
    private void EnsureLockWindow()
    {
        if (_lockWindow is not null) return;
        var panel = new StackPanel { Margin = new Thickness(28) };
        panel.Children.Add(new TextBlock { Text = "OctoShip is locked", FontSize = 25, Foreground = Brushes.White, Margin = new Thickness(0, 0, 0, 14) });
        panel.Children.Add(new TextBlock { Text = "Your account preferences and prepared work are retained. Unlock with Windows authentication to continue.\n\nOctoShip locks after 30 minutes without activity in the app.", TextWrapping = TextWrapping.Wrap, Foreground = Brushes.White, Margin = new Thickness(0, 0, 0, 16) });
        _status = new TextBlock { TextWrapping = TextWrapping.Wrap, Foreground = Brushes.LightSteelBlue, Margin = new Thickness(0, 0, 0, 12) };
        panel.Children.Add(_status);
        var unlock = new Button { Content = "Unlock with Windows", Padding = new Thickness(14, 9, 14, 9), IsDefault = true };
        AutomationProperties.SetName(unlock, "Unlock OctoShip with Windows authentication");
        unlock.Click += async (_, _) => { unlock.IsEnabled = false; try { await UnlockAsync(); } finally { unlock.IsEnabled = true; } };
        panel.Children.Add(unlock);
        var password = new Button { Content = "Use Windows account password", Padding = new Thickness(10, 6, 10, 6), Margin = new Thickness(0, 10, 0, 0) };
        password.Click += async (_, _) => { password.IsEnabled = false; try { await UnlockAsync(usePassword: true); } finally { password.IsEnabled = true; } };
        panel.Children.Add(password);
        var close = new Button { Content = "Close OctoShip", Padding = new Thickness(10, 6, 10, 6), Margin = new Thickness(0, 10, 0, 0) };
        close.Click += (_, _) => { _allowClose = true; _application.Shutdown(); };
        panel.Children.Add(close);
        _lockWindow = new Window { Title = "Unlock OctoShip", Width = 470, SizeToContent = SizeToContent.Height,
            ResizeMode = ResizeMode.NoResize, WindowStartupLocation = WindowStartupLocation.CenterScreen,
            Background = new SolidColorBrush(Color.FromRgb(17, 24, 39)), Content = panel };
        _lockWindow.Closing += (_, args) => { if (!_allowClose && IsLocked) args.Cancel = true; };
        _lockWindow.Show();
        unlock.Focus();
    }
    private async Task UnlockAsync(bool usePassword = false)
    {
        if (_unlocking || _lockWindow is null) return;
        if (DateTimeOffset.UtcNow < _retryAfter) { _status!.Text = "Wait a few seconds before trying again."; return; }
        _unlocking = true;
        try
        {
            _status!.Text = "Complete the Windows authentication prompt.";
            if (usePassword)
            {
                if (!WindowsAccountPasswordVerifier.Verify(new WindowInteropHelper(_lockWindow).Handle))
                { _status.Text = "Your current Windows account was not verified. Your workspace remains locked."; return; }
            }
            else
            {
            var availability = await UserConsentVerifier.CheckAvailabilityAsync();
            if (availability != UserConsentVerifierAvailability.Available)
            {
                _status.Text = "Windows Hello is unavailable (" + availability + "). Use your Windows account password, or set up Windows Hello in Windows Settings → Accounts → Sign-in options.";
                return;
            }
            var result = await UserConsentVerifierInterop.RequestVerificationForWindowAsync(new WindowInteropHelper(_lockWindow).Handle, "Unlock your OctoShip account workspace");
            if (result != UserConsentVerificationResult.Verified)
            { _status.Text = "Windows did not verify your identity (" + result + "). Your workspace remains locked."; return; }
            }
            _state.UnlockAfterVerification(DateTimeOffset.UtcNow);
            Persist();
            foreach (var pair in _shields)
            {
                pair.Key.Closing -= PreventWorkspaceClose;
                pair.Key.Content = pair.Value.Content;
                pair.Key.Title = pair.Value.Title;
            }
            _shields.Clear();
            _nativeWindows.Restore();
            var window = _lockWindow; _lockWindow = null; window.Close();
            _application.MainWindow?.Activate();
            _unlockCompletion?.TrySetResult(true); _unlockCompletion = null;
        }
        catch (Exception)
        { _status!.Text = "Windows authentication could not be completed. Your workspace remains locked. Retry or close OctoShip."; }
        finally { _unlocking = false; if (IsLocked) _retryAfter = DateTimeOffset.UtcNow.AddSeconds(5); }
    }
    private void Persist()
    {
        try { _state.Save(_path); _lastSaved = DateTimeOffset.UtcNow; PersistenceError = null; }
        catch (Exception) { PersistenceError = "OctoShip could not save its session state. Check access to its LocalAppData folder."; }
        if (_status is not null && PersistenceError is not null) _status.Text = PersistenceError;
    }
    public void Dispose()
    {
        if (_disposed) return;
        Persist(); _disposed = true; _allowClose = true;
        _unlockCompletion?.TrySetCanceled();
        _timer.Stop(); InputManager.Current.PreProcessInput -= OnInput; SystemEvents.SessionSwitch -= OnSessionSwitch;
        foreach (var window in _shields.Keys) window.Closing -= PreventWorkspaceClose;
        if (Current == this) Current = null;
    }
    private sealed record Shield(object? Content, string Title);
}
