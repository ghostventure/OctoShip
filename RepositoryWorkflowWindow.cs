using System;
using System.Linq;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace FileToGitHub;

public sealed class RepositoryWorkflowWindow : Window
{
    private readonly RepositoryWorkflowService _service;
    private readonly Func<string?> _tokenProvider;
    private readonly CancellationTokenSource _lifetime = new();
    private readonly TextBox _repository = new(), _branch = new(), _remote = new(), _local = new(), _newBranch = new(), _head = new(), _base = new(), _title = new(), _body = new();
    private readonly TextBlock _status = new() { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 10, 0, 0) };
    private readonly DataGrid _results = new() { IsReadOnly = true, AutoGenerateColumns = true, Height = 240, Background = Brushes.White, Foreground = Brushes.Black };
    private readonly CheckBox _draft = new() { Content = "Create as draft", Foreground = Brushes.Black, IsChecked = true, Margin = new Thickness(0, 8, 0, 8) };
    private bool _busy;

    public RepositoryWorkflowWindow(HttpClient http, Func<string?> tokenProvider, string repository, string branch, string remoteFolder)
    {
        _service = new(http); _tokenProvider = tokenProvider;
        Title = "Compare folders, branches and pull requests"; Width = 820; Height = 800; MinWidth = 650; MinHeight = 500;
        Background = new SolidColorBrush(Color.FromRgb(16, 21, 30)); Foreground = Brushes.WhiteSmoke; WindowStartupLocation = WindowStartupLocation.CenterOwner;
        var root = new StackPanel { Margin = new Thickness(20) }; Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        root.Children.Add(new TextBlock { Text = "Repository workflow", FontSize = 22, Margin = new Thickness(0, 0, 0, 12) });
        AddField(root, "Repository (owner/name)", _repository, repository);
        AddField(root, "Comparison branch / source for a new branch", _branch, branch);
        var tabs = new TabControl { Margin = new Thickness(0, 10, 0, 0) }; root.Children.Add(tabs);
        var compare = Panel(); tabs.Items.Add(new TabItem { Header = "Folder comparison", Content = compare });
        compare.Children.Add(Note("Read-only comparison of raw file bytes at a fixed commit. Excludes .git; other ignore rules are not applied. Line endings and LFS pointers can differ from checked-out files. File modes are not compared. Links/junctions stop the scan."));
        AddField(compare, "Remote folder (blank = repository root)", _remote, remoteFolder);
        AddField(compare, "Local folder", _local, "");
        AddButton(compare, "Browse local folder", (_, _) => { using var dialog = new System.Windows.Forms.FolderBrowserDialog(); if (dialog.ShowDialog() == System.Windows.Forms.DialogResult.OK) _local.Text = dialog.SelectedPath; });
        AddButton(compare, "Compare folders", async (_, _) =>
        {
            var repo = _repository.Text.Trim(); var source = _branch.Text.Trim(); var remote = _remote.Text.Trim(); var local = _local.Text.Trim();
            _results.ItemsSource = null;
            await RunAsync(async token =>
            {
                var result = await _service.CompareAsync(repo, source, remote, local, token, _lifetime.Token);
                _results.ItemsSource = result.Files;
                return "Compared commit " + result.Commit[..Math.Min(12, result.Commit.Length)] + ": " + string.Join(", ", result.Files.GroupBy(x => x.Status).Select(g => $"{g.Count()} {g.Key.ToLowerInvariant()}")) + ". No files were uploaded or deleted.";
            }, false);
        });
        compare.Children.Add(_results);
        var branchPanel = Panel(); tabs.Items.Add(new TabItem { Header = "Create branch", Content = branchPanel });
        branchPanel.Children.Add(Note("Create a new branch from the source branch above. Existing branches are never overwritten. Afterwards, choose the new branch as your upload destination."));
        AddField(branchPanel, "New branch name", _newBranch, "");
        AddButton(branchPanel, "Create branch on GitHub", async (_, _) =>
        {
            var repo = _repository.Text.Trim(); var source = _branch.Text.Trim(); var target = _newBranch.Text.Trim();
            if (_busy || MessageBox.Show(this, $"Create {target} in {repo} from {source}?", "Create branch", MessageBoxButton.OKCancel) != MessageBoxResult.OK) return;
            await RunAsync(async token => "Created " + await _service.CreateBranchAsync(repo, source, target, token, _lifetime.Token) + " in " + repo + ". Select it as the upload branch when ready.", true);
        });
        var pr = Panel(); tabs.Items.Add(new TabItem { Header = "Create pull request", Content = pr });
        pr.Children.Add(Note("Use two existing branches in this repository. Upload your changes to the head branch first. Creating a pull request does not merge it."));
        AddField(pr, "Head branch (your changes)", _head, ""); AddField(pr, "Base branch (destination)", _base, branch);
        AddField(pr, "Title", _title, ""); AddField(pr, "Description", _body, ""); _body.AcceptsReturn = true; _body.Height = 100; _body.VerticalScrollBarVisibility = ScrollBarVisibility.Auto;
        pr.Children.Add(_draft);
        AddButton(pr, "Create pull request on GitHub", async (_, _) =>
        {
            var repo = _repository.Text.Trim(); var head = _head.Text.Trim(); var target = _base.Text.Trim(); var title = _title.Text; var body = _body.Text; var draft = _draft.IsChecked == true;
            if (_busy || MessageBox.Show(this, $"Create {(draft ? "draft " : "")}pull request in {repo}: {head} into {target}?\n\n{title}", "Create pull request", MessageBoxButton.OKCancel) != MessageBoxResult.OK) return;
            await RunAsync(async token => "Pull request created: " + await _service.CreatePullRequestAsync(repo, head, target, title, body, draft, token, _lifetime.Token), true);
        });
        root.Children.Add(_status);
        Closed += (_, _) => _lifetime.Cancel();
    }
    private async Task RunAsync(Func<string, Task<string>> action, bool mutation)
    {
        if (_busy) return; _busy = true; _status.Text = "Working...";
        try
        {
            var token = _tokenProvider(); if (string.IsNullOrWhiteSpace(token)) throw new InvalidOperationException("Sign in to GitHub first.");
            _status.Text = await action(token);
        }
        catch (OperationCanceledException) { _status.Text = mutation ? "Request interrupted. Check GitHub before retrying; the action may have completed." : "Comparison cancelled."; }
        catch (Exception ex) { _status.Text = ex.Message + (mutation ? " If the connection failed, check GitHub before retrying." : ""); }
        finally { _busy = false; }
    }
    private static StackPanel Panel() => new() { Margin = new Thickness(12), Background = Brushes.White };
    private static TextBlock Note(string text) => new() { Text = text, Foreground = Brushes.Black, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 4, 0, 10) };
    private static void AddField(Panel parent, string label, TextBox box, string value)
    {
        parent.Children.Add(new TextBlock { Text = label, Foreground = parent.Background == Brushes.White ? Brushes.Black : Brushes.WhiteSmoke, Margin = new Thickness(0, 5, 0, 3) });
        box.Text = value; box.Padding = new Thickness(6); box.Foreground = Brushes.Black; box.Background = Brushes.White; parent.Children.Add(box);
    }
    private static void AddButton(Panel parent, string text, RoutedEventHandler handler)
    {
        var button = new Button { Content = text, Padding = new Thickness(10, 6, 10, 6), Margin = new Thickness(0, 8, 0, 8), HorizontalAlignment = HorizontalAlignment.Left, Foreground = Brushes.Black };
        button.Click += handler; parent.Children.Add(button);
    }
}
