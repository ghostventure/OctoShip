using System;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;

namespace FileToGitHub;

public sealed class AppearanceControls : StackPanel
{
    public AppearanceControls()
    {
        Children.Add(new TextBlock { Text = "Display preferences", FontSize = 18, FontWeight = FontWeights.SemiBold, Margin = new Thickness(0, 0, 0, 8) });
        Children.Add(new TextBlock { Text = "Text size and spacing apply to every OctoShip window. Changes are saved on this computer.", TextWrapping = TextWrapping.Wrap });
        var row = new WrapPanel { Margin = new Thickness(0, 8, 0, 4) };
        row.Children.Add(new TextBlock { Text = "Text size", VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 12, 0) });
        var size = new ComboBox { Width = 100, ItemsSource = new double[] { 12, 14, 16, 18 }, SelectedItem = UniformUi.Preferences.TextSize };
        AutomationProperties.SetName(size, "Application text size"); row.Children.Add(size);
        var compact = new CheckBox { Content = "Compact spacing", IsChecked = UniformUi.Preferences.Compact, Margin = new Thickness(16, 0, 0, 0), VerticalAlignment = VerticalAlignment.Center };
        AutomationProperties.SetName(compact, "Use compact spacing in all windows"); row.Children.Add(compact);
        Children.Add(row);
        var status = new TextBlock { TextWrapping = TextWrapping.Wrap }; Children.Add(status);
        void Apply()
        {
            try { UniformUi.ApplyPreferences(new(size.SelectedItem is double value ? value : 14, compact.IsChecked == true)); status.Text = "Display preferences saved for all windows."; }
            catch { status.Text = "Display updated for this session, but it could not be saved. Check LocalAppData access."; }
        }
        size.SelectionChanged += (_, _) => Apply(); compact.Checked += (_, _) => Apply(); compact.Unchecked += (_, _) => Apply();
    }
}
