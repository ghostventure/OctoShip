using System.Windows;
using System.Windows.Controls;
using System.Text;

namespace FileToGitHub;

/// <summary>A confirmation dialog whose primary action is explicit and whose safe choice is the default.</summary>
public sealed class DestructiveActionConfirmation : Window
{
    private DestructiveActionConfirmation(string title, string details, string actionLabel, string safeLabel)
    {
        Title = title;
        Width = 500;
        SizeToContent = SizeToContent.Height;
        MinWidth = 420;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        ResizeMode = ResizeMode.NoResize;
        ShowInTaskbar = false;

        var layout = new StackPanel { Margin = new Thickness(22) };
        layout.Children.Add(new TextBlock
        {
            Text = details,
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 20),
            MaxWidth = 450
        });

        var buttons = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        var safe = new Button { Content = safeLabel, IsCancel = true, IsDefault = true, MinWidth = 120, Margin = new Thickness(0, 0, 8, 0) };
        safe.Click += (_, _) => { DialogResult = false; Close(); };
        var action = new Button { Content = actionLabel, MinWidth = 140 };
        action.Click += (_, _) => { DialogResult = true; Close(); };
        buttons.Children.Add(safe);
        buttons.Children.Add(action);
        layout.Children.Add(buttons);
        Content = layout;
        // Enter and Escape both choose the safe action; the destructive button is never the default.
    }

    public static Window Create(string title, string details, string actionLabel, string safeLabel) =>
        new DestructiveActionConfirmation(title, details, actionLabel, safeLabel);

    public static bool Confirm(Window owner, string title, string details, string actionLabel, string safeLabel)
    {
        var dialog = Create(title, details, actionLabel, safeLabel);
        dialog.Owner = owner;
        return dialog.ShowDialog() == true;
    }

    public static string DescribePreset(string label, string value)
    {
        var parts = value.Split('|', 3);
        var destination = parts.Length == 3
            ? $"Repository: {parts[0]}\nBranch: {parts[1]}\nUpload folder: {(parts[2].Length == 0 ? "(repository root)" : parts[2])}"
            : $"Saved destination: {value}";
        return $"Delete the OctoShip destination preset “{label}”?\n\n{destination}\n\nThis removes only the local preset. It does not delete the GitHub repository or any files. The change takes effect only when you select Save.";
    }

    public static string DescribeHistory(int searchCount, int recentCount, int presetCount, bool search, bool recent, bool destinations)
    {
        var targets = new StringBuilder();
        if (search) targets.AppendLine($"Search history: {searchCount} entries");
        if (recent) targets.AppendLine($"Recent repositories: {recentCount} entries");
        if (destinations) targets.AppendLine($"Destination presets: {presetCount} entries");
        return "Clear these local OctoShip items?\n\n" + targets.ToString().TrimEnd() +
            "\n\nThis only removes the selected saved entries from OctoShip; it does not change anything on GitHub. The change takes effect only when you select Save.";
    }
}
