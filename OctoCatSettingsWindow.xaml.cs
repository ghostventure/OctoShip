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
    private OctoCatPreferences _preferences;
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true, PropertyNameCaseInsensitive = true };

    public OctoCatPreferences Preferences { get; private set; }
    public IReadOnlyList<string> SensitivePatterns { get; private set; }
    public IReadOnlyList<DestinationPreset> DestinationPresets { get; private set; }

    public OctoCatSettingsWindow(OctoCatPreferences? preferences = null, IEnumerable<string>? sensitivePatterns = null,
        IEnumerable<DestinationPreset>? destinationPresets = null)
    {
        InitializeComponent();
        _preferences = OctoCatPreferencesService.Normalize(preferences ?? new OctoCatPreferences());
        Preferences = _preferences;
        SensitivePatterns = Array.Empty<string>();
        DestinationPresets = Array.Empty<DestinationPreset>();
        PrivacyCheck.IsChecked = _preferences.PrivacyMode;
        ChannelPicker.SelectedIndex = _preferences.UpdateChannel == OctoCatUpdateChannel.Preview ? 1 : 0;
        _patterns.AddRange(NormalizePatterns(sensitivePatterns ?? Array.Empty<string>()));
        _presets.AddRange((destinationPresets ?? ToPresets(_preferences.Destinations)).Where(IsValidPreset).Take(50));
        PatternList.ItemsSource = _patterns.ToArray();
        RefreshPresets();
    }

    private void ClearHistory_Click(object sender, RoutedEventArgs e)
    {
        var search = ClearSearchCheck.IsChecked == true;
        var recent = ClearRecentCheck.IsChecked == true;
        var destinations = ClearDestinationsCheck.IsChecked == true;
        if (!search && !recent && !destinations) { SetStatus("Select at least one history type to clear.", true); return; }
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
        if (!IsSafeGlob(pattern)) { SetStatus("Enter a safe glob (for example, *.pem or **/.env).", true); return; }
        if (_patterns.Contains(pattern, StringComparer.OrdinalIgnoreCase)) { SetStatus("That pattern is already listed."); return; }
        _patterns.Add(pattern);
        PatternInput.Clear();
        PatternList.ItemsSource = _patterns.ToArray();
        SetStatus("Pattern added. It will warn on matching names; it will not block uploads.");
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
                _preferences = OctoCatPreferencesService.Normalize(package.Preferences);
                _patterns.Clear(); _patterns.AddRange(NormalizePatterns(package.SensitivePatterns ?? Array.Empty<string>()));
                _presets.Clear(); _presets.AddRange((package.DestinationPresets ?? ToPresets(_preferences.Destinations)).Where(IsValidPreset).Take(50));
            }
            PrivacyCheck.IsChecked = _preferences.PrivacyMode;
            ChannelPicker.SelectedIndex = _preferences.UpdateChannel == OctoCatUpdateChannel.Preview ? 1 : 0;
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
        Preferences = BuildResultPreferences();
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
            UpdateChannel = channel,
            Destinations = values,
            SearchHistory = privacy ? Array.Empty<string>() : _preferences.SearchHistory,
            RecentRepositories = privacy ? Array.Empty<string>() : _preferences.RecentRepositories
        };
        return OctoCatPreferencesService.Normalize(result);
    }

    private void RefreshPresets() => PresetList.ItemsSource = _presets.ToArray();
    private void SetStatus(string text, bool error = false)
    {
        StatusText.Text = text;
        StatusText.Foreground = error ? System.Windows.Media.Brushes.OrangeRed : System.Windows.Media.Brushes.LightSteelBlue;
    }

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

    private sealed record SettingsPackage(OctoCatPreferences Preferences, IReadOnlyList<string> SensitivePatterns, IReadOnlyList<DestinationPreset> DestinationPresets);
}

/// <summary>A display label paired with the original owner/repository|branch|folder value.</summary>
public sealed record DestinationPreset(string Label, string Value);
