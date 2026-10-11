using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;

namespace FileToGitHub;

/// <summary>Shared appearance, accessible controls and window chrome. Never owns credentials.</summary>
public static class UniformUi
{
    private static bool _registered;
    private static readonly ConditionalWeakTable<FrameworkElement, object> Styled = new();
    private static readonly ConditionalWeakTable<Window, ContextInfo> Contexts = new();
    private static readonly List<WeakReference<TextBlock>> ContextLabels = new();
    private static string _account = "Not connected";
    public static DisplayPreferences Preferences { get; private set; } = new();
    private static string SettingsPath => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub", "display.json");
    public static void Initialize(Application application, bool loadPreferences = true)
    {
        if (!application.Resources.Contains("CanvasBrush"))
            application.Resources.MergedDictionaries.Add(ThemeResources());
        if (loadPreferences)
        {
            try { if (File.Exists(SettingsPath)) Preferences = DisplayPreferences.Normalize(JsonSerializer.Deserialize<DisplayPreferences>(File.ReadAllText(SettingsPath)) ?? new()); }
            catch { Preferences = new(); }
        }
        ApplyPreferences(Preferences, false);
        if (_registered) return;
        _registered = true;
        EventManager.RegisterClassHandler(typeof(FrameworkElement), FrameworkElement.LoadedEvent, new RoutedEventHandler(OnLoaded));
    }
    public static ResourceDictionary ThemeResources() => new() { Source = new Uri("/OctoShip;component/Theme.xaml", UriKind.Relative) };
    public static void Prepare(Window window)
    {
        if (Application.Current is { } app) Initialize(app, !_registered);
        else window.Resources.MergedDictionaries.Add(ThemeResources());
    }
    public static void SetDestination(Window window, Func<string> destination) => Contexts.GetOrCreateValue(window).Destination = destination;
    public static void SetAccount(string? account)
    {
        _account = string.IsNullOrWhiteSpace(account) ? "Not connected" : account;
        RefreshContexts();
    }
    public static void RefreshContexts()
    {
        foreach (var reference in ContextLabels.ToArray())
        {
            if (!reference.TryGetTarget(out var label)) { ContextLabels.Remove(reference); continue; }
            var owner = Window.GetWindow(label);
            var destination = owner is not null && Contexts.TryGetValue(owner, out var context) ? context.Destination?.Invoke() : null;
            label.Text = "Account: " + _account + (string.IsNullOrWhiteSpace(destination) ? "" : "   ·   " + destination);
        }
    }
    public static void ApplyPreferences(DisplayPreferences preferences, bool save = true)
    {
        Preferences = DisplayPreferences.Normalize(preferences);
        if (Application.Current is { } app)
        {
            var resources = app.Resources;
            resources["BodySize"] = Preferences.TextSize;
            resources["CaptionSize"] = Math.Max(12, Preferences.TextSize - 1);
            resources["HeadingSize"] = Preferences.TextSize + 10;
            resources["SectionSize"] = Preferences.TextSize + 3;
            resources["ControlHeight"] = Preferences.Compact ? 34d : 42d;
            resources["ControlPadding"] = Preferences.Compact ? new Thickness(10, 5, 10, 5) : new Thickness(12, 9, 12, 9);
            resources["ButtonMargin"] = Preferences.Compact ? new Thickness(0, 3, 7, 3) : new Thickness(0, 6, 9, 6);
            resources["PagePadding"] = new Thickness(Preferences.Compact ? 16 : 24);
        }
        if (!save) return;
        Directory.CreateDirectory(Path.GetDirectoryName(SettingsPath)!);
        var temp = SettingsPath + ".tmp-" + Guid.NewGuid().ToString("N");
        try { File.WriteAllText(temp, JsonSerializer.Serialize(Preferences)); File.Move(temp, SettingsPath, true); }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }
    private static void OnLoaded(object sender, RoutedEventArgs args)
    {
        if (sender is not FrameworkElement element) return;
        var window = element as Window ?? Window.GetWindow(element);
        if (window is null || (window.GetType().Namespace != "FileToGitHub" && !window.Title.Contains("OctoShip", StringComparison.Ordinal))) return;
        if (element is Window appWindow) ApplyWindow(appWindow);
        Normalize(element);
    }
    public static void ApplyWindow(Window window)
    {
        if (!Contexts.GetOrCreateValue(window).Framed)
        {
            Contexts.GetOrCreateValue(window).Framed = true;
            window.SetResourceReference(Control.FontFamilyProperty, "UiFont");
            window.SetResourceReference(Control.FontSizeProperty, "BodySize");
            if (window is not SplashWindow) window.SetResourceReference(Control.BackgroundProperty, "CanvasBrush");
            window.SetResourceReference(Control.ForegroundProperty, "TextBrush");
            window.UseLayoutRounding = true;
            if (window is not SplashWindow && window is not OctoShipDialog && window.Title != "Unlock OctoShip")
            {
                window.MinWidth = Math.Min(window.MinWidth, window is MainWindow ? 1000 : 560);
                window.MinHeight = Math.Min(window.MinHeight, window is MainWindow ? 680 : 460);
                window.MaxHeight = SystemParameters.WorkArea.Height;
                window.MaxWidth = SystemParameters.WorkArea.Width;
                window.InputBindings.Add(new KeyBinding(new UiCommand(() => AccountSessionLock.Current?.Lock()), new KeyGesture(Key.L, ModifierKeys.Control | ModifierKeys.Shift)));
                if (window is not MainWindow)
                {
                    var original = window.Content;
                    window.Content = null;
                    var frame = new DockPanel();
                    var account = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(16, 10, 16, 10) };
                    account.SetResourceReference(TextBlock.ForegroundProperty, "MutedBrush");
                    account.SetResourceReference(TextBlock.FontSizeProperty, "CaptionSize");
                    ContextLabels.Add(new(account));
                    DockPanel.SetDock(account, Dock.Top); frame.Children.Add(account);
                    var footer = new DockPanel { Margin = new Thickness(16, 8, 16, 10) };
                    var close = new Button { Content = "Close", MinWidth = 80, HorizontalAlignment = HorizontalAlignment.Right };
                    close.Click += (_, _) => window.Close(); DockPanel.SetDock(close, Dock.Right); footer.Children.Add(close);
                    footer.Children.Add(new TextBlock { Text = "Ctrl+Shift+L  Lock workspace", VerticalAlignment = VerticalAlignment.Center });
                    DockPanel.SetDock(footer, Dock.Bottom); frame.Children.Add(footer);
                    if (original is UIElement content) frame.Children.Add(content);
                    window.Content = frame;
                    window.AddHandler(TextBoxBase.TextChangedEvent, new TextChangedEventHandler((_, _) => RefreshContexts()));
                }
            }
        }
        NormalizeTree(window);
        RefreshContexts();
    }
    public static void NormalizeTree(DependencyObject root)
    {
        if (root is FrameworkElement element) Normalize(element);
        // Use logical children so unselected tabs receive the same treatment.
        foreach (var child in LogicalTreeHelper.GetChildren(root).OfType<DependencyObject>().ToArray()) NormalizeTree(child);
    }
    private static void Normalize(FrameworkElement element)
    {
        if (element.TemplatedParent is not null || Styled.TryGetValue(element, out _)) return;
        Styled.Add(element, new object());
        if (element is Control control && element is not Window)
        {
            control.SetResourceReference(Control.FontSizeProperty, "BodySize");
            control.SetResourceReference(Control.ForegroundProperty, "TextBrush");
            control.SetResourceReference(Control.BorderBrushProperty, "BorderBrush");
            control.SetResourceReference(Control.FocusVisualStyleProperty, "FocusRing");
            if (control is TextBox or PasswordBox or ComboBox or ListBox or DataGrid)
                control.SetResourceReference(Control.BackgroundProperty, "InputBrush");
            if (control is Button or TextBox or PasswordBox or ComboBox)
            {
                if (control.Height is > 0 and <= 48) control.ClearValue(FrameworkElement.HeightProperty);
                control.SetResourceReference(Control.MinHeightProperty, "ControlHeight");
                control.SetResourceReference(Control.PaddingProperty, "ControlPadding");
            }
            if (control is Button button)
            {
                var name = button.Content as string ?? "";
                var primary = name.StartsWith("Upload", StringComparison.OrdinalIgnoreCase) || name.StartsWith("Publish", StringComparison.OrdinalIgnoreCase)
                    || name.StartsWith("Validate and publish", StringComparison.OrdinalIgnoreCase) || name.StartsWith("Create ", StringComparison.OrdinalIgnoreCase)
                    || name.StartsWith("Unlock with", StringComparison.OrdinalIgnoreCase) || name.StartsWith("Continue to", StringComparison.OrdinalIgnoreCase)
                    || name.StartsWith("3. Create", StringComparison.OrdinalIgnoreCase) || name is "Connect" or "Save" or "Save settings";
                var danger = name.StartsWith("Delete", StringComparison.OrdinalIgnoreCase) || name.StartsWith("Remove", StringComparison.OrdinalIgnoreCase) || name.StartsWith("Clear selected", StringComparison.OrdinalIgnoreCase);
                button.SetResourceReference(Control.BackgroundProperty, danger ? "DangerBrush" : primary ? "PrimaryBrush" : "ButtonBrush");
                if (string.IsNullOrEmpty(AutomationProperties.GetName(button))) AutomationProperties.SetName(button, name.Replace("_", ""));
                button.SetResourceReference(FrameworkElement.MarginProperty, "ButtonMargin");
                if (button.Content is string) button.SetResourceReference(ContentControl.ContentTemplateProperty, "ButtonTextTemplate");
            }
            if (control is DataGrid grid)
            {
                grid.SetResourceReference(DataGrid.RowBackgroundProperty, "InputBrush");
                grid.SetResourceReference(DataGrid.AlternatingRowBackgroundProperty, "SurfaceBrush");
                grid.SetResourceReference(DataGrid.HorizontalGridLinesBrushProperty, "BorderBrush");
            }
            if (control is TextBox box)
            {
                box.SetResourceReference(TextBox.CaretBrushProperty, "Accent");
                if (box.IsReadOnly || box.Name.Contains("Path") || box.Name.Contains("Folder")) box.SetResourceReference(Control.FontFamilyProperty, "CodeFont");
                if (string.IsNullOrWhiteSpace(AutomationProperties.GetName(box)))
                {
                    var label = FindLabel(box);
                    AutomationProperties.SetName(box, label ?? box.ToolTip as string ?? Friendly(box.Name));
                }
            }
            if (control is ProgressBar progress)
            { progress.SetResourceReference(Control.BackgroundProperty, "ButtonBrush"); progress.SetResourceReference(Control.ForegroundProperty, "Accent"); }
        }
        if (element is TextBlock text)
        {
            var size = text.FontSize;
            text.SetResourceReference(TextBlock.FontSizeProperty, size >= 20 ? "HeadingSize" : size >= 15 ? "SectionSize" : size <= 12 ? "CaptionSize" : "BodySize");
            if (text.Foreground is SolidColorBrush brush)
            {
                var c = brush.Color;
                var semantic = c.R > c.G * 1.15 && c.G > c.B * 1.1 ? "WarningBrush"
                    : c.R > c.G * 1.35 && c.R > c.B * 1.2 ? "ErrorBrush"
                    : c.G > c.R * 1.5 && c.G > c.B * 1.05 ? "SuccessBrush"
                    : c.G > c.R * 1.5 && c.B > c.R * 1.5 ? "Accent"
                    : c.R is > 70 and < 210 && c.B > c.R ? "MutedBrush" : "TextBrush";
                text.SetResourceReference(TextBlock.ForegroundProperty, semantic);
            }
        }
        if (element is Panel panel && panel.Background is SolidColorBrush { Color.A: > 0 }) panel.SetResourceReference(Panel.BackgroundProperty, "CanvasBrush");
        if (element is Border border && border.Background is SolidColorBrush background && background.Color.A > 0)
        {
            var color = background.Color;
            // Keep explicit warning cards visually distinct.
            if (color.R <= color.G * 1.3) border.SetResourceReference(Border.BackgroundProperty, "SurfaceBrush");
            border.SetResourceReference(Border.BorderBrushProperty, "BorderBrush");
            if (border.CornerRadius.TopLeft > 0) border.CornerRadius = new CornerRadius(8);
        }
    }
    private static string? FindLabel(FrameworkElement element)
    {
        if (element.Parent is not Panel panel) return null;
        var index = panel.Children.IndexOf(element);
        return index > 0 && panel.Children[index - 1] is TextBlock label ? label.Text : null;
    }
    private static string Friendly(string name) => string.IsNullOrWhiteSpace(name) ? "Text input" : System.Text.RegularExpressions.Regex.Replace(name, "([a-z])([A-Z])", "$1 $2").Replace("Box", "").Trim();
    private sealed class ContextInfo { public bool Framed; public Func<string>? Destination; }
    private sealed class UiCommand : ICommand
    {
        private readonly Action _action;
        public UiCommand(Action action) => _action = action;
        public bool CanExecute(object? parameter) => true;
        public void Execute(object? parameter) => _action();
        public event EventHandler? CanExecuteChanged { add { } remove { } }
    }
}

public sealed record DisplayPreferences(double TextSize = 14, bool Compact = true)
{
    public static DisplayPreferences Normalize(DisplayPreferences value) => value with
    { TextSize = double.IsFinite(value.TextSize) ? Math.Clamp(value.TextSize, 12, 18) : 14 };
}
