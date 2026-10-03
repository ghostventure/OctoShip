using System;
using System.IO;
using System.Linq;
using System.Text;
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

    public FileReviewWindow(string localPath, string? destinationRepositoryPath = null,
        Func<string, CancellationToken, Task<string?>>? remoteContentLoader = null,
        FileSafetyRules? safetyRules = null)
    {
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
        if (_remoteContentLoader == null) { CompareButton.IsEnabled = false; CompareStatus.Text = "Remote comparison is unavailable until the destination connection is supplied."; }
    }

    public string DestinationRepositoryPath { get; }
    public bool ContinueUpload { get; private set; }

    private void ConfigurePreview(FileInfo info)
    {
        var ext = info.Extension.ToLowerInvariant();
        if (new[] { ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff" }.Contains(ext))
        {
            try
            {
                var image = new BitmapImage();
                image.BeginInit(); image.CacheOption = BitmapCacheOption.OnLoad; image.UriSource = new Uri(_localPath); image.EndInit(); image.Freeze();
                ImagePreview.Source = image; ImagePreview.Visibility = Visibility.Visible; PreviewMessage.Visibility = Visibility.Collapsed;
            }
            catch (Exception ex) { PreviewMessage.Text = "Image preview could not be loaded: " + ex.Message; }
        }
        else if (ext == ".pdf")
        {
            PreviewMessage.Text = "PDF preview is not built into this app. You can open it in your default PDF viewer.";
            OpenPdfButton.Visibility = Visibility.Visible;
        }
        else if (info.Length > TextLimitBytes) PreviewMessage.Text = "Inline text preview is limited to files up to 2 MiB. Use the compare tab only for supported text files.";
        else
        {
            try
            {
                var bytes = File.ReadAllBytes(_localPath);
                _isText = !bytes.Take(Math.Min(bytes.Length, 8192)).Contains((byte)0);
                if (_isText)
                {
                    var text = new UTF8Encoding(false, false).GetString(bytes);
                    LocalText.Text = text;
                    PreviewMessage.Text = text.Length == 0 ? "Empty text file." : text;
                    PreviewMessage.FontFamily = new System.Windows.Media.FontFamily("Consolas");
                }
                else PreviewMessage.Text = "Binary preview is not supported for this file type.";
            }
            catch (Exception ex) { PreviewMessage.Text = "Could not read this file for preview: " + ex.Message; }
        }
        if (!_isText && ext is not ".png" and not ".jpg" and not ".jpeg" and not ".gif" and not ".bmp" and not ".tif" and not ".tiff")
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
            CompareStatus.Text = content == null ? "No remote file exists at this destination." : DescribeDifference(LocalText.Text, content);
        }
        catch (OperationCanceledException) { CompareStatus.Text = "Comparison canceled."; }
        catch (Exception ex) { CompareStatus.Text = "Could not load remote version: " + ex.Message; }
        finally { CompareButton.IsEnabled = true; }
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
        try { System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(_localPath) { UseShellExecute = true }); }
        catch (Exception ex) { MessageBox.Show(this, ex.Message, "Could not open PDF", MessageBoxButton.OK, MessageBoxImage.Warning); }
    }

    private void Continue_Click(object sender, RoutedEventArgs e) { ContinueUpload = true; DialogResult = true; }
    protected override void OnClosed(EventArgs e) { _lifetime.Cancel(); _lifetime.Dispose(); base.OnClosed(e); }
}
