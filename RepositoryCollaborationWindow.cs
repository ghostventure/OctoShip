using System;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Diagnostics;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace FileToGitHub;

/// <summary>Repository, branch, PR, release, diagnostics and Actions overview.</summary>
public sealed class RepositoryCollaborationWindow : Window
{
    private sealed record BranchChoice(string Name, bool Protected, string Sha)
    { public string Label => $"{Name} | {(Protected ? "protected" : "branch")} | {Sha[..Math.Min(7,Sha.Length)]}"; }
    private readonly GitHubCollaborationService _service;
    private readonly Func<string?> _tokenProvider;
    private readonly CancellationTokenSource _life = new();
    private readonly ComboBox _repositories = new(), _base = new(), _head = new();
    private readonly TextBlock _identity = new(), _status = new();
    private readonly DataGrid _prs = Grid(), _releases = Grid(), _runs = Grid(), _artifacts = Grid();
    private readonly TextBox _report = new() { AcceptsReturn = true, Height = 130, IsReadOnly = true, Text = "Run diagnostics to generate a redacted report." };
    private GitHubCollaborationService.Repo? _repo;

    public RepositoryCollaborationWindow(HttpClient http, Func<string?> tokenProvider, string? selectedRepository = null)
    {
        UniformUi.Prepare(this); _service = new(http); _tokenProvider = tokenProvider;
        Title = "Repository collaboration"; Width = 1000; Height = 790; MinWidth = 760; MinHeight = 580;
        Background = new SolidColorBrush(Color.FromRgb(16,21,30)); Foreground = Brushes.WhiteSmoke; WindowStartupLocation = WindowStartupLocation.CenterOwner;
        var root = new DockPanel { Margin = new Thickness(18) }; Content = root;
        var top = new StackPanel(); DockPanel.SetDock(top,Dock.Top); root.Children.Add(top);
        var title = new TextBlock { Text = "Repository collaboration", FontSize = 22, FontWeight = FontWeights.SemiBold, Margin = new Thickness(0,0,0,10) }; top.Children.Add(title);
        var identityRow = new StackPanel { Orientation = Orientation.Horizontal };
        _repositories.Width=360; _repositories.Margin=new Thickness(0,0,8,0); _repositories.SelectionChanged += async (_,_) => await SelectRepositoryAsync();
        identityRow.Children.Add(_repositories); identityRow.Children.Add(new Button { Content="Refresh repositories", Padding=new Thickness(8) });
        var refreshRepos=(Button)identityRow.Children[1]; refreshRepos.Click += async (_,_) => await LoadRepositoriesAsync(selectedRepository);
        var extrasButton=new Button { Content="Repository workflows", Padding=new Thickness(8), Margin=new Thickness(8,0,0,0) };
        extrasButton.Click += (_,_) => { if(_repo==null){Status("Select a repository first.",true);return;} try{new RepositoryWorkflowExtrasWindow(http,_repo.Name,Token()){Owner=this}.ShowDialog();}catch(Exception ex){Status("Could not open repository workflows: "+ex.Message,true);} };
        identityRow.Children.Add(extrasButton);
        _identity.VerticalAlignment=VerticalAlignment.Center; _identity.Margin=new Thickness(14,0,0,0); identityRow.Children.Add(_identity); top.Children.Add(identityRow);
        _status.TextWrapping=TextWrapping.Wrap; _status.Margin=new Thickness(0,8,0,6); top.Children.Add(_status);
        var tabs=new TabControl(); root.Children.Add(tabs);
        var branchPanel=Panel(); tabs.Items.Add(new TabItem { Header="Branches", Content=branchPanel });
        branchPanel.Children.Add(Note("Repository identity and branch context are shown above. Choose branches to compare their commits and file changes."));
        var row=new StackPanel { Orientation=Orientation.Horizontal }; _base.Width=300; _head.Width=300; _base.DisplayMemberPath="Label"; _head.DisplayMemberPath="Label"; _base.Margin=new Thickness(0,4,8,4); _head.Margin=new Thickness(0,4,8,4); row.Children.Add(_base); row.Children.Add(_head); var cmp=Button("Compare branches",async ()=>await CompareAsync()); row.Children.Add(cmp); branchPanel.Children.Add(row);
        var prPanel=Panel(); tabs.Items.Add(new TabItem { Header="Pull requests", Content=prPanel });
        prPanel.Children.Add(Note("Open and draft pull requests, with source, destination, freshness, and review state. Readiness checks are advisory and based on available GitHub metadata."));
        prPanel.Children.Add(Button("Refresh pull requests",async ()=>await LoadPrsAsync())); prPanel.Children.Add(_prs); prPanel.Children.Add(Button("Open selected pull request",async ()=>{if(_prs.SelectedItem is GitHubCollaborationService.PullRequest p)OpenUrl(p.Url);else Status("Select a pull request first.",true); await Task.CompletedTask;}));
        var prReview=new TextBlock { TextWrapping=TextWrapping.Wrap, Margin=new Thickness(0,8,0,0) }; _prs.SelectionChanged += async (_,_) => { if (_prs.SelectedItem is GitHubCollaborationService.PullRequest p) await ShowPrReadinessAsync(p,prReview); }; prPanel.Children.Add(prReview);
        var releasePanel=Panel(); tabs.Items.Add(new TabItem { Header="Releases", Content=releasePanel });
        releasePanel.Children.Add(Note("Review existing published and draft releases. Drafts can be resumed on GitHub; readiness checks call out missing notes, assets, or target information."));
        releasePanel.Children.Add(Button("Refresh releases",async ()=>await LoadReleasesAsync())); releasePanel.Children.Add(_releases); releasePanel.Children.Add(Button("Open selected release or draft",async ()=>{if(_releases.SelectedItem is GitHubCollaborationService.Release r)OpenUrl(r.Url);else Status("Select a release first.",true); await Task.CompletedTask;}));
        var releaseReview=new TextBlock { TextWrapping=TextWrapping.Wrap, Margin=new Thickness(0,8,0,0) }; _releases.SelectionChanged += (_,_) => { if (_releases.SelectedItem is GitHubCollaborationService.Release r) releaseReview.Text=$"{(r.Draft?"Draft recovery: open the draft on GitHub to continue editing. ":"Published release. ")}"+$"Readiness: {(string.IsNullOrWhiteSpace(r.Body)?"add release notes; ":"")}{(r.AssetCount==0?"attach expected assets; ":"")}{(string.IsNullOrWhiteSpace(r.Target)?"confirm target commit; ":"")}tag {r.Tag}, {r.AssetCount} asset(s)."; }; releasePanel.Children.Add(releaseReview);
        var actionPanel=Panel(); tabs.Items.Add(new TabItem { Header="Actions & artifacts", Content=actionPanel });
        actionPanel.Children.Add(Note("Recent GitHub Actions runs and downloadable artifacts. Artifact links require GitHub authorization and are opened in a browser."));
        actionPanel.Children.Add(Button("Refresh workflow runs",()=>LoadRunsAsync())); actionPanel.Children.Add(_runs); actionPanel.Children.Add(Button("Open selected run on GitHub",()=>OpenRun())); actionPanel.Children.Add(new TextBlock { Text="Artifacts for selected run", Margin=new Thickness(0,8,0,4) }); actionPanel.Children.Add(Button("Load artifacts",()=>LoadArtifactsAsync())); actionPanel.Children.Add(_artifacts); actionPanel.Children.Add(Button("Open selected artifact download",()=>OpenArtifact()));
        var diagnostics=Panel(); tabs.Items.Add(new TabItem { Header="Diagnostics", Content=diagnostics });
        diagnostics.Children.Add(Note("Run a read-only account and repository access check. The saved support report includes selected account/repository metadata and no credentials, authorization headers, response bodies, or freeform notes."));
        diagnostics.Children.Add(Button("Run diagnostics",async ()=>await DiagnosticsAsync())); diagnostics.Children.Add(_report); diagnostics.Children.Add(Button("Save redacted support report",()=>{SaveReport(this,new RoutedEventArgs());return Task.CompletedTask;}));
        Closed += (_,_)=>_life.Cancel(); Loaded += async (_,_)=>await LoadRepositoriesAsync(selectedRepository);
    }

    private async Task LoadRepositoriesAsync(string? preferred=null)
    {
        try { var token=Token(); _identity.Text="Loading account…"; var identity=await _service.IdentityAsync(token,_life.Token); var repos=await _service.RepositoriesAsync(token,_life.Token); _identity.Text="Signed in as "+identity;
            _repositories.ItemsSource=repos; _repositories.DisplayMemberPath="Name";
            var selection=repos.FirstOrDefault(x=>string.Equals(x.Name,preferred,StringComparison.OrdinalIgnoreCase)) ?? repos.FirstOrDefault(); if(selection!=null) _repositories.SelectedItem=selection; Status($"Loaded {repos.Count} accessible repositories."); }
        catch(Exception ex){Status("Could not load repositories: "+Guidance(ex),true);}
    }
    private async Task SelectRepositoryAsync()
    {
        if(_repositories.SelectedItem is not GitHubCollaborationService.Repo selected)return;
        _repo=selected; _base.ItemsSource=null;_head.ItemsSource=null;
        try { var branches=(await _service.BranchesAsync(selected.Name,Token(),_life.Token)).Select(x=>new BranchChoice(x.Name,x.Protected,x.Sha)).ToArray(); _base.ItemsSource=branches;_head.ItemsSource=branches; _base.SelectedItem=branches.FirstOrDefault(x=>x.Name==selected.DefaultBranch); _head.SelectedItem=branches.FirstOrDefault(x=>x.Name!=selected.DefaultBranch)??branches.FirstOrDefault();
            Title=$"{selected.Name} · Repository collaboration"; Status($"{selected.Name} · {selected.Visibility}{(selected.Archived?" · archived":"")} · default branch {selected.DefaultBranch} · {(selected.CanPush?"push access reported":"read access reported")}");
            await LoadPrsAsync(); await LoadReleasesAsync(); await LoadRunsAsync(); }
        catch(Exception ex){Status("Repository details unavailable: "+Guidance(ex),true);}
    }
    private async Task CompareAsync()
    {
        if(_repo==null||_base.SelectedItem is not BranchChoice b||_head.SelectedItem is not BranchChoice h)return;
        try { var c=await _service.CompareAsync(_repo.Name,b.Name,h.Name,Token(),_life.Token); var text=$"{h.Name} is {c.Ahead} commit(s) ahead and {c.Behind} behind {b.Name}. Changed files: {c.Files.Count}.\n"+string.Join("\n",c.Files.Take(250)); MessageBox.Show(this,text,"Branch comparison",MessageBoxButton.OK,MessageBoxImage.Information); }
        catch(Exception ex){Status("Branch comparison failed: "+Guidance(ex),true);}
    }
    private async Task LoadPrsAsync(){if(_repo==null)return;try{_prs.ItemsSource=await _service.PullRequestsAsync(_repo.Name,Token(),_life.Token);}catch(Exception ex){Status("Pull request list unavailable: "+Guidance(ex),true);}}
    private async Task ShowPrReadinessAsync(GitHubCollaborationService.PullRequest pr,TextBlock target){
        target.Text=$"Checking PR #{pr.Number} reviews and required checks...";
        try{if(_repo==null)return;var r=await _service.PullRequestReadinessAsync(_repo.Name,pr,Token(),_life.Token);var findings=new System.Collections.Generic.List<string>();if(string.IsNullOrWhiteSpace(pr.Title))findings.Add("add a title");if(pr.Draft)findings.Add("PR is draft");if(pr.MergeableState is "blocked" or "dirty")findings.Add("resolve merge blockers");if(r.ChangesRequested>0)findings.Add($"{r.ChangesRequested} reviewer(s) requested changes");if(r.FailedChecks>0)findings.Add($"{r.FailedChecks} check(s) failed");if(r.PendingChecks>0)findings.Add($"{r.PendingChecks} check(s) pending");target.Text=$"PR #{pr.Number}: {pr.Head} -> {pr.Base}. Reviews: {r.Approvals} approval(s), {r.ChangesRequested} change request(s). Checks: {r.TotalChecks} total, {r.FailedChecks} failed, {r.PendingChecks} pending. "+(findings.Count==0?"No blockers reported by these endpoints; verify branch protection and freshness on GitHub.":string.Join("; ",findings)+". Verify branch protection and freshness on GitHub.");}
        catch(Exception ex){target.Text=$"PR #{pr.Number} readiness details could not be loaded: {Guidance(ex)}";}
    }
    private async Task LoadReleasesAsync(){if(_repo==null)return;try{_releases.ItemsSource=await _service.ReleasesAsync(_repo.Name,Token(),_life.Token);}catch(Exception ex){Status("Release list unavailable: "+Guidance(ex),true);}}
    private async Task LoadRunsAsync(){if(_repo==null)return;try{_runs.ItemsSource=await _service.RunsAsync(_repo.Name,Token(),_life.Token);}catch(Exception ex){Status("Workflow runs unavailable: "+Guidance(ex),true);}}
    private async Task LoadArtifactsAsync(){if(_repo==null||_runs.SelectedItem is not GitHubCollaborationService.WorkflowRun run)return;try{_artifacts.ItemsSource=await _service.ArtifactsAsync(_repo.Name,run.Id,Token(),_life.Token);}catch(Exception ex){Status("Artifacts unavailable: "+Guidance(ex),true);}}
    private Task OpenRun(){if(_runs.SelectedItem is GitHubCollaborationService.WorkflowRun run)OpenUrl(run.Url);else Status("Select a workflow run first.",true);return Task.CompletedTask;}
    private Task OpenArtifact(){if(_artifacts.SelectedItem is GitHubCollaborationService.Artifact artifact)OpenUrl(artifact.Url);else Status("Select an artifact first.",true);return Task.CompletedTask;}
    private static void OpenUrl(string value){if(Uri.TryCreate(value,UriKind.Absolute,out var uri)&&uri.Scheme==Uri.UriSchemeHttps)Process.Start(new ProcessStartInfo(uri.AbsoluteUri){UseShellExecute=true});}
    private async Task DiagnosticsAsync()
    {
        try { var identity=await _service.IdentityAsync(Token(),_life.Token); var rate=await _service.RepositoriesAsync(Token(),_life.Token); var selected=_repo;
            var lines=new[]{"OctoShip GitHub diagnostics",DateTimeOffset.Now.ToString("O"),"Account: "+identity,"Accessible repositories: "+rate.Count,"Selected repository: "+(selected?.Name??"none"),"Repository visibility: "+(selected?.Visibility??"unknown"),"Push access reported: "+(selected?.CanPush==true?"yes":"no or unknown"),"Connectivity: GitHub API read succeeded","No write operation was attempted."};
            _report.Text=string.Join(Environment.NewLine,lines); Status("Diagnostics passed for read access. Push permission is the repository metadata report; no write was attempted."); }
        catch(Exception ex){Status("Diagnostics could not complete: "+Guidance(ex),true);}
    }
    private void SaveReport(object? sender,RoutedEventArgs e){var dlg=new Microsoft.Win32.SaveFileDialog{Title="Save redacted support report",Filter="Text report (*.txt)|*.txt",FileName="octoship-support-report.txt"};if(dlg.ShowDialog(this)==true){try{File.WriteAllText(dlg.FileName,_report.Text,Encoding.UTF8);Status("Saved redacted report to "+dlg.FileName);}catch(Exception ex){Status("Could not save report: "+ex.Message,true);}}}
    private string Token()=>_tokenProvider()??throw new InvalidOperationException("Sign in to GitHub first.");
    private static string Guidance(Exception ex)=>ex is HttpRequestException http&&http.StatusCode.HasValue?((int)http.StatusCode.Value switch{401=>"GitHub rejected sign-in. Reconnect the account and retry.",403=>"GitHub denied access. Check repository permissions and API quota.",404=>"The repository, branch, or feature may be unavailable to this account.",429=>"GitHub rate limit reached. Wait for the quota reset and retry.",_=>"GitHub request failed; check network access and retry."}):ex.Message;
    private void Status(string value,bool error=false){_status.Text=value;_status.Foreground=error?Brushes.OrangeRed:Brushes.LightSteelBlue;}
    private static DataGrid Grid()=>new(){IsReadOnly=true,AutoGenerateColumns=true,CanUserAddRows=false,MinHeight=160,MaxHeight=360,Background=Brushes.White,Foreground=Brushes.Black,Margin=new Thickness(0,8,0,8)};
    private static StackPanel Panel()=>new(){Margin=new Thickness(10),Background=Brushes.White};
    private static TextBlock Note(string text)=>new(){Text=text,Foreground=Brushes.Black,TextWrapping=TextWrapping.Wrap,Margin=new Thickness(0,4,0,10)};
    private static Button Button(string text,Func<Task> click){var b=new Button{Content=text,Padding=new Thickness(9,6,9,6),Margin=new Thickness(0,5,0,8),HorizontalAlignment=HorizontalAlignment.Left,Foreground=Brushes.Black};b.Click+=async(_,_)=>await click();return b;}
}
