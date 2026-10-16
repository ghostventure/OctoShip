using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Windows;
using System.Windows.Controls;

namespace FileToGitHub;

/// <summary>Edits local Markdown issue and pull-request templates under a selected project .github folder.</summary>
public sealed class RepositoryTemplateManagerWindow : Window
{
    private sealed record TemplateEntry(string Kind, string Name, string Path)
    {
        public string Label => $"{Kind} · {Name}";
        public override string ToString() => Label;
    }

    private readonly TextBox _project = new();
    private readonly ComboBox _kind = new();
    private readonly TextBox _name = new();
    private readonly TextBox _body = new() { AcceptsReturn = true, AcceptsTab = true, TextWrapping = TextWrapping.Wrap, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Auto };
    private readonly ListBox _templates = new();
    private readonly TextBlock _status = new();
    private string? _currentPath;
    private bool _loading;

    public RepositoryTemplateManagerWindow(string projectFolder)
    {
        UniformUi.Prepare(this);
        Title = "Local issue and pull-request templates"; Width = 1020; Height = 700; MinWidth = 700; MinHeight = 500;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        var root = new DockPanel { Margin = new Thickness(18) };
        var warning = new TextBlock
        {
            Text = "Local files only. Saving edits your project working tree; OctoShip does not send templates to GitHub. Review and publish those files through the normal upload workflow when you choose.",
            TextWrapping = TextWrapping.Wrap, Opacity = .78, Margin = new Thickness(0, 0, 0, 12)
        };
        DockPanel.SetDock(warning, Dock.Top); root.Children.Add(warning);
        var layout = new Grid();
        layout.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(260) });
        layout.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(16) });
        layout.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        layout.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var projectBar = new DockPanel { Margin = new Thickness(0, 0, 0, 10) };
        var browse = new Button { Content = "Choose local project folder" }; browse.Click += Browse_Click;
        DockPanel.SetDock(browse, Dock.Right); projectBar.Children.Add(browse);
        _project.Text = projectFolder; _project.IsReadOnly = true; projectBar.Children.Add(_project);
        Grid.SetColumnSpan(projectBar, 3); Grid.SetRow(projectBar, 0); layout.Children.Add(projectBar);

        var left = new DockPanel(); Grid.SetRow(left, 1); Grid.SetColumn(left, 0); layout.Children.Add(left);
        var leftButtons = new WrapPanel { Margin = new Thickness(0, 0, 0, 7) };
        var refresh = new Button { Content = "Refresh list" }; refresh.Click += (_, _) => RefreshTemplates(); leftButtons.Children.Add(refresh);
        var newIssue = new Button { Content = "New issue" }; newIssue.Click += (_, _) => NewTemplate("Issue", "bug-report.md"); leftButtons.Children.Add(newIssue);
        var newPr = new Button { Content = "New PR" }; newPr.Click += (_, _) => NewTemplate("Pull request", "pull-request.md"); leftButtons.Children.Add(newPr);
        DockPanel.SetDock(leftButtons, Dock.Top); left.Children.Add(leftButtons);
        _templates.SelectionChanged += (_, _) => { if (!_loading && _templates.SelectedItem is TemplateEntry entry) LoadTemplate(entry); };
        left.Children.Add(_templates);

        var editor = new Grid(); Grid.SetRow(editor, 1); Grid.SetColumn(editor, 2); layout.Children.Add(editor);
        editor.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        editor.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        editor.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        editor.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var metadata = new Grid { Margin = new Thickness(0, 0, 0, 8) };
        metadata.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(140) });
        metadata.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(10) });
        metadata.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        _kind.Items.Add("Issue"); _kind.Items.Add("Pull request"); _kind.SelectedIndex = 0;
        metadata.Children.Add(_kind); Grid.SetColumn(_name, 2); metadata.Children.Add(_name);
        Grid.SetRow(metadata, 0); editor.Children.Add(metadata);
        var nameLabel = new TextBlock { Text = "Markdown file name", Opacity = .72, Margin = new Thickness(0, 0, 0, 3) };
        Grid.SetRow(nameLabel, 1); editor.Children.Add(nameLabel);
        Grid.SetRow(_body, 2); editor.Children.Add(_body);
        _status.TextWrapping = TextWrapping.Wrap; _status.Margin = new Thickness(0, 8, 0, 0);
        Grid.SetRow(_status, 3); editor.Children.Add(_status);

        var footer = new WrapPanel { Margin = new Thickness(0, 12, 0, 0) };
        var save = new Button { Content = "Save local Markdown template", Padding = new Thickness(12, 7, 12, 7) };
        save.Click += SaveTemplate_Click; footer.Children.Add(save);
        var close = new Button { Content = "Close", Padding = new Thickness(12, 7, 12, 7) }; close.Click += (_, _) => Close(); footer.Children.Add(close);
        Grid.SetRow(footer, 2); Grid.SetColumnSpan(footer, 3); layout.Children.Add(footer);
        root.Children.Add(layout); Content = root;
        RefreshTemplates();
    }

    private void Browse_Click(object sender, RoutedEventArgs e)
    {
        using var picker = new System.Windows.Forms.FolderBrowserDialog { Description = "Choose a local repository or project folder", UseDescriptionForTitle = true };
        if (Directory.Exists(_project.Text)) picker.SelectedPath = _project.Text;
        if (picker.ShowDialog() != System.Windows.Forms.DialogResult.OK) return;
        _project.Text = picker.SelectedPath; _currentPath = null; _body.Clear(); RefreshTemplates();
    }

    private void RefreshTemplates(string? selectedPath = null)
    {
        _loading = true;
        var entries = new List<TemplateEntry>();
        try
        {
            var root = ProjectRoot();
            EnsureSafeDirectory(root, Path.Combine(root, ".github"));
            var github = Path.Combine(root, ".github");
            AddFiles(entries, "Issue", Path.Combine(github, "ISSUE_TEMPLATE"));
            AddFiles(entries, "Pull request", Path.Combine(github, "PULL_REQUEST_TEMPLATE"));
            if (Directory.Exists(github))
            {
                var rootPr = Directory.EnumerateFiles(github, "*", SearchOption.TopDirectoryOnly)
                    .FirstOrDefault(path => string.Equals(Path.GetFileName(path), "PULL_REQUEST_TEMPLATE.md", StringComparison.OrdinalIgnoreCase));
                if (rootPr is not null && SafeFile(root, rootPr)) entries.Add(new TemplateEntry("Pull request", Path.GetFileName(rootPr), rootPr));
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or ArgumentException or InvalidOperationException)
        {
            _templates.ItemsSource = Array.Empty<TemplateEntry>();
            _loading = false;
            _status.Text = "Could not read templates: " + SecurityBoundaries.Redact(ex.Message);
            return;
        }
        _templates.ItemsSource = entries.OrderBy(item => item.Kind, StringComparer.OrdinalIgnoreCase).ThenBy(item => item.Name, StringComparer.OrdinalIgnoreCase).ToArray();
        if (selectedPath is not null) _templates.SelectedItem = entries.FirstOrDefault(item => string.Equals(item.Path, selectedPath, StringComparison.OrdinalIgnoreCase));
        _loading = false;
        if (selectedPath is null) _status.Text = entries.Count == 0 ? "No Markdown templates were found. Create one to add a file under .github." : $"Found {entries.Count} local Markdown template(s).";
    }

    private void AddFiles(List<TemplateEntry> entries, string kind, string folder)
    {
        var root = ProjectRoot();
        EnsureSafeDirectory(root, folder);
        if (!Directory.Exists(folder)) return;
        foreach (var path in Directory.EnumerateFiles(folder, "*", SearchOption.TopDirectoryOnly)
                     .Where(path => string.Equals(Path.GetExtension(path), ".md", StringComparison.OrdinalIgnoreCase)))
        {
            var info = new FileInfo(path);
            if (!SafeFile(root, path) || info.Length > 1024 * 1024) continue;
            entries.Add(new TemplateEntry(kind, info.Name, path));
        }
    }

    private void LoadTemplate(TemplateEntry entry)
    {
        try
        {
            if (!SafeFile(ProjectRoot(), entry.Path)) throw new InvalidOperationException("Template path is outside the selected project or is linked.");
            var info = new FileInfo(entry.Path);
            if (info.Length > 1024 * 1024) throw new InvalidOperationException("Templates larger than 1 MiB are not opened in this editor.");
            _kind.SelectedItem = entry.Kind; _name.Text = entry.Name; _name.IsReadOnly = true; _kind.IsEnabled = false;
            _body.Text = File.ReadAllText(entry.Path, new UTF8Encoding(false, true)); _currentPath = entry.Path;
            _status.Text = "Editing the selected local file. Save writes only to this file; it does not upload it.";
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidOperationException or ArgumentException)
        { _status.Text = "Could not open template: " + SecurityBoundaries.Redact(ex.Message); }
    }

    private void NewTemplate(string kind, string fileName)
    {
        _templates.SelectedItem = null; _currentPath = null;
        _kind.SelectedItem = kind; _kind.IsEnabled = true;
        _name.IsReadOnly = false; _name.Text = fileName;
        _body.Clear(); _body.Focus();
        _status.Text = "New template draft. Choose a Markdown file name and save to create it locally.";
    }

    private void SaveTemplate_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var root = ProjectRoot();
            var kind = _kind.SelectedItem as string ?? throw new InvalidOperationException("Choose Issue or Pull request.");
            var text = _body.Text;
            if (text.Length > 1024 * 1024) throw new InvalidOperationException("Template content exceeds the 1 MiB editor limit.");
            var target = _currentPath ?? NewTemplatePath(root, kind, _name.Text);
            var safe = SafeTemplatePath(root, target);
            if (_currentPath is null && File.Exists(safe)) throw new InvalidOperationException("That template already exists. Refresh the list and open it before editing.");
            var directory = Path.GetDirectoryName(safe)!;
            Directory.CreateDirectory(directory);
            EnsureSafeDirectory(root, directory);
            if (File.Exists(safe) && !SafeFile(root, safe)) throw new InvalidOperationException("A linked or unsafe file cannot be overwritten.");
            var temp = safe + ".octoship-" + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                using (var writer = new StreamWriter(stream, new UTF8Encoding(false))) { writer.Write(text); writer.Flush(); stream.Flush(true); }
                EnsureSafeDirectory(root, directory);
                if (File.Exists(safe) && !SafeFile(root, safe)) throw new InvalidOperationException("The target became linked or unsafe while saving.");
                File.Move(temp, safe, true);
            }
            finally { if (File.Exists(temp)) File.Delete(temp); }
            _currentPath = safe; _name.IsReadOnly = true; _kind.IsEnabled = false;
            RefreshTemplates(safe);
            _status.Text = "Saved local template. Review the working-tree diff, then publish through the normal upload flow if desired.";
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or ArgumentException or InvalidOperationException)
        { _status.Text = "Could not save template: " + SecurityBoundaries.Redact(ex.Message); }
    }

    private string NewTemplatePath(string root, string kind, string name)
    {
        var file = name.Trim();
        if (file.Length is < 1 or > 100 || file is "." or ".." || Path.GetFileName(file) != file || file.Contains('/') || file.Contains('\\')
            || !file.EndsWith(".md", StringComparison.OrdinalIgnoreCase) || file.Any(char.IsControl))
            throw new ArgumentException("Use a simple Markdown file name such as bug-report.md.");
        var category = kind == "Issue" ? "ISSUE_TEMPLATE" : kind == "Pull request" ? "PULL_REQUEST_TEMPLATE" : throw new ArgumentException("Unsupported template category.");
        return Path.Combine(root, ".github", category, file);
    }

    private string ProjectRoot()
    {
        if (!Directory.Exists(_project.Text)) throw new DirectoryNotFoundException("Choose an existing local project folder.");
        var root = NormalizeRoot(_project.Text);
        if ((File.GetAttributes(root) & FileAttributes.ReparsePoint) != 0) throw new InvalidOperationException("A linked or redirected project root cannot be edited.");
        return root;
    }

    private static void EnsureSafeDirectory(string root, string directory)
    {
        var fullRoot = NormalizeRoot(root);
        var fullDirectory = Path.GetFullPath(directory);
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        var prefix = fullRoot.EndsWith(Path.DirectorySeparatorChar) ? fullRoot : fullRoot + Path.DirectorySeparatorChar;
        if (!fullDirectory.Equals(fullRoot, comparison) && !fullDirectory.StartsWith(prefix, comparison))
            throw new InvalidOperationException("Template directory escapes the selected project folder.");
        var current = fullDirectory;
        while (current.Length >= fullRoot.Length)
        {
            if (Directory.Exists(current) && (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidOperationException("A linked template directory cannot be read or changed.");
            if (current.Equals(fullRoot, comparison)) break;
            current = Path.GetDirectoryName(current) ?? fullRoot;
        }
    }

    private static string SafeTemplatePath(string root, string target)
    {
        var full = Path.GetFullPath(target);
        root = NormalizeRoot(root);
        EnsureSafeDirectory(root, Path.GetDirectoryName(full)!);
        if (!full.Contains(Path.DirectorySeparatorChar + ".github" + Path.DirectorySeparatorChar, OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal))
            throw new InvalidOperationException("Templates must be stored under the selected project's .github directory.");
        return full;
    }

    private static string NormalizeRoot(string path)
    {
        var full = Path.GetFullPath(path);
        var volumeRoot = Path.GetPathRoot(full) ?? "";
        return full.Length > volumeRoot.Length ? full.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) : volumeRoot;
    }

    private static bool SafeFile(string root, string path)
    {
        var full = SafeTemplatePath(root, path);
        return File.Exists(full) && (File.GetAttributes(full) & FileAttributes.ReparsePoint) == 0;
    }
}
