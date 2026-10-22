using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using Microsoft.Win32;

namespace FileToGitHub;

/// <summary>Settings editor. Import/export uses an allow-listed package that contains no credentials or local paths.</summary>
public partial class OctoCatSettingsWindow : Window
{
    private readonly List<string> _patterns = new();
    private readonly List<DestinationPreset> _presets = new();
    private string[] _originalPatterns = Array.Empty<string>();
    private DestinationPreset[] _originalPresets = Array.Empty<DestinationPreset>();
    private OctoCatPreferences _preferences;
    private readonly OctoCatPreferences _originalPreferences;
    private readonly List<string> _archived = new();
    private readonly List<string> _privateRepositories = new();
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true, PropertyNameCaseInsensitive = true };

    public OctoCatPreferences Preferences { get; private set; }
    public IReadOnlyList<string> SensitivePatterns { get; private set; }
    public IReadOnlyList<DestinationPreset> DestinationPresets { get; private set; }

    public OctoCatSettingsWindow(OctoCatPreferences? preferences = null, IEnumerable<string>? sensitivePatterns = null,
        IEnumerable<DestinationPreset>? destinationPresets = null)
    {
        UniformUi.Prepare(this);
        InitializeComponent();
        _preferences = OctoCatPreferencesService.Normalize(preferences ?? new OctoCatPreferences());
        Preferences = _preferences;
        _originalPreferences = _preferences;
        SensitivePatterns = Array.Empty<string>();
        DestinationPresets = Array.Empty<DestinationPreset>();
        PrivacyCheck.IsChecked = _preferences.PrivacyMode;
        AutomaticUpdatesCheck.IsChecked = _preferences.AutomaticUpdates;
        ClipboardClearPicker.SelectedIndex = ClipboardClearSelection(_preferences.ClearCopiedTextAfterSeconds);
        ChannelPicker.SelectedIndex = _preferences.UpdateChannel == OctoCatUpdateChannel.Preview ? 1 : 0;
        ScreenShareMaskCheck.IsChecked = _preferences.ScreenSharePrivacyMask;
        _privateRepositories.AddRange(_preferences.PrivateOnlyRepositories);
        PrivateRepositoryList.ItemsSource = _privateRepositories.ToArray();
        _archived.AddRange(OctoShipWorkspacePolicyService.ReadArchived());
        ArchivedWorkspaceList.ItemsSource = _archived.ToArray();
        RefreshRetention();
        _patterns.AddRange(NormalizePatterns(sensitivePatterns ?? Array.Empty<string>()));
        _presets.AddRange((destinationPresets ?? ToPresets(_preferences.Destinations)).Where(IsValidPreset).Take(50));
        _originalPatterns = _patterns.ToArray();
        _originalPresets = _presets.ToArray();
        PatternList.ItemsSource = _patterns.ToArray();
        RefreshPresets();
    }

    private void ClearHistory_Click(object sender, RoutedEventArgs e)
    {
        var search = ClearSearchCheck.IsChecked == true;
        var recent = ClearRecentCheck.IsChecked == true;
        var destinations = ClearDestinationsCheck.IsChecked == true;
        if (!search && !recent && !destinations) { SetStatus("Select at least one history type to clear.", true); return; }
        var details = DestructiveActionConfirmation.DescribeHistory(_preferences.SearchHistory.Count,
            _preferences.RecentRepositories.Count, _presets.Count, search, recent, destinations);
        if (!DestructiveActionConfirmation.Confirm(this, "Clear selected history?", details,
                "Clear selected history", "Keep history")) return;
        if (search && recent && destinations)
            _preferences = OctoCatPreferencesService.ClearHistory(_preferences, clearDestinations: true);
        else
            _preferences = _preferences with
            {
                SearchHistory = search ? Array.Empty<string>() : _preferences.SearchHistory,
                RecentRepositories = recent ? Array.Empty<string>() : _preferences.RecentRepositories,
                Destinations = destinations ? Array.Empty<string>() : _preferences.Destinations
            };
        if (destinations) { _presets.Clear(); RefreshPresets(); }
        SetStatus("Selected history will be cleared when you save.");
    }

    private void AddPattern_Click(object sender, RoutedEventArgs e)
    {
        var pattern = PatternInput.Text.Trim();
        if (!IsSafeGlob(pattern)) { ShowPatternError("Enter a safe glob (for example, *.pem or **/.env). Avoid absolute paths, backslashes, and . or .. path segments."); return; }
        if (_patterns.Contains(pattern, StringComparer.OrdinalIgnoreCase)) { ShowPatternError("That pattern is already listed. Edit it or choose a different glob."); return; }
        _patterns.Add(pattern);
        PatternInput.Clear();
        PatternValidationText.Text = string.Empty;
        PatternValidationText.Visibility = Visibility.Collapsed;
        PatternList.ItemsSource = _patterns.ToArray();
        SetStatus("Pattern added. It will warn on matching names; it will not block uploads.");
    }

    private void ShowPatternError(string message)
    {
        PatternValidationText.Text = message;
        PatternValidationText.Visibility = Visibility.Visible;
        SetStatus(message, true);
        PatternInput.Focus();
        PatternInput.SelectAll();
    }

    private void PatternInput_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (PatternValidationText is null || PatternValidationText.Visibility != Visibility.Visible) return;
        PatternValidationText.Text = string.Empty;
        PatternValidationText.Visibility = Visibility.Collapsed;
    }

    private void RemovePattern_Click(object sender, RoutedEventArgs e)
    {
        if (PatternList.SelectedItem is not string pattern) return;
        _patterns.Remove(pattern);
        PatternList.ItemsSource = _patterns.ToArray();
        SetStatus("Pattern removed.");
    }

    private void PresetList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (PresetList.SelectedItem is DestinationPreset preset) PresetNameInput.Text = preset.Label;
    }

    private void RenamePreset_Click(object sender, RoutedEventArgs e)
    {
        if (PresetList.SelectedItem is not DestinationPreset selected) { SetStatus("Select a destination preset first.", true); return; }
        var newName = PresetNameInput.Text.Trim();
        if (newName.Length is < 1 or > 80 || newName.Any(char.IsControl)) { SetStatus("Preset names must be 1 to 80 characters.", true); return; }
        var index = _presets.IndexOf(selected);
        if (index < 0) return;
        _presets[index] = selected with { Label = newName };
        RefreshPresets();
        PresetList.SelectedItem = _presets[index];
        SetStatus("Preset renamed; its repository, branch, and folder values are unchanged.");
    }

    private void DeletePreset_Click(object sender, RoutedEventArgs e)
    {
        if (PresetList.SelectedItem is not DestinationPreset selected) { SetStatus("Select a destination preset first.", true); return; }
        var details = DestructiveActionConfirmation.DescribePreset(selected.Label, selected.Value);
        if (!DestructiveActionConfirmation.Confirm(this, "Delete destination preset?", details, "Delete preset", "Keep preset")) return;
        _presets.Remove(selected);
        RefreshPresets();
        SetStatus("Preset will be deleted when you save.");
    }

    private void VerifyPublisher_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog { Title = "Choose an OctoShip executable", Filter = "Windows executable (*.exe)|*.exe|All files (*.*)|*.*", CheckFileExists = true };
        if (dialog.ShowDialog(this) != true) return;
        var result = OctoCatPreferencesService.VerifyPublisher(dialog.FileName, ThumbprintInput.Text.Trim());
        SignatureStatus.Text = $"{(result.Trusted ? "TRUSTED" : "NOT TRUSTED")}: {result.Message}" +
            (string.IsNullOrWhiteSpace(result.SignerThumbprint) ? "" : $" Signer: {result.SignerThumbprint}.");
        SignatureStatus.Foreground = result.Trusted ? System.Windows.Media.Brushes.LightGreen : System.Windows.Media.Brushes.OrangeRed;
    }

    private void Import_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog { Title = "Import OctoShip settings", Filter = "OctoShip settings (*.json)|*.json|JSON files (*.json)|*.json", CheckFileExists = true };
        if (dialog.ShowDialog(this) != true) return;
        try
        {
            using var stream = File.OpenRead(dialog.FileName);
            var package = JsonSerializer.Deserialize<SettingsPackage>(stream, JsonOptions);
            if (package?.Preferences is null)
            {
                _preferences = OctoCatPreferencesService.Import(dialog.FileName);
                _patterns.Clear();
                _presets.Clear();
                _presets.AddRange(ToPresets(_preferences.Destinations));
            }
            else
            {
                if (package.SchemaVersion > 2) throw new InvalidOperationException($"Settings package version {package.SchemaVersion} is newer than this app supports.");
                var imported = OctoCatPreferencesService.Normalize(package.Preferences);
                var choices = new Dictionary<string, bool>(StringComparer.Ordinal);
                var conflictDetails = new Dictionary<string, string>(StringComparer.Ordinal);
                foreach (var key in new[] { "PrivacyMode", "ScreenSharePrivacyMask", "UpdateChannel", "AutomaticUpdates", "ClearCopiedTextAfterSeconds", "SearchHistory", "RecentRepositories", "Destinations", "DefaultUploadFolders", "PrivateOnlyRepositories", "ArchivedWorkspaces" })
                {
                    var currentValue = JsonSerializer.Serialize(GetPreferenceValue(_preferences, key));
                    var importedValue = JsonSerializer.Serialize(GetPreferenceValue(imported, key));
                    if (currentValue != importedValue) { choices[key] = true; conflictDetails[key] = $"Current: {ShortValue(currentValue)}\nImported: {ShortValue(importedValue)}"; }
                }
                var importedPatterns = NormalizePatterns(package.SensitivePatterns ?? Array.Empty<string>()).ToArray();
                var importedPresets = (package.DestinationPresets ?? ToPresets(imported.Destinations)).Where(IsValidPreset).Take(50).ToArray();
                AddCollectionConflict("Sensitive filename patterns", _patterns.ToArray(), importedPatterns);
                AddCollectionConflict("Destination presets", _presets.ToArray(), importedPresets);
                if (choices.Count > 0)
                {
                    var resolver = new SettingsImportConflictWindow(conflictDetails) { Owner = this };
                    if (resolver.ShowDialog() != true) { SetStatus("Import canceled; no settings changed."); return; }
                    imported = imported with
                    {
                        PrivacyMode = Merge("PrivacyMode", imported.PrivacyMode, _preferences.PrivacyMode),
                        ScreenSharePrivacyMask = Merge("ScreenSharePrivacyMask", imported.ScreenSharePrivacyMask, _preferences.ScreenSharePrivacyMask),
                        UpdateChannel = Merge("UpdateChannel", imported.UpdateChannel, _preferences.UpdateChannel),
                        AutomaticUpdates = Merge("AutomaticUpdates", imported.AutomaticUpdates, _preferences.AutomaticUpdates),
                        ClearCopiedTextAfterSeconds = Merge("ClearCopiedTextAfterSeconds", imported.ClearCopiedTextAfterSeconds, _preferences.ClearCopiedTextAfterSeconds),
                        SearchHistory = Merge("SearchHistory", imported.SearchHistory, _preferences.SearchHistory),
                        RecentRepositories = Merge("RecentRepositories", imported.RecentRepositories, _preferences.RecentRepositories),
                        Destinations = Merge("Destinations", imported.Destinations, _preferences.Destinations),
                        DefaultUploadFolders = Merge("DefaultUploadFolders", imported.DefaultUploadFolders, _preferences.DefaultUploadFolders),
                        PrivateOnlyRepositories = Merge("PrivateOnlyRepositories", imported.PrivateOnlyRepositories, _preferences.PrivateOnlyRepositories),
                        ArchivedWorkspaces = Merge("ArchivedWorkspaces", imported.ArchivedWorkspaces, _preferences.ArchivedWorkspaces)
                    };
                    T Merge<T>(string name, T value, T current) => choices.TryGetValue(name, out var useImported) && !useImported ? current : value;
                }
                _preferences = imported;
                if (!choices.TryGetValue("Sensitive filename patterns", out var usePatterns) || usePatterns) { _patterns.Clear(); _patterns.AddRange(importedPatterns); }
                if (!choices.TryGetValue("Destination presets", out var usePresets) || usePresets) { _presets.Clear(); _presets.AddRange(importedPresets); }

                void AddCollectionConflict<T>(string key, T current, T proposed)
                {
                    var currentText = JsonSerializer.Serialize(current); var importedText = JsonSerializer.Serialize(proposed);
                    if (currentText != importedText) { choices[key] = true; conflictDetails[key] = $"Current: {ShortValue(currentText)}\nImported: {ShortValue(importedText)}"; }
                }
            }
            PrivacyCheck.IsChecked = _preferences.PrivacyMode;
            ChannelPicker.SelectedIndex = _preferences.UpdateChannel == OctoCatUpdateChannel.Preview ? 1 : 0;
            AutomaticUpdatesCheck.IsChecked = _preferences.AutomaticUpdates;
            ScreenShareMaskCheck.IsChecked = _preferences.ScreenSharePrivacyMask;
            _privateRepositories.Clear(); _privateRepositories.AddRange(_preferences.PrivateOnlyRepositories); PrivateRepositoryList.ItemsSource = _privateRepositories.ToArray();
            _archived.Clear(); _archived.AddRange(_preferences.ArchivedWorkspaces); ArchivedWorkspaceList.ItemsSource = _archived.ToArray();
            ClipboardClearPicker.SelectedIndex = ClipboardClearSelection(_preferences.ClearCopiedTextAfterSeconds);
            PatternList.ItemsSource = _patterns.ToArray();
            RefreshPresets();
            SetStatus("Settings imported into this window. Select Save to apply them.");
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException or InvalidOperationException)
        { SetStatus("Could not import settings: " + ex.Message, true); }
    }

    private void Export_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new SaveFileDialog { Title = "Export OctoShip settings", Filter = "OctoShip settings (*.json)|*.json", FileName = "OctoShip-settings.json", DefaultExt = ".json", AddExtension = true };
        if (dialog.ShowDialog(this) != true) return;
        try
        {
            var current = BuildResultPreferences();
            var package = new SettingsPackage(current, _patterns.ToArray(), _presets.ToArray());
            var json = JsonSerializer.Serialize(package, JsonOptions);
            WriteAtomic(dialog.FileName, json);
            SetStatus("Credential-free settings exported. No GitHub credentials or local paths are included.");
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException)
        { SetStatus("Could not export settings: " + ex.Message, true); }
    }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        try { BackupCurrentPreferencesIfChanged(); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { SetStatus("Could not preserve the previous preferences before saving: " + ex.Message, true); return; }
        Preferences = BuildResultPreferences();
        try { OctoShipWorkspacePolicyService.SaveArchived(_archived); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { SetStatus("Could not save workspace archive: " + ex.Message, true); return; }
        SensitivePatterns = _patterns.ToArray();
        DestinationPresets = _presets.ToArray();
        DialogResult = true;
        Close();
    }

    private void Cancel_Click(object sender, RoutedEventArgs e) { DialogResult = false; Close(); }

    private OctoCatPreferences BuildResultPreferences()
    {
        var privacy = PrivacyCheck.IsChecked == true;
        var channel = ChannelPicker.SelectedIndex == 1 ? OctoCatUpdateChannel.Preview : OctoCatUpdateChannel.Stable;
        var values = _presets.Select(preset => preset.Value).ToArray();
        var result = _preferences with
        {
            PrivacyMode = privacy,
            ScreenSharePrivacyMask = ScreenShareMaskCheck.IsChecked == true,
            PrivateOnlyRepositories = _privateRepositories.ToArray(),
            ArchivedWorkspaces = _archived.ToArray(),
            UpdateChannel = channel,
            AutomaticUpdates = AutomaticUpdatesCheck.IsChecked == true,
            ClearCopiedTextAfterSeconds = ClipboardClearDelay(ClipboardClearPicker.SelectedIndex),
            Destinations = values,
            SearchHistory = privacy ? Array.Empty<string>() : _preferences.SearchHistory,
            RecentRepositories = privacy ? Array.Empty<string>() : _preferences.RecentRepositories
        };
        return OctoCatPreferencesService.Normalize(result);
    }

    private void RefreshPresets() => PresetList.ItemsSource = _presets.ToArray();
    private static int ClipboardClearSelection(int seconds) => seconds switch { 30 => 1, 60 => 2, 300 => 3, _ => 0 };
    private static int ClipboardClearDelay(int selection) => selection switch { 1 => 30, 2 => 60, 3 => 300, _ => 0 };
    private void SetStatus(string text, bool error = false)
    {
        StatusText.Text = text;
        StatusText.Foreground = error ? System.Windows.Media.Brushes.OrangeRed : System.Windows.Media.Brushes.LightSteelBlue;
    }

    private void SettingsSearch_TextChanged(object sender, TextChangedEventArgs e)
    {
        var query = SettingsSearchBox.Text.Trim();
        foreach (var group in new[] { WorkspaceHealthGroup, PrivacyPolicyGroup, RetentionRepairGroup, ChangeReviewGroup, PrivacyUpdatesGroup, ClearHistoryGroup, DestinationPresetsGroup, SensitivePatternsGroup, PublisherSignatureGroup, SettingsTransferGroup })
            group.Visibility = string.IsNullOrEmpty(query) || (group.Header?.ToString()?.Contains(query, StringComparison.OrdinalIgnoreCase) == true) ? Visibility.Visible : Visibility.Collapsed;
    }

    private void HealthReport_Click(object sender, RoutedEventArgs e) => HealthReportText.Text = string.Join(Environment.NewLine, OctoShipWorkspacePolicyService.HealthReport());
    private void ArchiveWorkspace_Click(object sender, RoutedEventArgs e)
    {
        var name = ArchiveWorkspaceInput.Text.Trim();
        if (name.Length is < 1 or > 500 || name.Any(char.IsControl)) { SetStatus("Enter a workspace name of 1 to 500 characters.", true); return; }
        if (!_archived.Contains(name, StringComparer.OrdinalIgnoreCase)) _archived.Add(name);
        ArchivedWorkspaceList.ItemsSource = _archived.ToArray(); ArchiveWorkspaceInput.Clear(); SetStatus("Workspace archive status will be saved with your settings.");
    }
    private void RestoreWorkspace_Click(object sender, RoutedEventArgs e)
    {
        if (ArchivedWorkspaceList.SelectedItem is not string name) return;
        _archived.Remove(name); ArchivedWorkspaceList.ItemsSource = _archived.ToArray(); SetStatus("Workspace restored from archive.");
    }
    private void AddPrivateRepository_Click(object sender, RoutedEventArgs e)
    {
        var value = PrivateRepositoryInput.Text.Trim();
        if (!Regex.IsMatch(value, "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$") || value.Split('/').Any(x => x is "." or "..")) { SetStatus("Use a repository in owner/name format.", true); return; }
        if (!_privateRepositories.Contains(value, StringComparer.OrdinalIgnoreCase)) _privateRepositories.Add(value);
        PrivateRepositoryList.ItemsSource = _privateRepositories.ToArray(); PrivateRepositoryInput.Clear();
    }
    private void RemovePrivateRepository_Click(object sender, RoutedEventArgs e)
    { if (PrivateRepositoryList.SelectedItem is string value) { _privateRepositories.Remove(value); PrivateRepositoryList.ItemsSource = _privateRepositories.ToArray(); } }
    private void RefreshRetention_Click(object sender, RoutedEventArgs e) => RefreshRetention();
    private void RefreshRetention() => RetentionList.ItemsSource = OctoShipWorkspacePolicyService.RetentionInventory().Select(x => $"{x.Name} — {x.Bytes:N0} bytes").ToArray();
    private void PurgeRetention_Click(object sender, RoutedEventArgs e)
    {
        var items = RetentionList.SelectedItems.Cast<string>().Select(x => x.Split(" — ", StringSplitOptions.None)[0]).ToArray();
        if (items.Length == 0) { SetStatus("Select local data in the preview first.", true); return; }
        if (!DestructiveActionConfirmation.Confirm(this, "Purge selected local data?", string.Join(Environment.NewLine, items), "Purge selected data", "Keep data")) return;
        try { OctoShipWorkspacePolicyService.PurgeRetainable(items); RefreshRetention(); SetStatus("Selected local data purged. Protected account settings were not touched."); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidOperationException) { SetStatus("Could not purge local data: " + ex.Message, true); }
    }
    private void RepairProfile_Click(object sender, RoutedEventArgs e)
    {
        if (!DestructiveActionConfirmation.Confirm(this, "Repair preference profile?", "A malformed preference file will be preserved as a timestamped backup before defaults are written. Valid profiles are left unchanged.", "Repair profile", "Cancel")) return;
        try { SetStatus(OctoShipWorkspacePolicyService.RepairPreferences()); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException) { SetStatus("Profile repair did not complete: " + ex.Message, true); }
    }
    private void PreviewChanges_Click(object sender, RoutedEventArgs e)
    {
        var current = BuildResultPreferences();
        var changes = new List<string>();
        Add("Privacy", _originalPreferences.PrivacyMode, current.PrivacyMode);
        Add("Screen-share mask", _originalPreferences.ScreenSharePrivacyMask, current.ScreenSharePrivacyMask);
        Add("Update channel", _originalPreferences.UpdateChannel, current.UpdateChannel);
        Add("Automatic updates", _originalPreferences.AutomaticUpdates, current.AutomaticUpdates);
        Add("Clipboard clearing", _originalPreferences.ClearCopiedTextAfterSeconds, current.ClearCopiedTextAfterSeconds);
        Add("Search history", _originalPreferences.SearchHistory.Count, current.SearchHistory.Count);
        Add("Repository policy rules", string.Join(", ", _originalPreferences.PrivateOnlyRepositories), string.Join(", ", current.PrivateOnlyRepositories));
        Add("Archived workspaces", string.Join(", ", _originalPreferences.ArchivedWorkspaces), string.Join(", ", current.ArchivedWorkspaces));
        Add("Sensitive filename patterns", string.Join(", ", _originalPatterns), string.Join(", ", _patterns));
        Add("Destination presets", string.Join("; ", _originalPresets.Select(x => x.Label + "=" + x.Value)), string.Join("; ", _presets.Select(x => x.Label + "=" + x.Value)));
        PendingChangesText.Text = changes.Count == 0 ? "No preference changes are pending." : string.Join(Environment.NewLine, changes);
        void Add(string label, object? before, object? after) { if (!Equals(before, after)) changes.Add($"{label}: {before} → {after}"); }
    }
    private void ResetPrivacy_Click(object sender, RoutedEventArgs e) { PrivacyCheck.IsChecked = _originalPreferences.PrivacyMode; ScreenShareMaskCheck.IsChecked = _originalPreferences.ScreenSharePrivacyMask; _privateRepositories.Clear(); _privateRepositories.AddRange(_originalPreferences.PrivateOnlyRepositories); PrivateRepositoryList.ItemsSource = _privateRepositories.ToArray(); }
    private void ResetUpdates_Click(object sender, RoutedEventArgs e) { AutomaticUpdatesCheck.IsChecked = _originalPreferences.AutomaticUpdates; ChannelPicker.SelectedIndex = _originalPreferences.UpdateChannel == OctoCatUpdateChannel.Preview ? 1 : 0; }
    private void ResetHistory_Click(object sender, RoutedEventArgs e) { ClearSearchCheck.IsChecked = false; ClearRecentCheck.IsChecked = false; ClearDestinationsCheck.IsChecked = false; _archived.Clear(); _archived.AddRange(_originalPreferences.ArchivedWorkspaces); ArchivedWorkspaceList.ItemsSource = _archived.ToArray(); }
    private void ResetPatterns_Click(object sender, RoutedEventArgs e) { _patterns.Clear(); _patterns.AddRange(_originalPatterns); PatternList.ItemsSource = _patterns.ToArray(); }
    private void ResetDestinations_Click(object sender, RoutedEventArgs e) { _presets.Clear(); _presets.AddRange(_originalPresets); RefreshPresets(); }

    private static object? GetPreferenceValue(OctoCatPreferences preferences, string name) => typeof(OctoCatPreferences).GetProperty(name)?.GetValue(preferences);
    private static string ShortValue(string value) => value.Length <= 160 ? value : value[..157] + "...";

    private static IEnumerable<DestinationPreset> ToPresets(IEnumerable<string> values) => values.Select(value => new DestinationPreset(value, value));
    private static bool IsValidPreset(DestinationPreset item) => item is not null && item.Label is { Length: > 0 and <= 80 } && !item.Label.Any(char.IsControl) && IsSafePresetValue(item.Value);
    private static bool IsSafePresetValue(string value)
    {
        var parts = value.Split('|', 3);
        return parts.Length == 3 && Regex.IsMatch(parts[0], "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$") && parts[1].Length is > 0 and <= 255 && !parts[1].Any(char.IsControl) &&
            !parts[2].Contains('\\') && !parts[2].Any(char.IsControl) && (parts[2].Length == 0 || parts[2].Split('/').All(part => part.Length > 0 && part is not "." and not ".."));
    }
    private static bool IsSafeGlob(string value) => value.Length is > 0 and <= 200 && !value.StartsWith('/') && !value.Contains('\\') && !value.Any(char.IsControl) && value.Split('/').All(part => part is not "." and not "..");
    private static IEnumerable<string> NormalizePatterns(IEnumerable<string> patterns) => patterns.Where(IsSafeGlob).Distinct(StringComparer.OrdinalIgnoreCase).Take(100);

    private static void WriteAtomic(string fileName, string contents)
    {
        var fullPath = Path.GetFullPath(fileName);
        var tempPath = fullPath + ".tmp-" + Guid.NewGuid().ToString("N");
        try
        {
            using (var stream = new FileStream(tempPath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            using (var writer = new StreamWriter(stream)) { writer.Write(contents); writer.Flush(); stream.Flush(true); }
            File.Move(tempPath, fullPath, true);
        }
        finally { if (File.Exists(tempPath)) File.Delete(tempPath); }
    }

    private void BackupCurrentPreferencesIfChanged()
    {
        var current = BuildResultPreferences();
        if (JsonSerializer.Serialize(current) == JsonSerializer.Serialize(_originalPreferences)) return;
        var source = Path.Combine(OctoShipWorkspacePolicyService.DataDirectory, "preferences.json");
        if (!File.Exists(source)) return;
        var backup = source + ".backup-" + DateTime.UtcNow.ToString("yyyyMMdd-HHmmss") + ".json";
        File.Copy(source, backup, false);
    }

    private sealed record SettingsPackage(OctoCatPreferences Preferences, IReadOnlyList<string> SensitivePatterns, IReadOnlyList<DestinationPreset> DestinationPresets)
    { public int SchemaVersion { get; init; } = 2; }
}

/// <summary>A display label paired with the original owner/repository|branch|folder value.</summary>
public sealed record DestinationPreset(string Label, string Value);
