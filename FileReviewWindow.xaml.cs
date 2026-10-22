using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Media.Imaging;

namespace FileToGitHub;

/// <summary>Review local file content and destination before upload. ShowDialog()==true means continue.</summary>
public partial class FileReviewWindow : Window
{
    private const int TextLimitBytes = 2 * 1024 * 1024;
    private readonly string _localPath;
    private readonly Func<string, CancellationToken, Task<string?>>? _remoteContentLoader;
    private readonly CancellationTokenSource _lifetime = new();
    private bool _isText;
    private bool _isPdf;
    private int[] _changedLineIndexes = Array.Empty<int>();
    private int _changeIndex = -1;

    public FileReviewWindow(string localPath, string? destinationRepositoryPath = null,
        Func<string, CancellationToken, Task<string?>>? remoteContentLoader = null,
        FileSafetyRules? safetyRules = null)
    {
        UniformUi.Prepare(this);
        InitializeComponent();
        _localPath = Path.GetFullPath(localPath);
        DestinationRepositoryPath = (destinationRepositoryPath ?? Path.GetFileName(_localPath)).Replace('\\', '/').TrimStart('/');
        _remoteContentLoader = remoteContentLoader;
        var info = new FileInfo(_localPath);
        FileTitle.Text = info.Name;
        FileDetails.Text = $"{info.Length:N0} bytes | {_localPath}\nGitHub destination: {DestinationRepositoryPath}";
        var matches = (safetyRules ?? new FileSafetyRules()).Match(info.Name);
        if (matches.Count > 0)
        {
            WarningCard.Visibility = Visibility.Visible;
            WarningText.Text = "This filename matches: " + string.Join(", ", matches) + ". The file may contain credentials or other sensitive data.";
        }
        if (info.Length > 50L * 1024 * 1024)
        {
            WarningCard.Visibility = Visibility.Visible;
            WarningText.Text += (WarningText.Text.Length == 0 ? "" : " ") + "GitHub's regular file upload API does not accept files above 50 MiB.";
        }
        ConfigurePreview(info);
        Loaded += ScanContentOnLoad;
        if (_remoteContentLoader == null) { CompareButton.IsEnabled = false; CompareStatus.Text = "Remote comparison is unavailable until the destination connection is supplied."; }
    }

    public string DestinationRepositoryPath { get; }
    public bool ContinueUpload { get; private set; }

    private async void ScanContentOnLoad(object sender, RoutedEventArgs e)
    {
        try
        {
            var scan = await ContentSecretScanner.ScanAsync(_localPath, _lifetime.Token);
            WarningCard.Visibility = Visibility.Visible;
            WarningText.Text += (WarningText.Text.Length == 0 ? "" : "\n") + scan.Summary;
        }
        catch (OperationCanceledException) { }
    }

    private void ConfigurePreview(FileInfo info)
    {
        PreviewContentKind kind;
        try { kind = FileContentTypeAudit.Read(_localPath); }
        catch (Exception ex)
        {
            PreviewMessage.Text = "Could not inspect the file signature: " + ex.Message;
            CompareButton.IsEnabled = false;
            return;
        }
        if (FileContentTypeAudit.HasKnownExtensionMismatch(info.Extension, kind))
        {
            WarningCard.Visibility = Visibility.Visible;
            WarningText.Text += (WarningText.Text.Length == 0 ? "" : "\n") + $"The .{info.Extension.TrimStart('.')} extension does not match the detected {kind} content. Preview selection follows the detected content.";
        }
        if (kind is PreviewContentKind.Png or PreviewContentKind.Jpeg or PreviewContentKind.Gif or PreviewContentKind.Bitmap or PreviewContentKind.Tiff)
        {
            try
            {
                var image = new BitmapImage();
                image.BeginInit(); image.CacheOption = BitmapCacheOption.OnLoad; image.DecodePixelWidth = 1600; image.UriSource = new Uri(_localPath); image.EndInit(); image.Freeze();
                ImagePreview.Source = image; ImagePreview.Visibility = Visibility.Visible; PreviewMessage.Visibility = Visibility.Collapsed;
            }
            catch (Exception ex) { PreviewMessage.Text = "Image preview could not be loaded: " + ex.Message; }
        }
        else if (kind == PreviewContentKind.Pdf)
        {
            _isPdf = true;
            PreviewMessage.Text = "PDF preview is not built into this app. You can open it in your default PDF viewer.";
            OpenPdfButton.Visibility = Visibility.Visible;
        }
        else if (info.Length > TextLimitBytes) PreviewMessage.Text = "Inline text preview is limited to files up to 2 MiB. Use the compare tab only for supported text files.";
        else if (kind == PreviewContentKind.Text)
        {
            try
            {
                var bytes = File.ReadAllBytes(_localPath);
                _isText = !bytes.Take(Math.Min(bytes.Length, 8192)).Contains((byte)0);
                if (_isText)
                {
                    var text = new UTF8Encoding(false, false).GetString(bytes);
                    LocalText.Text = text;
                    if (string.Equals(info.Extension, ".json", StringComparison.OrdinalIgnoreCase))
                    {
                        try
                        {
                            using var json = JsonDocument.Parse(text);
                            PreviewMessage.Text = JsonSerializer.Serialize(json.RootElement, new JsonSerializerOptions { WriteIndented = true });
                        }
                        catch (JsonException) { PreviewMessage.Text = "This JSON file is malformed. Raw text is shown in the compare tab."; }
                    }
                    else if (string.Equals(info.Extension, ".md", StringComparison.OrdinalIgnoreCase) || string.Equals(info.Extension, ".markdown", StringComparison.OrdinalIgnoreCase))
                        PreviewMessage.Text = text.Length == 0 ? "Empty Markdown file." : text;
                    else PreviewMessage.Text = text.Length == 0 ? "Empty text file." : text;
                    PreviewMessage.FontFamily = new System.Windows.Media.FontFamily("Consolas");
                }
                else PreviewMessage.Text = "Binary preview is not supported for this file type.";
            }
            catch (Exception ex) { PreviewMessage.Text = "Could not read this file for preview: " + ex.Message; }
        }
        else PreviewMessage.Text = "Content type is not recognized. OctoShip will not launch it from this preview.";
        if (!_isText)
        { CompareButton.IsEnabled = false; CompareStatus.Text = "Text comparison is available for UTF-8-like text files up to 2 MiB."; }
    }

    private async void Compare_Click(object sender, RoutedEventArgs e)
    {
        if (!_isText || _remoteContentLoader == null) return;
        CompareButton.IsEnabled = false; CompareStatus.Text = "Loading remote file...";
        try
        {
            var content = await _remoteContentLoader(DestinationRepositoryPath, _lifetime.Token);
            RemoteText.Text = content ?? string.Empty;
            BuildChangeLandmarks(LocalText.Text, RemoteText.Text);
            CompareStatus.Text = content == null ? "No remote file exists at this destination." : DescribeDifference(LocalText.Text, content);
        }
        catch (OperationCanceledException) { CompareStatus.Text = "Comparison canceled."; }
        catch (Exception ex) { CompareStatus.Text = "Could not load remote version: " + ex.Message; }
        finally { CompareButton.IsEnabled = true; }
    }

    private void BuildChangeLandmarks(string local, string remote)
    {
        var a = local.Replace("\r\n", "\n").Split('\n'); var b = remote.Replace("\r\n", "\n").Split('\n');
        _changedLineIndexes = Enumerable.Range(0, Math.Max(a.Length, b.Length)).Where(i => i >= a.Length || i >= b.Length || !string.Equals(a[i], b[i], StringComparison.Ordinal)).ToArray();
        _changeIndex = _changedLineIndexes.Length == 0 ? -1 : 0;
        ChangePosition.Text = _changedLineIndexes.Length == 0 ? "No changed lines" : $"Change 1 of {_changedLineIndexes.Length} · line {_changedLineIndexes[0] + 1}";
        if (_changeIndex >= 0) FocusChange();
    }
    private void PreviousChange_Click(object sender, RoutedEventArgs e) => MoveChange(-1);
    private void NextChange_Click(object sender, RoutedEventArgs e) => MoveChange(1);
    private void MoveChange(int direction)
    {
        if (_changedLineIndexes.Length == 0) return;
        _changeIndex = (_changeIndex + direction + _changedLineIndexes.Length) % _changedLineIndexes.Length;
        ChangePosition.Text = $"Change {_changeIndex + 1} of {_changedLineIndexes.Length} · line {_changedLineIndexes[_changeIndex] + 1}";
        FocusChange();
    }
    private void FocusChange()
    {
        var line = _changedLineIndexes[_changeIndex];
        ScrollToLine(LocalText, line); ScrollToLine(RemoteText, line);
    }
    private static void ScrollToLine(System.Windows.Controls.TextBox box, int line)
    {
        var index = box.GetCharacterIndexFromLineIndex(Math.Min(line, Math.Max(0, box.LineCount - 1)));
        box.Select(index, 0); box.ScrollToLine(Math.Min(line, Math.Max(0, box.LineCount - 1)));
    }

    private static string DescribeDifference(string local, string remote)
    {
        if (string.Equals(local, remote, StringComparison.Ordinal)) return "Local and remote contents match.";
        var a = local.Replace("\r\n", "\n").Split('\n'); var b = remote.Replace("\r\n", "\n").Split('\n');
        var changed = Enumerable.Range(0, Math.Max(a.Length, b.Length)).Count(i => i >= a.Length || i >= b.Length || a[i] != b[i]);
        return $"Contents differ | {changed} line position(s) differ | local {a.Length} lines / remote {b.Length} lines.";
    }

    private void OpenPdf_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (!_isPdf || FileContentTypeAudit.Read(_localPath) != PreviewContentKind.Pdf)
                throw new InvalidOperationException("The file no longer has a PDF signature. Review it again before opening.");
            TrustedProcess.Start(new System.Diagnostics.ProcessStartInfo(_localPath) { UseShellExecute = true });
        }
        catch (Exception ex) { OctoShipDialog.Show(this, ex.Message, "Could not open PDF", MessageBoxButton.OK, MessageBoxImage.Warning); }
    }

    private void Continue_Click(object sender, RoutedEventArgs e) { ContinueUpload = true; DialogResult = true; }
    protected override void OnClosed(EventArgs e) { _lifetime.Cancel(); _lifetime.Dispose(); base.OnClosed(e); }
}
