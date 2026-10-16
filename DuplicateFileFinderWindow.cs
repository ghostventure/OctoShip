using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;

namespace FileToGitHub;

public sealed class DuplicateFileFinderWindow : Window
{
    private readonly TextBox _folder = new();
    private readonly TextBlock _status = new();
    private readonly ListBox _results = new();
    private readonly Button _scan = new() { Content = "Find identical files" };
    private readonly Button _cancel = new() { Content = "Cancel", IsEnabled = false };
    private readonly Button _export = new() { Content = "Export report", IsEnabled = false };
    private readonly DuplicateFileFinderService _service = new();
    private CancellationTokenSource? _cancellation;
    private DuplicateScanResult? _lastResult;

    public DuplicateFileFinderWindow(string folder)
    {
        UniformUi.Prepare(this);
        Title = "Find duplicate files";
        Width = 880; Height = 650; MinWidth = 580; MinHeight = 430;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        var root = new DockPanel { Margin = new Thickness(18) };
        var footer = new TextBlock
        {
            Text = "Read-only scan · linked folders are skipped · hashes files up to 256 MiB with a 1 GiB total hash budget",
            TextWrapping = TextWrapping.Wrap, Opacity = .72, Margin = new Thickness(0, 12, 0, 0)
        };
        DockPanel.SetDock(footer, Dock.Bottom);
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 10, 0, 10) };
        var choose = new Button { Content = "Choose folder" };
        choose.Click += ChooseFolder_Click;
        _scan.Click += async (_, _) => await ScanAsync();
        _cancel.Click += (_, _) => _cancellation?.Cancel();
        _export.Click += ExportReport_Click;
        actions.Children.Add(choose); actions.Children.Add(_scan); actions.Children.Add(_cancel); actions.Children.Add(_export);
        var content = new StackPanel();
        content.Children.Add(new TextBlock { Text = "Project folder", Margin = new Thickness(0, 0, 0, 5), FontWeight = FontWeights.SemiBold });
        _folder.Text = folder; _folder.Margin = new Thickness(0, 0, 0, 2); content.Children.Add(_folder);
        content.Children.Add(actions);
        _status.Text = "Finds files with the same length and SHA-256 digest. It never removes or changes files.";
        _status.TextWrapping = TextWrapping.Wrap; _status.Margin = new Thickness(0, 0, 0, 8); content.Children.Add(_status);
        _results.MinHeight = 250;
        _results.HorizontalContentAlignment = HorizontalAlignment.Stretch;
        _results.ItemTemplate = BuildResultTemplate();
        content.Children.Add(_results);
        root.Children.Add(footer); root.Children.Add(content); Content = root;
        Closed += (_, _) => _cancellation?.Cancel();
    }

    private static DataTemplate BuildResultTemplate()
    {
        var template = new DataTemplate(typeof(string));
        var text = new FrameworkElementFactory(typeof(TextBlock));
        text.SetBinding(TextBlock.TextProperty, new System.Windows.Data.Binding());
        text.SetValue(TextBlock.TextWrappingProperty, TextWrapping.Wrap);
        text.SetValue(FrameworkElement.MarginProperty, new Thickness(4, 3, 4, 3));
        template.VisualTree = text;
        return template;
    }

    private void ChooseFolder_Click(object sender, RoutedEventArgs e)
    {
        using var dialog = new System.Windows.Forms.FolderBrowserDialog { Description = "Choose a project folder to scan", UseDescriptionForTitle = true };
        if (Directory.Exists(_folder.Text)) dialog.SelectedPath = _folder.Text;
        if (dialog.ShowDialog() == System.Windows.Forms.DialogResult.OK) _folder.Text = dialog.SelectedPath;
    }

    private async Task ScanAsync()
    {
        if (!Directory.Exists(_folder.Text)) { _status.Text = "Choose an existing folder first."; return; }
        _cancellation?.Dispose(); _cancellation = new CancellationTokenSource();
        var token = _cancellation.Token;
        _scan.IsEnabled = false; _cancel.IsEnabled = true; _export.IsEnabled = false;
        _results.ItemsSource = null; _lastResult = null;
        _status.Text = "Scanning folder entries…";
        var progress = new Progress<(int Visited, int Candidates, long Bytes)>(value =>
            _status.Text = $"Visited {value.Visited:N0} entries · hashed {value.Candidates:N0} candidate files · {FormatSize(value.Bytes)} read");
        try
        {
            var result = await Task.Run(() => _service.Scan(_folder.Text, progress, token), token);
            _lastResult = result;
            _results.ItemsSource = result.Groups.Select(group => group.Display).ToArray();
            _export.IsEnabled = result.Groups.Count > 0;
            var headline = result.Groups.Count == 0 ? "No identical files were found in the files checked." :
                $"Found {result.Groups.Count:N0} duplicate group(s) across {result.Groups.Sum(group => group.Files.Count):N0} files.";
            var notes = result.Warnings.Count == 0 ? "" : " " + string.Join(" ", result.Warnings);
            _status.Text = $"{headline} Visited {result.VisitedEntries:N0} entries, hashed {result.HashedFiles:N0} files ({FormatSize(result.HashedBytes)})." +
                (result.Limited ? " Scan limits were reached; remaining files were not checked." : "") + notes;
        }
        catch (OperationCanceledException) { _status.Text = "Scan canceled. No files were changed."; }
        catch (Exception ex) { _status.Text = "Could not finish duplicate scan: " + SecurityBoundaries.Redact(ex.Message); }
        finally
        {
            _scan.IsEnabled = true; _cancel.IsEnabled = false;
            _cancellation?.Dispose(); _cancellation = null;
        }
    }

    private void ExportReport_Click(object sender, RoutedEventArgs e)
    {
        if (_lastResult is null || _lastResult.Groups.Count == 0) return;
        using var dialog = new System.Windows.Forms.SaveFileDialog
        {
            Title = "Export duplicate-file report", Filter = "Text files (*.txt)|*.txt|All files (*.*)|*.*",
            FileName = "OctoShip-duplicate-files.txt", OverwritePrompt = true
        };
        if (dialog.ShowDialog() != System.Windows.Forms.DialogResult.OK) return;
        try
        {
            var lines = new[]
            {
                "OctoShip duplicate-file report", "Folder: " + Path.GetFullPath(_folder.Text),
                "This report contains local file paths. Review it before sharing.",
                $"Visited entries: {_lastResult.VisitedEntries}; files hashed: {_lastResult.HashedFiles}; bytes hashed: {_lastResult.HashedBytes}; limited: {_lastResult.Limited}", ""
            }.Concat(_lastResult.Groups.Select(group => group.Display + "\nSHA-256: " + group.Sha256 + "\n"));
            File.WriteAllLines(dialog.FileName, lines, new UTF8Encoding(false));
            _status.Text = "Duplicate report exported. It contains full local paths; review it before sharing.";
        }
        catch (Exception ex) { _status.Text = "Could not export report: " + SecurityBoundaries.Redact(ex.Message); }
    }

    private static string FormatSize(long bytes) => bytes < 1024 * 1024 ? $"{bytes / 1024d:0.#} KB" : $"{bytes / (1024d * 1024):0.##} MB";
}
