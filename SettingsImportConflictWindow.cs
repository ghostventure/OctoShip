using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;

namespace FileToGitHub;

/// <summary>Per-setting import merge choices; unchecked rows preserve the current local value.</summary>
internal sealed class SettingsImportConflictWindow : Window
{
    private readonly Dictionary<string, CheckBox> _choices;
    public SettingsImportConflictWindow(IReadOnlyDictionary<string, string> differences)
    {
        Title = "Resolve settings import"; Width = 560; Height = 520; MinWidth = 460; MinHeight = 360;
        WindowStartupLocation = WindowStartupLocation.CenterOwner; Background = System.Windows.Media.Brushes.White;
        _choices = differences.ToDictionary(pair => pair.Key,
            pair => new CheckBox { Content = $"Use imported value for {pair.Key}\n{pair.Value}", IsChecked = true, Margin = new Thickness(4, 7, 4, 7) });
        var root = new DockPanel { Margin = new Thickness(16) };
        var hint = new TextBlock { Text = "Choose imported values one setting at a time. Unchecked settings keep the current value.", TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 10) };
        DockPanel.SetDock(hint, Dock.Top); root.Children.Add(hint);
        var buttons = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        var apply = new Button { Content = "Apply selected", MinWidth = 110, Margin = new Thickness(4) };
        apply.Click += (_, _) => { DialogResult = true; Close(); };
        var cancel = new Button { Content = "Cancel", MinWidth = 80, Margin = new Thickness(4) };
        cancel.Click += (_, _) => { DialogResult = false; Close(); };
        buttons.Children.Add(apply); buttons.Children.Add(cancel); DockPanel.SetDock(buttons, Dock.Bottom); root.Children.Add(buttons);
        var list = new StackPanel();
        foreach (var choice in _choices.Values) list.Children.Add(choice);
        root.Children.Add(new ScrollViewer { Content = list, VerticalScrollBarVisibility = ScrollBarVisibility.Auto });
        Content = root;
    }
}
