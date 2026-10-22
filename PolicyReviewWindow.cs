using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace FileToGitHub;

/// <summary>Read-only view of active local policy and a credential-free settings import preview.</summary>
public sealed class PolicyReviewWindow : Window
{
    private readonly OctoCatPreferences _current;
    private readonly TextBlock _preview = new() { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 10, 0, 0) };

    public PolicyReviewWindow(OctoCatPreferences current)
    {
        _current = current;
        Title = "Effective policies and import preview"; Width = 680; Height = 540; MinWidth = 560; MinHeight = 400;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        Background = new SolidColorBrush(Color.FromRgb(16, 21, 30)); Foreground = Brushes.WhiteSmoke;
        var root = new StackPanel { Margin = new Thickness(22) }; Content = root;
        root.Children.Add(new TextBlock { Text = "Effective local policies", FontSize = 21, FontWeight = FontWeights.SemiBold });
        root.Children.Add(new TextBlock { Text = "These app preferences apply on this device. GitHub organization and repository rules are enforced by GitHub.", Foreground = Brushes.LightGray, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 6, 0, 12) });
        var policies = new[]
        {
            $"Privacy mode: {(_current.PrivacyMode ? "On; local search history is not retained" : "Off; selected workspace history may be retained")}",
            $"Screen share mask: {(_current.ScreenSharePrivacyMask ? "On" : "Off")}",
            $"Private-only repositories: {(_current.PrivateOnlyRepositories.Count == 0 ? "None configured" : _current.ScreenSharePrivacyMask ? $"{_current.PrivateOnlyRepositories.Count} configured (names hidden)" : string.Join(", ", _current.PrivateOnlyRepositories))}",
            $"Update channel: {_current.UpdateChannel}; automatic updates: {(_current.AutomaticUpdates ? "On" : "Off")}",
            $"Clipboard clearing: {(_current.ClearCopiedTextAfterSeconds == 0 ? "Off" : $"after {_current.ClearCopiedTextAfterSeconds} seconds")}",
            $"Archived workspaces: {_current.ArchivedWorkspaces.Count}"
        };
        foreach (var policy in policies) root.Children.Add(new TextBlock { Text = "• " + policy, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 4, 0, 4) });
        var button = new Button { Content = "Choose settings file to preview", Padding = new Thickness(12, 8, 12, 8), Margin = new Thickness(0, 16, 0, 0), HorizontalAlignment = HorizontalAlignment.Left };
        button.Click += PreviewImport_Click; root.Children.Add(button); root.Children.Add(_preview);
    }

    private void PreviewImport_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new Microsoft.Win32.OpenFileDialog { Filter = "OctoShip settings (*.json)|*.json|All files (*.*)|*.*", Title = "Preview credential-free settings import" };
        if (dialog.ShowDialog(this) != true) return;
        try
        {
            var imported = OctoCatPreferencesService.Import(dialog.FileName);
            var changes = new[]
            {
                Change("Privacy mode", _current.PrivacyMode, imported.PrivacyMode),
                Change("Screen share mask", _current.ScreenSharePrivacyMask, imported.ScreenSharePrivacyMask),
                Change("Update channel", _current.UpdateChannel, imported.UpdateChannel),
                Change("Automatic updates", _current.AutomaticUpdates, imported.AutomaticUpdates),
                Change("Clipboard clear delay", _current.ClearCopiedTextAfterSeconds, imported.ClearCopiedTextAfterSeconds),
                Change("Private-only repositories", string.Join(", ", _current.PrivateOnlyRepositories), string.Join(", ", imported.PrivateOnlyRepositories)),
                Change("Archived workspaces", _current.ArchivedWorkspaces.Count, imported.ArchivedWorkspaces.Count)
            }.Where(value => value is not null).ToArray();
            _preview.Text = changes.Length == 0
                ? "Preview complete: this file would not change the displayed policy values. No settings were applied."
                : "Proposed policy changes (preview only):\n" + string.Join("\n", changes) + "\n\nNo settings were applied. Use the settings editor to perform an import.";
        }
        catch (Exception ex) { _preview.Text = "Could not preview this settings file: " + ex.Message; }
    }

    private static string? Change<T>(string label, T before, T after) => Equals(before, after) ? null : $"• {label}: {before} → {after}";
}
