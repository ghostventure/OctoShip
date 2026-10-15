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
    private static readonly string[] ThemeNames = { "Midnight", "Slate", "Ocean", "Forest", "Mint", "Plum", "Berry", "Rose", "Ember", "Sand", "Paper", "Arctic", "Sky", "Indigo", "Monochrome" };
    private sealed record Palette(string Canvas, string Surface, string Input, string Text, string Muted, string Border, string Button, string Primary, string Danger, string Success, string Warning, string Error, string Selection, string Accent);
    private static readonly Palette[] Palettes = {
        new("#0B1020","#121B2B","#0C1422","#E9EFF8","#A2B2C9","#34465E","#202D41","#116866","#742F40","#72DEC0","#F4CB83","#FF9CAA","#244E62","#50D6D0"),
        new("#111318","#1B1F26","#13171D","#F0F2F5","#AEB7C2","#3A424D","#292F38","#42658C","#873D4C","#78C9A6","#E6BD72","#FF9CAA","#2E4055","#8FB8E8"),
        new("#071522","#0D2233","#091B2A","#E8F4FC","#A4BDCE","#29475B","#173247","#146C85","#793C4A","#76D6BC","#EBC47B","#FFA1AA","#1D4961","#53C8E5"),
        new("#0D1712","#16251C","#101D16","#EAF4EC","#A8BBAE","#344B3B","#24382B","#316B49","#81424A","#8DD29D","#E4C77B","#FFA1AA","#294B35","#73C991"),
        new("#101916","#1A2922","#13211A","#ECF6F0","#AEC4B8","#3A5246","#273B30","#347A62","#86454D","#91D5B3","#E9C981","#FFA1AA","#315944","#74D9B0"),
        new("#171321","#241B31","#1C1628","#F2EBF8","#BFB1CC","#493A58","#342841","#704C91","#824254","#C49AE0","#EBC681","#FFA1AA","#49315C","#C39AE8"),
        new("#1B1118","#2B1A24","#21141C","#F8EBF1","#C8AEBB","#543646","#3B2632","#8A3F68","#923F53","#D291BA","#EBC47B","#FFA1AA","#542D48","#E28BBF"),
        new("#1B1413","#2B201F","#211817","#F8EFED","#C9B6B2","#55413D","#3B2E2B","#8B5144","#8A3D47","#D99E91","#E8C17B","#FFA1AA","#55352F","#E6A08F"),
        new("#1B1510","#2B2118","#21190F","#F8F1E8","#C8B8A4","#554533","#3B3023","#8A5B25","#91434A","#C5B06F","#E9C173","#FFA1AA","#574127","#E6AC5E"),
        new("#1A1813","#29261D","#201E17","#F6F2E9","#C4BCA9","#514A39","#393429","#74643A","#87444A","#BAC28B","#E2BD73","#FFA1AA","#4C4630","#D8C27D"),
        new("#F3F4F6","#FFFFFF","#F8FAFC","#20242B","#5B6470","#CBD1D8","#E8EBEF","#376B91","#A43C4B","#287A57","#896316","#A62236","#DDEAF3","#286E9D"),
        new("#101922","#1A2834","#14212C","#EDF4FA","#B2C2CF","#3B4D5A","#293B48","#3D697D","#854551","#82C4AC","#E3C47C","#FFA1AA","#2D4A5B","#8CC8DD"),
        new("#0E1720","#172532","#111E2A","#EDF3FA","#ABBACB","#35495B","#253747","#3E648F","#84434E","#79C5B3","#E8C37A","#FFA1AA","#2B465F","#83B9E8"),
        new("#111321","#1B1F35","#14172A","#EFF0FA","#B1B4CF","#3B3E5D","#292D49","#4F5391","#854454","#8EC6BE","#E6C17B","#FFA1AA","#343A68","#A5A9F2"),
        new("#151515","#222222","#191919","#F2F2F2","#B8B8B8","#444444","#303030","#666666","#8A4141","#91B39A","#D2B978","#FFA1AA","#3A3A3A","#B7C0C8")
    };
    public static IReadOnlyList<string> AvailableThemes => ThemeNames;
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
            ApplyTheme(resources, Preferences.Theme);
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
        try
        {
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
            {
                JsonSerializer.Serialize(stream, Preferences);
                stream.Flush(true);
            }
            File.Move(temp, SettingsPath, true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }
    private static void ApplyTheme(ResourceDictionary resources, string name)
    {
        var index = Array.FindIndex(ThemeNames, n => string.Equals(n, name, StringComparison.OrdinalIgnoreCase));
        if (index < 0) index = 0;
        var p = Palettes[index];
        SetBrush(resources, "CanvasBrush", p.Canvas); SetBrush(resources, "SurfaceBrush", p.Surface); SetBrush(resources, "InputBrush", p.Input);
        SetBrush(resources, "TextBrush", p.Text); SetBrush(resources, "MutedBrush", p.Muted); SetBrush(resources, "BorderBrush", p.Border);
        SetBrush(resources, "ButtonBrush", p.Button); SetBrush(resources, "PrimaryBrush", p.Primary); SetBrush(resources, "DangerBrush", p.Danger);
        SetBrush(resources, "SuccessBrush", p.Success); SetBrush(resources, "WarningBrush", p.Warning); SetBrush(resources, "ErrorBrush", p.Error);
        SetBrush(resources, "SelectionBrush", p.Selection); SetBrush(resources, "Accent", p.Accent);
        SetBrush(resources, "Panel", p.Surface); SetBrush(resources, "PanelSoft", p.Canvas); SetBrush(resources, "Line", p.Border); SetBrush(resources, "Muted", p.Muted);
        resources["CurrentTheme"] = ThemeNames[index];
    }
    private static void SetBrush(ResourceDictionary resources, string key, string color)
        => resources[key] = new SolidColorBrush((Color)ColorConverter.ConvertFromString(color));
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
                var primary = name.StartsWith("Upload ", StringComparison.OrdinalIgnoreCase) || name.StartsWith("Publish ", StringComparison.OrdinalIgnoreCase)
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

public sealed record DisplayPreferences(double TextSize = 14, bool Compact = true, string Theme = "Midnight")
{
    public static DisplayPreferences Normalize(DisplayPreferences value) => value with
    { TextSize = double.IsFinite(value.TextSize) ? Math.Clamp(value.TextSize, 12, 18) : 14,
      Theme = UniformUi.AvailableThemes.FirstOrDefault(n => string.Equals(n, value.Theme, StringComparison.OrdinalIgnoreCase)) ?? "Midnight" };
}
