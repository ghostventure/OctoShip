using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;

namespace FileToGitHub;

/// <summary>Edits local named upload constraints; profile changes never publish files.</summary>
public sealed class UploadPolicyProfilesWindow : Window
{
    private readonly List<UploadPolicyProfile> _profiles;
    private readonly ListBox _list = new();
    private readonly TextBox _name = new();
    private readonly TextBox _includes = new() { AcceptsReturn = true, Height = 78, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
    private readonly TextBox _excludes = new() { AcceptsReturn = true, Height = 78, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
    private readonly TextBox _maxMiB = new();
    private readonly TextBlock _status = new();
    private string? _editingOriginalName;
    private bool _loading;

    public IReadOnlyList<UploadPolicyProfile> Profiles => _profiles.ToArray();

    public UploadPolicyProfilesWindow(IEnumerable<UploadPolicyProfile> profiles)
    {
        UniformUi.Prepare(this);
        _profiles = UploadPolicyProfileService.Normalize(profiles).ToList();
        Title = "Upload policy profiles"; Width = 850; Height = 650; MinWidth = 600; MinHeight = 480;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        var root = new Grid { Margin = new Thickness(18) };
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(220) });
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(16) });
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        _list.DisplayMemberPath = nameof(UploadPolicyProfile.Name);
        _list.SelectionChanged += (_, _) => { if (!_loading && _list.SelectedItem is UploadPolicyProfile selected) LoadProfile(selected); };
        Grid.SetColumn(_list, 0); root.Children.Add(_list);

        var editor = new StackPanel(); Grid.SetColumn(editor, 2); root.Children.Add(editor);
        editor.Children.Add(new TextBlock { Text = "Named local profile", FontSize = 18, FontWeight = FontWeights.SemiBold });
        editor.Children.Add(new TextBlock { Text = "Constraints are checked against GitHub destination paths and file sizes in the standard single-file and reviewed folder-batch flows. They do not replace GitHub permissions or repository rules.", TextWrapping = TextWrapping.Wrap, Opacity = .75, Margin = new Thickness(0, 4, 0, 14) });
        AddField(editor, "Profile name", _name);
        AddField(editor, "Include patterns (one per line; blank means all paths)", _includes);
        AddField(editor, "Exclude patterns (one per line; exclusions take precedence)", _excludes);
        AddField(editor, "Maximum file size (MiB; 1 byte to 50 MiB)", _maxMiB);
        _status.TextWrapping = TextWrapping.Wrap; _status.Margin = new Thickness(0, 6, 0, 0); editor.Children.Add(_status);

        var buttons = new WrapPanel { Margin = new Thickness(0, 12, 0, 0) };
        AddButton(buttons, "New profile", NewProfile_Click);
        AddButton(buttons, "Save profile", SaveProfile_Click);
        AddButton(buttons, "Delete profile", DeleteProfile_Click);
        AddButton(buttons, "Cancel", (_, _) => { DialogResult = false; });
        AddButton(buttons, "Done", (_, _) => { DialogResult = true; });
        Grid.SetRow(buttons, 1); Grid.SetColumnSpan(buttons, 3); root.Children.Add(buttons);
        Content = root;
        RefreshList();
        if (_profiles.Count > 0) _list.SelectedIndex = 0; else NewProfile_Click(this, new RoutedEventArgs());
    }

    private static void AddField(Panel panel, string label, Control control)
    {
        panel.Children.Add(new TextBlock { Text = label, FontWeight = FontWeights.SemiBold, Margin = new Thickness(0, 8, 0, 3) });
        panel.Children.Add(control);
    }

    private static void AddButton(Panel panel, string label, RoutedEventHandler click)
    {
        var button = new Button { Content = label, Margin = new Thickness(0, 0, 7, 5), Padding = new Thickness(10, 6, 10, 6) };
        button.Click += click; panel.Children.Add(button);
    }

    private void RefreshList(string? selectName = null)
    {
        _loading = true;
        _list.ItemsSource = null; _list.ItemsSource = _profiles.ToArray();
        if (selectName is not null)
            _list.SelectedItem = _profiles.FirstOrDefault(profile => string.Equals(profile.Name, selectName, StringComparison.OrdinalIgnoreCase));
        _loading = false;
    }

    private void LoadProfile(UploadPolicyProfile profile)
    {
        _editingOriginalName = profile.Name;
        _name.Text = profile.Name;
        _includes.Text = string.Join(Environment.NewLine, profile.IncludePatterns);
        _excludes.Text = string.Join(Environment.NewLine, profile.ExcludePatterns);
        _maxMiB.Text = (profile.MaxFileBytes / (1024m * 1024m)).ToString("0.######", CultureInfo.InvariantCulture);
        _status.Text = "Editing local rules. Save here, then choose the profile in the main upload panel to apply it.";
    }

    private void NewProfile_Click(object sender, RoutedEventArgs e)
    {
        _loading = true; _list.SelectedItem = null; _loading = false;
        _editingOriginalName = null;
        _name.Text = ""; _includes.Text = ""; _excludes.Text = ""; _maxMiB.Text = "50";
        _status.Text = "Define a profile, then save it. It will not become active until selected in the main window.";
        _name.Focus();
    }

    private void SaveProfile_Click(object sender, RoutedEventArgs e)
    {
        if (!decimal.TryParse(_maxMiB.Text.Trim(), NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var maxMiB)
            || maxMiB <= 0 || maxMiB > 50)
        { _status.Text = "Maximum size must be a number greater than 0 and at most 50 MiB."; return; }
        var candidate = new UploadPolicyProfile
        {
            Name = _name.Text,
            IncludePatterns = _includes.Text.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries).Select(value => value.Trim()).Where(value => value.Length > 0).ToArray(),
            ExcludePatterns = _excludes.Text.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries).Select(value => value.Trim()).Where(value => value.Length > 0).ToArray(),
            MaxFileBytes = (long)(maxMiB * 1024m * 1024m)
        };
        try { candidate = UploadPolicyProfileService.Validate(candidate); }
        catch (ArgumentException ex) { _status.Text = ex.Message; return; }

        var index = _editingOriginalName is null ? -1 : _profiles.FindIndex(profile => string.Equals(profile.Name, _editingOriginalName, StringComparison.OrdinalIgnoreCase));
        var duplicate = _profiles.FindIndex(profile => string.Equals(profile.Name, candidate.Name, StringComparison.OrdinalIgnoreCase));
        if (duplicate >= 0 && duplicate != index)
        { _status.Text = "A profile with that name already exists."; return; }
        if (index >= 0) _profiles[index] = candidate; else _profiles.Add(candidate);
        _editingOriginalName = candidate.Name;
        RefreshList(candidate.Name);
        _status.Text = $"Saved '{candidate.Name}' locally. Review its rules and select it in the main upload panel to apply.";
    }

    private void DeleteProfile_Click(object sender, RoutedEventArgs e)
    {
        var profile = _list.SelectedItem as UploadPolicyProfile;
        if (profile is null) { _status.Text = "Select a saved profile to delete."; return; }
        if (MessageBox.Show(this, $"Delete the local profile '{profile.Name}'? This does not affect GitHub.", "Delete upload profile", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
        _profiles.RemoveAll(item => string.Equals(item.Name, profile.Name, StringComparison.OrdinalIgnoreCase));
        RefreshList(); NewProfile_Click(this, new RoutedEventArgs());
    }
}
