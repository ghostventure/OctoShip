using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace FileToGitHub;

public sealed record PaletteCommand(string Id, string Title, string Description, string Shortcut);

/// <summary>Small searchable launcher for existing OctoShip actions.</summary>
public sealed class CommandPaletteWindow : Window
{
    private readonly IReadOnlyList<PaletteCommand> _commands;
    private readonly TextBox _query = new();
    private readonly ListBox _results = new();
    public string? SelectedCommandId { get; private set; }

    public CommandPaletteWindow(IEnumerable<PaletteCommand> commands)
    {
        _commands = commands.ToArray();
        UniformUi.Prepare(this);
        Title = "OctoShip command palette";
        Width = 610; Height = 470; MinWidth = 480; MinHeight = 340;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        ShowInTaskbar = false;
        var root = new DockPanel { Margin = new Thickness(18) };
        var footer = new TextBlock { Text = "Type to filter · Enter to run · Esc to close", Opacity = .72, Margin = new Thickness(0, 10, 0, 0) };
        DockPanel.SetDock(footer, Dock.Bottom);
        DockPanel.SetDock(_query, Dock.Top);
        _query.Margin = new Thickness(0, 0, 0, 12);
        _query.FontSize = 16;
        _query.Padding = new Thickness(9, 7, 9, 7);
        _results.ItemTemplate = CreateItemTemplate();
        _results.MouseDoubleClick += (_, _) => RunSelected();
        _results.PreviewKeyDown += Results_PreviewKeyDown;
        _query.TextChanged += (_, _) => RefreshResults();
        _query.PreviewKeyDown += Query_PreviewKeyDown;
        root.Children.Add(footer); root.Children.Add(_query); root.Children.Add(_results);
        Content = root;
        RefreshResults();
        Loaded += (_, _) => _query.Focus();
    }

    private void RefreshResults()
    {
        var query = _query.Text.Trim();
        var filtered = _commands.Where(command => string.IsNullOrEmpty(query)
            || command.Title.Contains(query, StringComparison.OrdinalIgnoreCase)
            || command.Description.Contains(query, StringComparison.OrdinalIgnoreCase)
            || command.Shortcut.Contains(query, StringComparison.OrdinalIgnoreCase)).ToArray();
        _results.ItemsSource = filtered;
        if (_results.Items.Count > 0) _results.SelectedIndex = 0;
    }

    private static DataTemplate CreateItemTemplate()
    {
        var template = new DataTemplate(typeof(PaletteCommand));
        var panel = new FrameworkElementFactory(typeof(DockPanel));
        var shortcut = new FrameworkElementFactory(typeof(TextBlock));
        shortcut.SetBinding(TextBlock.TextProperty, new System.Windows.Data.Binding(nameof(PaletteCommand.Shortcut)));
        shortcut.SetValue(TextBlock.OpacityProperty, .65d);
        shortcut.SetValue(FrameworkElement.MarginProperty, new Thickness(12, 0, 0, 0));
        DockPanel.SetDock(shortcut, Dock.Right); panel.AppendChild(shortcut);
        var text = new FrameworkElementFactory(typeof(StackPanel));
        var title = new FrameworkElementFactory(typeof(TextBlock));
        title.SetBinding(TextBlock.TextProperty, new System.Windows.Data.Binding(nameof(PaletteCommand.Title)));
        title.SetValue(TextBlock.FontWeightProperty, FontWeights.SemiBold); text.AppendChild(title);
        var description = new FrameworkElementFactory(typeof(TextBlock));
        description.SetBinding(TextBlock.TextProperty, new System.Windows.Data.Binding(nameof(PaletteCommand.Description)));
        description.SetValue(TextBlock.OpacityProperty, .7d); description.SetValue(TextBlock.FontSizeProperty, 11d); text.AppendChild(description);
        panel.AppendChild(text); template.VisualTree = panel;
        return template;
    }

    private void Query_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Down && _results.Items.Count > 0) { _results.Focus(); _results.SelectedIndex = Math.Min(_results.SelectedIndex + 1, _results.Items.Count - 1); e.Handled = true; }
        else if (e.Key == Key.Enter) { RunSelected(); e.Handled = true; }
        else if (e.Key == Key.Escape) { Close(); e.Handled = true; }
    }

    private void Results_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter) { RunSelected(); e.Handled = true; }
        else if (e.Key == Key.Escape) { Close(); e.Handled = true; }
    }

    private void RunSelected()
    {
        if (_results.SelectedItem is not PaletteCommand selected) return;
        SelectedCommandId = selected.Id;
        DialogResult = true;
    }
}
