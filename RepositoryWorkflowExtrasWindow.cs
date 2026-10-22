using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Microsoft.Win32;

namespace FileToGitHub;

/// <summary>Repository query, issue, branch, tag, setup, and release maintenance workflows.</summary>
public sealed class RepositoryWorkflowExtrasWindow : Window
{
    private readonly HttpClient _http;
    private readonly string _repo, _token;
    private readonly CancellationTokenSource _life = new();
    private readonly TextBlock _status = new() { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 8) };
    private readonly ComboBox _queryKind = new(), _savedQueries = new();
    private readonly TextBox _queryText = new(), _issueTitle = new(), _issueBody = new(), _issuePath = new(), _linkIssue = new(), _reviewPr = new(), _reviewers = new(), _teams = new(), _tag = new(), _setupName = new(), _setupDescription = new(), _releaseOne = new(), _releaseTwo = new();
    private readonly CheckBox _readme = new() { Content = "Add README.md" }, _license = new() { Content = "Add MIT LICENSE" }, _ignore = new() { Content = "Add .gitignore for .NET" };
    private readonly ListBox _results = new(), _branches = new(), _tags = new(), _releases = new();
    private readonly DataGrid _grid = new() { IsReadOnly = true, AutoGenerateColumns = true, CanUserAddRows = false, MinHeight = 170, MaxHeight = 400 };
    private readonly List<SavedQuery> _saved = new();
    private IReadOnlyList<BranchInfo> _branchData = Array.Empty<BranchInfo>();
    private IReadOnlyList<TagInfo> _tagData = Array.Empty<TagInfo>();
    private IReadOnlyList<ReleaseInfo> _releaseData = Array.Empty<ReleaseInfo>();
    private string _defaultBranch = "main";
    private string Root => "https://api.github.com/repos/" + string.Join("/", _repo.Split('/').Select(Uri.EscapeDataString));
    private string SavedFile => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShip", "saved-repository-queries.json");

    private sealed record SavedQuery(string Repository, string Name, string Kind, string Query);
    private sealed record BranchInfo(string Name, string Sha, bool Protected, DateTimeOffset? Updated, bool HasOpenPullRequest)
    { public string Summary => $"{Name} | {(Protected ? "protected" : "unprotected")} | {(HasOpenPullRequest ? "open PR" : "no open PR")} | {(Updated?.ToLocalTime().ToString("d") ?? "date unavailable")}"; }
    private sealed record TagInfo(string Name, string Sha);
    private sealed record ReleaseInfo(long Id, string Tag, string Name, string Body, bool Draft, string Url, IReadOnlyList<AssetInfo> Assets);
    private sealed record AssetInfo(long Id, string Name, long Size, string Url, string Digest);

    public RepositoryWorkflowExtrasWindow(HttpClient http, string repository, string token)
    {
        UniformUi.Prepare(this); _http = http; _repo = repository; _token = token;
        RepositoryWorkflowService.ValidateRepository(repository);
        Title = repository + " | Repository workflows"; Width = 980; Height = 820; MinWidth = 760; MinHeight = 600;
        Background = new SolidColorBrush(Color.FromRgb(16, 21, 30)); Foreground = Brushes.WhiteSmoke;
        var root = new DockPanel { Margin = new Thickness(16) }; Content = root;
        var header = new StackPanel(); DockPanel.SetDock(header, Dock.Top); root.Children.Add(header);
        header.Children.Add(new TextBlock { Text = "Repository workflows", FontSize = 22, FontWeight = FontWeights.SemiBold });
        header.Children.Add(new TextBlock { Text = repository + "  ·  Writes require a separate confirmation", Margin = new Thickness(0, 4, 0, 0) });
        _status.Foreground = Brushes.LightSteelBlue; header.Children.Add(_status);
        var tabs = new TabControl(); root.Children.Add(tabs);
        tabs.Items.Add(Tab("Saved queries", BuildQueries()));
        tabs.Items.Add(Tab("Issue triage", BuildIssues()));
        tabs.Items.Add(Tab("Link issue", BuildLinks()));
        tabs.Items.Add(Tab("PR reviewers", BuildReviewers()));
        tabs.Items.Add(Tab("Branch cleanup", BuildBranches()));
        tabs.Items.Add(Tab("Tags", BuildTags()));
        tabs.Items.Add(Tab("New repository", BuildSetup()));
        tabs.Items.Add(Tab("Release repair", BuildRepair()));
        tabs.Items.Add(Tab("Compare releases", BuildReleaseCompare()));
        LoadSaved();
        Loaded += async (_, _) => { try { await LoadRepoInfoAsync(); } catch (Exception ex) { Status("Repository details unavailable: " + ex.Message, true); } };
        Closed += (_, _) => _life.Cancel();
    }

    private UIElement BuildQueries()
    {
        var p = Panel(); p.Children.Add(Note("Save repository-scoped searches for pull requests, issues, and workflow runs. Search results come from GitHub and reflect the selected query at load time."));
        _queryKind.ItemsSource = new[] { "Pull requests", "Issues", "Workflow runs" }; _queryKind.SelectedIndex = 0; p.Children.Add(Row("Type", _queryKind)); p.Children.Add(Row("GitHub search terms", _queryText));
        p.Children.Add(Button("Run query", RunQueryAsync)); p.Children.Add(Button("Save query", SaveQueryAsync)); p.Children.Add(Row("Saved queries", _savedQueries)); p.Children.Add(Button("Run selected saved query", RunSavedQueryAsync));
        _results.Height = 320; p.Children.Add(_results); return Scroll(p);
    }
    private UIElement BuildIssues()
    {
        var p = Panel(); p.Children.Add(Note("Triage open issues by state, labels, assignee, and age. Selecting an item shows its GitHub URL and available metadata; no issue is changed by this view."));
        p.Children.Add(Row("Search (optional)", _queryText)); p.Children.Add(Button("Load open issues", async () => await LoadIssuesAsync())); p.Children.Add(_grid); return Scroll(p);
    }
    private UIElement BuildLinks()
    {
        var p = Panel(); p.Children.Add(Note("Create an issue with a file path in its body, then preview milestone and classic project links for an existing issue. Review the path before submitting; a local absolute path can disclose your Windows user or folder names."));
        p.Children.Add(Row("File or repository path", _issuePath)); p.Children.Add(Button("Choose local file", () => { var d = new OpenFileDialog(); if (d.ShowDialog(this) == true) _issuePath.Text = d.FileName; return Task.CompletedTask; }));
        p.Children.Add(Row("Issue title", _issueTitle)); p.Children.Add(Row("Issue body", _issueBody)); p.Children.Add(Button("Create issue from file (review and confirm)", CreateIssueAsync));
        p.Children.Add(new Separator { Margin = new Thickness(0, 12, 0, 8) }); p.Children.Add(Row("Existing issue number", _linkIssue));
        p.Children.Add(Button("Preview milestone and project link", PreviewLinksAsync)); p.Children.Add(Button("Apply selected milestone link", ApplyMilestoneAsync)); p.Children.Add(Button("Add issue to selected classic project", AddProjectCardAsync)); return Scroll(p);
    }
    private UIElement BuildReviewers()
    {
        var p = Panel(); p.Children.Add(Note("Request reviewers on an open pull request. GitHub requires write access; team names use the team slug."));
        p.Children.Add(Row("Pull request number", _reviewPr)); p.Children.Add(Row("Users, comma separated", _reviewers)); p.Children.Add(Row("Team slugs, comma separated", _teams)); p.Children.Add(Button("Load pull requests", LoadPullRequestsForReviewAsync)); p.Children.Add(_results); p.Children.Add(Button("Review request and submit", RequestReviewersAsync)); return Scroll(p);
    }
    private UIElement BuildBranches()
    {
        var p = Panel(); p.Children.Add(Note("Preview candidates that are unprotected, older than 90 days, and have no open pull request. Branch deletion is permanent on GitHub and requires a final confirmation."));
        p.Children.Add(Button("Build stale branch preview", LoadStaleBranchesAsync)); p.Children.Add(_branches); p.Children.Add(Button("Delete selected branch (confirm)", DeleteBranchAsync)); return Scroll(p);
    }
    private UIElement BuildTags()
    {
        var p = Panel(); p.Children.Add(Note("Browse repository tags, create a tag at a reviewed branch or commit SHA, or delete a tag after confirmation."));
        p.Children.Add(Button("Refresh tags", LoadTagsAsync)); p.Children.Add(_tags); p.Children.Add(Row("New tag name", _tag)); p.Children.Add(Row("Target branch or commit SHA", _issuePath)); p.Children.Add(Button("Create tag (confirm)", CreateTagAsync)); p.Children.Add(Button("Delete selected tag (confirm)", DeleteTagAsync)); return Scroll(p);
    }
    private UIElement BuildSetup()
    {
        var p = Panel(); p.Children.Add(Note("Create a repository under the signed-in account. Choose initial files; OctoShip previews the contents and asks before creating the remote repository."));
        p.Children.Add(Row("Repository name", _setupName)); p.Children.Add(Row("Description", _setupDescription)); p.Children.Add(_readme); p.Children.Add(_license); p.Children.Add(_ignore); p.Children.Add(Button("Preview and create repository", CreateRepositoryAsync)); return Scroll(p);
    }
    private UIElement BuildRepair()
    {
        var p = Panel(); p.Children.Add(Note("Inspect a draft release's assets against selected local files. Missing names can be uploaded; same-name assets with a different size can be replaced after explicit confirmation."));
        p.Children.Add(Button("Load draft releases", LoadReleasesAsync)); p.Children.Add(_releases); p.Children.Add(Button("Choose local repair asset", () => { var d = new OpenFileDialog(); if (d.ShowDialog(this) == true) _issuePath.Text = d.FileName; return Task.CompletedTask; }));
        p.Children.Add(Button("Preview asset match", PreviewAssetRepairAsync)); p.Children.Add(Button("Upload or replace selected asset (confirm)", RepairAssetAsync)); return Scroll(p);
    }
    private UIElement BuildReleaseCompare()
    {
        var p = Panel(); p.Children.Add(Note("Compare two repository releases by tag, notes, and asset filename, size, and GitHub-provided digest. Missing digest values are reported as unavailable."));
        p.Children.Add(Button("Load releases", LoadReleasesAsync)); p.Children.Add(Row("First release tag", _releaseOne)); p.Children.Add(Row("Second release tag", _releaseTwo)); p.Children.Add(Button("Compare releases", CompareReleasesAsync)); p.Children.Add(_results); return Scroll(p);
    }

    private async Task RunQueryAsync()
    {
        var query = _queryText.Text.Trim(); var kind = _queryKind.SelectedItem?.ToString() ?? "Pull requests";
        if (string.IsNullOrWhiteSpace(query)) { Status("Enter GitHub search terms, such as is:open label:bug.", true); return; }
        try
        {
            var (route, q) = kind switch
            {
                "Pull requests" => ("issues", $"repo:{_repo} is:pr {query}"),
                "Issues" => ("issues", $"repo:{_repo} is:issue {query}"),
                _ => ("actions/runs", query)
            };
            using var doc = await GetAsync(route == "actions/runs" ? $"{Root}/actions/runs?per_page=50" : "https://api.github.com/search/issues?q=" + Uri.EscapeDataString(q) + "&per_page=50");
            var arr = route == "actions/runs" ? doc.RootElement.GetProperty("workflow_runs") : doc.RootElement.GetProperty("items");
            var terms = query.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Where(x => !x.Contains(':')).ToArray();
            var rows = arr.EnumerateArray().Where(x => route != "actions/runs" || terms.Length == 0 || terms.All(term => (S(x,"name") + " " + S(x,"head_branch") + " " + S(x,"status") + " " + S(x,"conclusion")).Contains(term, StringComparison.OrdinalIgnoreCase))).ToArray();
            _results.ItemsSource = rows.Select(x => route == "actions/runs" ? $"#{S(x,"run_number")} {S(x,"name")} | {S(x,"head_branch")} | {S(x,"status")} {S(x,"conclusion")} | {S(x,"html_url")}" : $"#{S(x,"number")} {S(x,"title")} | {S(x,"state")} | {S(x,"html_url")}").ToArray();
            Status($"Loaded {_results.Items.Count} result(s) from GitHub.");
        }
        catch (Exception ex) { Status("Query failed: " + ex.Message, true); }
    }
    private Task SaveQueryAsync()
    {
        var text = _queryText.Text.Trim(); var kind = _queryKind.SelectedItem?.ToString() ?? "Pull requests";
        if (text.Length == 0) { Status("Enter a query before saving it.", true); return Task.CompletedTask; }
        var name = Microsoft.VisualBasic.Interaction.InputBox("Name this saved query", "Save repository query", kind + " · " + text);
        if (string.IsNullOrWhiteSpace(name)) return Task.CompletedTask;
        _saved.RemoveAll(x => string.Equals(x.Repository, _repo, StringComparison.OrdinalIgnoreCase) && string.Equals(x.Name, name.Trim(), StringComparison.OrdinalIgnoreCase)); _saved.Add(new(_repo, name.Trim(), kind, text));
        try { Directory.CreateDirectory(Path.GetDirectoryName(SavedFile)!); File.WriteAllText(SavedFile, JsonSerializer.Serialize(_saved, new JsonSerializerOptions { WriteIndented = true })); RefreshSaved(); Status("Saved query locally on this Windows account."); }
        catch (Exception ex) { Status("Could not save the query locally: " + ex.Message, true); }
        return Task.CompletedTask;
    }
    private async Task RunSavedQueryAsync() { if (_savedQueries.SelectedItem is not SavedQuery q) { Status("Select a saved query first.", true); return; } _queryKind.SelectedItem = q.Kind; _queryText.Text = q.Query; await RunQueryAsync(); }
    private async Task LoadIssuesAsync()
    {
        try
        {
            var extra = _queryText.Text.Trim(); var q = $"repo:{_repo} is:issue is:open {extra}";
            using var d = await GetAsync("https://api.github.com/search/issues?q=" + Uri.EscapeDataString(q) + "&per_page=100");
            var rows = d.RootElement.GetProperty("items").EnumerateArray().Select(x => new { Number = I(x,"number"), Title = S(x,"title"), State = S(x,"state"), Labels = string.Join(", ", x.GetProperty("labels").EnumerateArray().Select(l => S(l,"name"))), Assignee = x.TryGetProperty("assignee",out var a)&&a.ValueKind==JsonValueKind.Object?S(a,"login"):"unassigned", Updated = S(x,"updated_at"), Url = S(x,"html_url") }).ToArray();
            _grid.ItemsSource = rows; Status($"Loaded {rows.Length} open issue(s). Search ranking and metadata are from GitHub.");
        }
        catch (Exception ex) { Status("Issue triage unavailable: " + ex.Message, true); }
    }
    private async Task CreateIssueAsync()
    {
        var title = _issueTitle.Text.Trim(); var path = _issuePath.Text.Trim(); if (title.Length == 0 || path.Length == 0) { Status("Provide an issue title and file path.", true); return; }
        var body = _issueBody.Text; body += (body.Length == 0 ? "" : "\n\n") + "Related file: `" + path.Replace("`", "") + "`";
        if (!Confirm($"Create issue in {_repo}?\n\nTitle: {title}\nFile/path: {path}\n\nThe issue body will be sent to GitHub.", "Create issue")) return;
        try { using var d = await SendJsonAsync(HttpMethod.Post, $"{Root}/issues", new { title, body }); Status("Issue created: " + S(d.RootElement,"html_url")); }
        catch (Exception ex) { Status("Issue create result may be uncertain. Inspect GitHub before retrying. " + ex.Message, true); }
    }
    private async Task PreviewLinksAsync()
    {
        if (!int.TryParse(_linkIssue.Text, out var number)) { Status("Enter an issue number.", true); return; }
        try
        {
            using var issue = await GetAsync($"{Root}/issues/{number}");
            using var milestones = await GetAsync($"{Root}/milestones?state=open&per_page=100");
            using var projects = await GetAsync($"{Root}/projects?state=open&per_page=100");
            var m = milestones.RootElement.EnumerateArray().Select(x => $"#{I(x,"number")} {S(x,"title")} ({I(x,"open_issues")} open)").ToArray();
            var p = projects.RootElement.EnumerateArray().Select(x => $"#{I(x,"id")} {S(x,"name")} (classic project)").ToArray();
            _results.ItemsSource = new[] { $"Issue #{number}: {S(issue.RootElement,"title")}", "Milestones: " + (m.Length == 0 ? "none available" : string.Join("; ",m)), "Projects: " + (p.Length == 0 ? "none available or API disabled" : string.Join("; ",p)), "Choose milestone/project through the controls before applying." };
            Status("Link preview loaded. Projects API availability depends on repository settings and token scopes.");
        }
        catch (Exception ex) { Status("Link preview failed: " + ex.Message + ". GitHub Projects v2 is not exposed by this classic project API.", true); }
    }
    private async Task ApplyMilestoneAsync()
    {
        if (!int.TryParse(_linkIssue.Text,out var issue)) { Status("Enter an issue number.",true); return; }
        try
        {
            using var ms = await GetAsync($"{Root}/milestones?state=open&per_page=100"); var list=ms.RootElement.EnumerateArray().ToArray();
            if(list.Length==0){Status("No open milestones are available.",true);return;}
            var choices=list.Select(x=>$"{I(x,"number")} | {S(x,"title")}").ToArray(); var chosen=Pick("Choose milestone number",choices); if(!int.TryParse(chosen?.Split('|')[0].Trim(),out var milestone))return;
            if(!Confirm($"Set issue #{issue} to milestone #{milestone}?","Apply milestone"))return;
            using var result=await SendJsonAsync(HttpMethod.Patch,$"{Root}/issues/{issue}",new{milestone}); Status($"Issue #{issue} milestone updated. GitHub returned: {S(result.RootElement,"html_url")}");
        }catch(Exception ex){Status("Milestone update failed or is uncertain: "+ex.Message,true);}
    }
    private async Task AddProjectCardAsync()
    {
        if (!int.TryParse(_linkIssue.Text,out var issue)) { Status("Enter an issue number.",true); return; }
        try
        {
            using var d=await GetAsync($"{Root}/projects?state=open&per_page=100"); var list=d.RootElement.EnumerateArray().ToArray(); if(list.Length==0){Status("No classic projects returned. GitHub Projects v2 uses GraphQL and is not available in this classic project workflow.",true);return;}
            var choices=list.Select(x=>$"{I(x,"id")} | {S(x,"name")}").ToArray(); var chosen=Pick("Choose classic project",choices); if(!long.TryParse(chosen?.Split('|')[0].Trim(),out var id))return;
            using var cols=await GetAsync($"https://api.github.com/projects/{id}/columns?per_page=100");var columns=cols.RootElement.EnumerateArray().ToArray();if(columns.Length==0){Status("Selected project has no columns.",true);return;}var columnChoices=columns.Select(x=>$"{L(x,"id")} | {S(x,"name")}").ToArray();var selectedColumn=Pick("Choose project column",columnChoices);if(!long.TryParse(selectedColumn?.Split('|')[0].Trim(),out var columnId))return;var column=columns.First(x=>L(x,"id")==columnId);
            if(!Confirm($"Add issue #{issue} to project '{S(column,"name")}'?","Add issue to project"))return;
            using var card=await SendJsonAsync(HttpMethod.Post,$"https://api.github.com/projects/columns/{L(column,"id")}/cards",new{content_id=await IssueIdAsync(issue),content_type="Issue"});Status("GitHub added the issue to the selected classic project column.");
        }catch(Exception ex){Status("Project link failed or is uncertain: "+ex.Message,true);}
    }
    private async Task<long> IssueIdAsync(int issue){using var d=await GetAsync($"{Root}/issues/{issue}");return L(d.RootElement,"id");}
    private async Task LoadPullRequestsForReviewAsync()
    {
        try{using var d=await GetAsync($"{Root}/pulls?state=open&per_page=100");var rows=d.RootElement.EnumerateArray().Select(x=>$"#{I(x,"number")} {S(x,"title")} | @{S(x,"user","login")} | {S(x,"html_url")}").ToArray();_results.ItemsSource=rows;Status($"Loaded {rows.Length} open pull request(s).");}catch(Exception ex){Status("Could not load pull requests: "+ex.Message,true);}
    }
    private async Task RequestReviewersAsync()
    {
        if(!int.TryParse(_reviewPr.Text,out var pr)){Status("Enter a pull request number.",true);return;}
        var users=_reviewers.Text.Split(',',StringSplitOptions.RemoveEmptyEntries|StringSplitOptions.TrimEntries);var teams=_teams.Text.Split(',',StringSplitOptions.RemoveEmptyEntries|StringSplitOptions.TrimEntries);if(users.Length+teams.Length==0||users.Concat(teams).Any(x=>x.Length>100||x.Any(char.IsControl))){Status("Enter one or more valid usernames or team slugs.",true);return;}
        if(!Confirm($"Request review on PR #{pr} from users: {string.Join(", ",users)}; teams: {string.Join(", ",teams)}?","Request reviewers"))return;
        try{using var d=await SendJsonAsync(HttpMethod.Post,$"{Root}/pulls/{pr}/requested_reviewers",new{reviewers=users,team_reviewers=teams});Status($"GitHub accepted the reviewer request for PR #{pr}. Returned reviewer count: {(d.RootElement.TryGetProperty("requested_reviewers",out var a)?a.GetArrayLength():0)}; team count: {(d.RootElement.TryGetProperty("team_reviewers",out var t)?t.GetArrayLength():0)}.");}catch(Exception ex){Status("Reviewer request failed or is uncertain: "+ex.Message,true);}
    }
    private async Task LoadStaleBranchesAsync()
    {
        try
        {
            using var repo=await GetAsync(Root);_defaultBranch=S(repo.RootElement,"default_branch");
            using var bs=await GetAsync($"{Root}/branches?per_page=100");using var prs=await GetAsync($"{Root}/pulls?state=open&per_page=100");var open=prs.RootElement.EnumerateArray().Select(x=>S(x,"head","ref")).ToHashSet(StringComparer.OrdinalIgnoreCase);
            var rows=new List<BranchInfo>();foreach(var b in bs.RootElement.EnumerateArray()) {var name=S(b,"name");if(name==_defaultBranch)continue;var sha=S(b,"commit","sha");DateTimeOffset? updated=null;try{using var commit=await GetAsync($"{Root}/commits/{Uri.EscapeDataString(sha)}");if(DateTimeOffset.TryParse(S(commit.RootElement,"commit","committer","date"),out var dt))updated=dt;}catch{} rows.Add(new(name,sha,B(b,"protected"),updated,open.Contains(name)));}
            _branchData=rows;var candidates=rows.Where(x=>!x.Protected&&!x.HasOpenPullRequest&&x.Updated.HasValue&&x.Updated.Value<DateTimeOffset.UtcNow.AddDays(-90)).ToArray();_branches.ItemsSource=candidates;Status($"Found {candidates.Length} deletion candidate(s) out of {rows.Count} branches. GitHub reports commit author time; merged state is not inferred.");
        }catch(Exception ex){Status("Branch preview failed: "+ex.Message,true);}
    }
    private async Task DeleteBranchAsync()
    {
        if(_branches.SelectedItem is not BranchInfo b){Status("Select a candidate branch.",true);return;}if(b.Protected||b.HasOpenPullRequest||b.Name==_defaultBranch){Status("This branch is no longer eligible. Refresh the preview.",true);return;}
        if(!Confirm($"Permanently delete branch '{b.Name}' from {_repo}? Confirm the branch and repository carefully.","Delete remote branch"))return;
        try{using var r=await SendAsync(HttpMethod.Delete,$"{Root}/git/refs/heads/{Uri.EscapeDataString(b.Name)}");Status("GitHub accepted the branch deletion request. Refresh branch list to verify its current state.");await LoadStaleBranchesAsync();}catch(Exception ex){Status("Delete outcome may be uncertain. Refresh GitHub before retrying. "+ex.Message,true);}
    }
    private async Task LoadTagsAsync(){try{using var d=await GetAsync($"{Root}/tags?per_page=100");_tagData=d.RootElement.EnumerateArray().Select(x=>new TagInfo(S(x,"name"),S(x,"commit","sha"))).ToArray();_tags.ItemsSource=_tagData.Select(x=>$"{x.Name} | {x.Sha[..Math.Min(8,x.Sha.Length)]}").ToArray();Status($"Loaded {_tagData.Count} tag(s).");}catch(Exception ex){Status("Tags unavailable: "+ex.Message,true);}}
    private async Task CreateTagAsync()
    {
        var name=_tag.Text.Trim();var target=_issuePath.Text.Trim();if(name.Length==0||target.Length==0){Status("Enter a tag name and target branch or commit SHA.",true);return;}
        try{using var d=await GetAsync($"{Root}/commits/{Uri.EscapeDataString(target)}");var sha=S(d.RootElement,"sha");if(sha.Length<40){Status("GitHub did not return a full commit SHA.",true);return;}if(!Confirm($"Create lightweight tag '{name}' at commit {sha} in {_repo}?","Create tag"))return;using var r=await SendJsonAsync(HttpMethod.Post,$"{Root}/git/refs",new{ @ref="refs/tags/"+name,sha});Status("GitHub accepted tag creation. Refresh tags to verify.");await LoadTagsAsync();}catch(Exception ex){Status("Tag creation failed or is uncertain: "+ex.Message,true);}
    }
    private async Task DeleteTagAsync()
    {
        var i=_tags.SelectedIndex;if(i<0||i>=_tagData.Count){Status("Select a tag first.",true);return;}var tag=_tagData[i];if(!Confirm($"Delete tag '{tag.Name}' from {_repo}? This removes its Git ref.","Delete tag"))return;
        try{using var d=await SendAsync(HttpMethod.Delete,$"{Root}/git/refs/tags/{string.Join("/",tag.Name.Split('/').Select(Uri.EscapeDataString))}");Status("GitHub accepted tag deletion. Refresh tags to verify.");await LoadTagsAsync();}catch(Exception ex){Status("Tag delete outcome may be uncertain: "+ex.Message,true);}
    }
    private async Task CreateRepositoryAsync()
    {
        var name=_setupName.Text.Trim();if(name.Length==0||name.Any(c=>!(char.IsLetterOrDigit(c)||c is '-' or '_'))){Status("Repository name may contain letters, numbers, hyphens, and underscores.",true);return;}
        var files=new List<string>();if(_readme.IsChecked==true)files.Add("README.md");if(_license.IsChecked==true)files.Add("LICENSE");if(_ignore.IsChecked==true)files.Add(".gitignore");
        var preview=string.Join(Environment.NewLine,files.Select(f=>"  "+f));if(!Confirm($"Create private repository '{name}' under the signed-in account with these initial files?\n\n{(preview.Length==0?"No files":"Files:\n"+preview)}\n\nDescription: {_setupDescription.Text}","Create repository"))return;
        try
        {
            using var created=await SendJsonAsync(HttpMethod.Post,"https://api.github.com/user/repos",new{name,description=_setupDescription.Text.Trim(),@private=true,auto_init=false});var owner=S(created.RootElement,"owner","login");var full=S(created.RootElement,"full_name");var repoRoot="https://api.github.com/repos/"+string.Join("/",full.Split('/').Select(Uri.EscapeDataString));
            var initial=new Dictionary<string,string>();if(_readme.IsChecked==true)initial["README.md"]=$"# {name}\n\n{_setupDescription.Text.Trim()}\n";if(_license.IsChecked==true)initial["LICENSE"]="MIT License\n\nCopyright (c) "+DateTime.Now.Year+" "+owner+"\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files, to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies.\n\nTHE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND.\n";if(_ignore.IsChecked==true)initial[".gitignore"]="bin/\nobj/\n.vs/\n*.user\n";
            foreach(var f in initial)using(var response=await SendJsonAsync(HttpMethod.Put,$"{repoRoot}/contents/{Uri.EscapeDataString(f.Key)}",new{message="Add initial "+f.Key,content=Convert.ToBase64String(Encoding.UTF8.GetBytes(f.Value))})){}
            Status("Repository created: "+S(created.RootElement,"html_url")+". Initial file requests completed; verify the repository on GitHub.");
        }catch(Exception ex){Status("Repository creation may have partially completed. Inspect GitHub before retrying. "+ex.Message,true);}
    }
    private async Task LoadReleasesAsync()
    {
        try{using var d=await GetAsync($"{Root}/releases?per_page=100");_releaseData=d.RootElement.EnumerateArray().Select(x=>new ReleaseInfo(L(x,"id"),S(x,"tag_name"),S(x,"name"),S(x,"body"),B(x,"draft"),S(x,"html_url"),x.TryGetProperty("assets",out var assets)&&assets.ValueKind==JsonValueKind.Array?assets.EnumerateArray().Select(a=>new AssetInfo(L(a,"id"),S(a,"name"),L(a,"size"),S(a,"browser_download_url"),S(a,"digest"))).ToArray():Array.Empty<AssetInfo>())).ToArray();var drafts=_releaseData.Where(x=>x.Draft).ToArray();_releases.ItemsSource=drafts;Status($"Loaded {drafts.Length} draft release(s). Select one for repair; comparison tab can use any loaded release.");}catch(Exception ex){Status("Draft releases unavailable: "+ex.Message,true);}
    }
    private ReleaseInfo? SelectedRelease()=>_releases.SelectedItem as ReleaseInfo;
    private async Task PreviewAssetRepairAsync()
    {
        var rel=SelectedRelease();var path=_issuePath.Text;if(rel==null||!File.Exists(path)){Status("Select a draft release and a local file.",true);return;}var name=Path.GetFileName(path);var existing=rel.Assets.FirstOrDefault(x=>string.Equals(x.Name,name,StringComparison.OrdinalIgnoreCase));var size=new FileInfo(path).Length;
        _results.ItemsSource=new[]{"Release: "+rel.Tag,"Local file: "+name+" ("+size+" bytes)",existing==null?"Status: missing asset; upload will add it.":$"Status: same-name asset exists ({existing.Size} bytes); replacement requires deleting old asset before upload.","SHA256 local: "+Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(path)))}; Status("Repair preview ready. A local size/hash comparison cannot verify remote file contents when GitHub digest is unavailable.");
    }
    private async Task RepairAssetAsync()
    {
        var rel=SelectedRelease();var path=_issuePath.Text;if(rel==null||!File.Exists(path)){Status("Select a draft release and a local file.",true);return;}var name=Path.GetFileName(path);if(!rel.Draft){Status("Only draft releases can be repaired through this workflow.",true);return;}var old=rel.Assets.FirstOrDefault(x=>string.Equals(x.Name,name,StringComparison.OrdinalIgnoreCase));
        if(!Confirm(old==null?$"Upload '{name}' to draft {rel.Tag}?":$"Delete existing '{name}' asset and upload the selected local file to draft {rel.Tag}? The old asset will be removed first.","Repair draft release asset"))return;
        try{if(old!=null)using(await SendAsync(HttpMethod.Delete,$"{Root}/releases/assets/{old.Id}")){}var owner=_repo.Split('/')[0];var repo=_repo.Split('/')[1];var svc=new GitHubReleaseService(_http);await svc.UploadAssetAsync(owner,repo,_token,rel.Id,path,_life.Token);Status("Asset upload request succeeded. Refresh release details on GitHub to verify the resulting asset.");await LoadReleasesAsync();}catch(Exception ex){Status("Asset repair may have partially completed. Inspect the draft before retrying. "+ex.Message,true);}
    }
    private async Task CompareReleasesAsync()
    {
        if(_releaseData.Count==0)await LoadReleasesAsync();var a=_releaseData.FirstOrDefault(x=>x.Tag==_releaseOne.Text.Trim());var b=_releaseData.FirstOrDefault(x=>x.Tag==_releaseTwo.Text.Trim());if(a==null||b==null){Status("Enter two tags from the loaded releases.",true);return;}
        var aa=a.Assets.ToDictionary(x=>x.Name,StringComparer.OrdinalIgnoreCase);var bb=b.Assets.ToDictionary(x=>x.Name,StringComparer.OrdinalIgnoreCase);var names=aa.Keys.Union(bb.Keys,StringComparer.OrdinalIgnoreCase).OrderBy(x=>x,StringComparer.OrdinalIgnoreCase);var lines=new List<string>{$"{a.Tag} vs {b.Tag}",$"Compatibility notes for {a.Tag}: {CompatibilityNotes(a.Body)}",$"Compatibility notes for {b.Tag}: {CompatibilityNotes(b.Body)}","Assets:"};foreach(var n in names){var left=aa.GetValueOrDefault(n);var right=bb.GetValueOrDefault(n);lines.Add(left==null?$"+ {n} ({right!.Size} bytes, digest {ShowDigest(right.Digest)})":right==null?$"- {n} ({left.Size} bytes, digest {ShowDigest(left.Digest)})":$"= {n} | {left.Size} -> {right.Size} bytes | digest {ShowDigest(left.Digest)} -> {ShowDigest(right.Digest)}");}
        _results.ItemsSource=lines;Status($"Compared {aa.Count} asset(s) with {bb.Count} asset(s). GitHub reports digest only when available.");
    }

    private async Task LoadRepoInfoAsync(){using var d=await GetAsync(Root);_defaultBranch=S(d.RootElement,"default_branch");Status($"Default branch: {_defaultBranch}; repository API read succeeded.");}
    private void LoadSaved(){try{if(File.Exists(SavedFile))_saved.AddRange(JsonSerializer.Deserialize<List<SavedQuery>>(File.ReadAllText(SavedFile))??new());}catch{}RefreshSaved();}
    private void RefreshSaved()=>_savedQueries.ItemsSource=_saved.Where(x=>string.Equals(x.Repository,_repo,StringComparison.OrdinalIgnoreCase)).ToArray();
    private async Task<JsonDocument> GetAsync(string route)=>await SendAsync(HttpMethod.Get,route);
    private async Task<JsonDocument> SendJsonAsync(HttpMethod method,string route,object body){var req=Make(method,route);req.Content=new StringContent(JsonSerializer.Serialize(body),Encoding.UTF8,"application/json");return await SendAsync(req);}
    private async Task<JsonDocument> SendAsync(HttpMethod method,string route){var req=Make(method,route);return await SendAsync(req);}
    private async Task<JsonDocument> SendAsync(HttpRequestMessage req)
    {
        using(req){using var res=await _http.SendAsync(req,_life.Token);var text=await res.Content.ReadAsStringAsync(_life.Token);if(!res.IsSuccessStatusCode)throw new HttpRequestException($"GitHub returned HTTP {(int)res.StatusCode}: {Short(text)}",null,res.StatusCode);return text.Length==0?JsonDocument.Parse("{}") : JsonDocument.Parse(text);}
    }
    private HttpRequestMessage Make(HttpMethod method,string route){if(string.IsNullOrWhiteSpace(_token)||_token.Any(char.IsControl))throw new InvalidOperationException("Sign in to GitHub first.");var url=route.StartsWith("https://",StringComparison.OrdinalIgnoreCase)?route:"https://api.github.com"+route;var r=new HttpRequestMessage(method,url);r.Headers.Authorization=new AuthenticationHeaderValue("Bearer",_token);r.Headers.UserAgent.ParseAdd("OctoShip-for-GitHub/1.6");r.Headers.Accept.ParseAdd("application/vnd.github+json");r.Headers.Add("X-GitHub-Api-Version","2022-11-28");return r;}
    private bool Confirm(string text,string title)=>OctoShipDialog.Show(this,text,title,MessageBoxButton.YesNo,MessageBoxImage.Warning,MessageBoxResult.No)==MessageBoxResult.Yes;
    private string? Pick(string title,IReadOnlyList<string> options){var w=new Window{Title=title,Width=500,Height=180,Owner=this,WindowStartupLocation=WindowStartupLocation.CenterOwner,Background=Background};var c=new ComboBox{ItemsSource=options,SelectedIndex=0,Margin=new Thickness(12)};var b=new Button{Content="Use selection",Margin=new Thickness(12),IsDefault=true};w.Content=new StackPanel{Children={c,b}};b.Click+=(_,_)=>w.DialogResult=true;return w.ShowDialog()==true?c.SelectedItem?.ToString():null;}
    private void Status(string text,bool error=false){_status.Text=text;_status.Foreground=error?Brushes.OrangeRed:Brushes.LightSteelBlue;}
    private static string Short(string x)=>x.Length>500?x[..500]:x;
    private static string ShowDigest(string value)=>string.IsNullOrWhiteSpace(value)?"unavailable":value;
    private static string CompatibilityNotes(string body){var matches=body.Split(new[]{'\r','\n'},StringSplitOptions.RemoveEmptyEntries).Where(x=>new[]{"compatib","support","require","windows","linux","macos","runtime"}.Any(k=>x.Contains(k,StringComparison.OrdinalIgnoreCase))).Take(8).ToArray();return matches.Length==0?"no explicit compatibility line found":string.Join(" | ",matches);}
    private static string S(JsonElement x,string p)=>x.TryGetProperty(p,out var v)&&v.ValueKind==JsonValueKind.String?v.GetString()??"":"";
    private static string S(JsonElement x,string p,string c)=>x.TryGetProperty(p,out var v)&&v.TryGetProperty(c,out var z)&&z.ValueKind==JsonValueKind.String?z.GetString()??"":"";
    private static string S(JsonElement x,string p,string c,string d)=>x.TryGetProperty(p,out var v)&&v.TryGetProperty(c,out var w)&&w.TryGetProperty(d,out var z)&&z.ValueKind==JsonValueKind.String?z.GetString()??"":"";
    private static int I(JsonElement x,string p)=>x.TryGetProperty(p,out var v)&&v.TryGetInt32(out var n)?n:0;
    private static long L(JsonElement x,string p)=>x.TryGetProperty(p,out var v)&&v.TryGetInt64(out var n)?n:0;
    private static bool B(JsonElement x,string p)=>x.TryGetProperty(p,out var v)&&v.ValueKind==JsonValueKind.True;
    private static TabItem Tab(string header,UIElement content)=>new(){Header=header,Content=content};
    private static StackPanel Panel()=>new(){Margin=new Thickness(12),Background=Brushes.White};
    private static TextBlock Note(string text)=>new(){Text=text,Foreground=Brushes.Black,TextWrapping=TextWrapping.Wrap,Margin=new Thickness(0,3,0,10)};
    private static UIElement Row(string label,Control c){c.Margin=new Thickness(0,3,0,7);var p=new StackPanel();p.Children.Add(new TextBlock{Text=label,Foreground=Brushes.Black});p.Children.Add(c);return p;}
    private static Button Button(string text,Func<Task> action){var b=new Button{Content=text,Padding=new Thickness(9,6,9,6),Margin=new Thickness(0,4,0,6),HorizontalAlignment=HorizontalAlignment.Left,Foreground=Brushes.Black};b.Click+=async(_,_)=>await action();return b;}
    private static ScrollViewer Scroll(UIElement c)=>new(){Content=c,VerticalScrollBarVisibility=ScrollBarVisibility.Auto};
}
