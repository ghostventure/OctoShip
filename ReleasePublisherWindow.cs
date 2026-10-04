using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Threading;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace FileToGitHub;

public sealed class ReleasePublisherWindow : Window
{
    private readonly GitHubReleaseService _service;
    private readonly string _owner, _repository, _branch, _token;
    private readonly TextBox _tag = new(), _title = new(), _notes = new() { AcceptsReturn = true, Height = 125, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
    private readonly CheckBox _prerelease = new() { Content = "Pre-release", Margin = new Thickness(0, 8, 0, 8) };
    private readonly ListBox _assets = new() { Height = 100 };
    private readonly TextBlock _status = new() { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 10, 0, 10) };
    private readonly Button _create = new() { Content = "Create draft and upload assets", Padding = new Thickness(10) };
    private readonly Button _publish = new() { Content = "Publish release", IsEnabled = false, Padding = new Thickness(10), Margin = new Thickness(8, 0, 0, 0) };
    private readonly StackPanel _editor = new();
    private readonly CancellationTokenSource _lifetime = new();
    private readonly List<string> _paths = new();
    private CreatedRelease? _release;
    private bool _busy;

    public ReleasePublisherWindow(HttpClient http, string owner, string repository, string branch, string token)
    {
        _service = new GitHubReleaseService(http);
        _owner = owner; _repository = repository; _branch = branch; _token = token;
        Title = "Release publisher — OctoShip"; Width = 730; Height = 750; MinWidth = 600; MinHeight = 620;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        Background = new SolidColorBrush(Color.FromRgb(11, 16, 32)); Foreground = Brushes.White;
        var inputBackground = new SolidColorBrush(Color.FromRgb(24, 35, 53));
        foreach (var input in new Control[] { _tag, _title, _notes, _assets })
        {
            input.Background = inputBackground;
            input.Foreground = Brushes.White;
            input.BorderBrush = new SolidColorBrush(Color.FromRgb(91, 112, 139));
            input.Padding = new Thickness(6);
        }
        _prerelease.Foreground = Brushes.White;
        var panel = new StackPanel { Margin = new Thickness(22) };
        Content = new ScrollViewer { Content = panel, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        panel.Children.Add(new TextBlock { Text = $"Release for {owner}/{repository}", FontSize = 22, FontWeight = FontWeights.Bold });
        panel.Children.Add(new TextBlock { Text = $"Target: {branch}. Existing tags keep their original commit. Create a draft first, then publish when ready.", TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 10, 0, 12) });
        panel.Children.Add(_editor);
        Field("Tag (for example v1.6.0)", _tag); Field("Release title", _title); Field("Release notes", _notes);
        _editor.Children.Add(_prerelease);
        _editor.Children.Add(new TextBlock { Text = "Assets (archives and binaries are not inspected for embedded secrets)", TextWrapping = TextWrapping.Wrap });
        _editor.Children.Add(_assets);
        var add = new Button { Content = "Add assets", Margin = new Thickness(0, 8, 0, 0) };
        add.Click += (_, _) =>
        {
            var picker = new Microsoft.Win32.OpenFileDialog { Multiselect = true, Title = "Select release assets" };
            if (picker.ShowDialog(this) != true) return;
            foreach (var path in picker.FileNames) if (!_paths.Contains(path, StringComparer.OrdinalIgnoreCase)) _paths.Add(path);
            RefreshAssets();
        };
        _editor.Children.Add(add);
        var remove = new Button { Content = "Remove selected asset", Margin = new Thickness(0, 6, 0, 0) };
        remove.Click += (_, _) => { if (_assets.SelectedIndex >= 0) { _paths.RemoveAt(_assets.SelectedIndex); RefreshAssets(); } };
        _editor.Children.Add(remove);
        panel.Children.Add(_status);
        var actions = new StackPanel { Orientation = Orientation.Horizontal };
        actions.Children.Add(_create); actions.Children.Add(_publish); panel.Children.Add(actions);
        foreach (var button in new[] { add, remove, _create, _publish })
        {
            button.Foreground = Brushes.White;
            button.Background = new SolidColorBrush(Color.FromRgb(28, 79, 87));
        }
        _publish.Foreground = Brushes.DimGray;
        _publish.IsEnabledChanged += (_, _) => _publish.Foreground = _publish.IsEnabled ? Brushes.White : Brushes.DimGray;
        _create.Click += Create_Click; _publish.Click += Publish_Click;
        Closing += (_, e) => { if (_busy) { e.Cancel = true; _status.Text += "\nWait for the current operation to finish before closing."; } };
        Closed += (_, _) => { _lifetime.Cancel(); _lifetime.Dispose(); };
    }
    private void Field(string label, Control control)
    {
        _editor.Children.Add(new TextBlock { Text = label, Margin = new Thickness(0, 8, 0, 4) });
        _editor.Children.Add(control);
    }
    private void RefreshAssets() => _assets.ItemsSource = _paths.Select(Path.GetFileName).ToArray();

    private async void Create_Click(object sender, RoutedEventArgs e)
    {
        if (_busy || _release != null) return;
        try
        {
            if (string.IsNullOrWhiteSpace(_tag.Text)) throw new InvalidOperationException("Enter a release tag.");
            if (_paths.Select(Path.GetFileName).Distinct(StringComparer.OrdinalIgnoreCase).Count() != _paths.Count) throw new InvalidOperationException("Asset filenames must be unique.");
            foreach (var path in _paths)
            {
                var info = new FileInfo(path);
                if (!info.Exists || info.Length == 0 || info.Length >= 2L * 1024 * 1024 * 1024) throw new InvalidOperationException("Each asset must exist, be nonempty, and be smaller than 2 GiB.");
            }
            var notesScan = ContentSecretScanner.ScanText(_notes.Text);
            if (notesScan.HasFindings && MessageBox.Show(this, notesScan.Summary + "\nInclude these release notes?", "Review release notes", MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes) return;
            if (MessageBox.Show(this, $"Create draft {_tag.Text.Trim()} in {_owner}/{_repository} from {_branch} and upload {_paths.Count} asset(s)?\nAssets are uploaded as selected; archives and binaries are not secret-scanned.", "Create GitHub draft", MessageBoxButton.YesNo, MessageBoxImage.Question, MessageBoxResult.No) != MessageBoxResult.Yes) return;
            _busy = true; _create.IsEnabled = false; _editor.IsEnabled = false;
            _status.Text = "Creating draft...";
            _release = await _service.CreateDraftAsync(_owner, _repository, _token, _tag.Text, _branch, _title.Text, _notes.Text, _prerelease.IsChecked == true, _lifetime.Token);
            foreach (var path in _paths)
            {
                _status.Text = "Uploading " + Path.GetFileName(path) + "\nDraft: " + _release.HtmlUrl;
                await _service.UploadAssetAsync(_owner, _repository, _token, _release.Id, path, _lifetime.Token);
            }
            _status.Text = "Draft ready; all selected assets uploaded.\n" + _release.HtmlUrl;
            _publish.IsEnabled = true;
        }
        catch (Exception ex)
        {
            _status.Text = ex.Message + (_busy ? "\nInspect GitHub before retrying; a draft or partial upload may remain." : "") + (_release == null ? "" : "\nDraft: " + _release.HtmlUrl);
        }
        finally { _busy = false; }
    }
    private async void Publish_Click(object sender, RoutedEventArgs e)
    {
        if (_busy || _release == null) return;
        if (MessageBox.Show(this, $"Publish {_tag.Text.Trim()} in {_owner}/{_repository} now? The release will become visible to repository readers.", "Publish release", MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes) return;
        _busy = true; _publish.IsEnabled = false;
        try
        {
            _release = await _service.PublishAsync(_owner, _repository, _token, _release.Id, _lifetime.Token);
            _status.Text = "Release published.\n" + _release.HtmlUrl;
        }
        catch (Exception ex) { _status.Text = ex.Message + "\nInspect the release on GitHub to confirm its state.\n" + _release.HtmlUrl; }
        finally { _busy = false; }
    }
}
