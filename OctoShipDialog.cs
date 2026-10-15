using System;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Threading;

namespace FileToGitHub;

/// <summary>Consistent app-owned notices and confirmations. Windows authentication remains native.</summary>
public sealed class OctoShipDialog : Window
{
    public MessageBoxResult Result { get; private set; }
    public OctoShipDialog(string message, string caption, MessageBoxButton buttons, MessageBoxImage image, MessageBoxResult defaultResult)
    {
        UniformUi.Prepare(this);
        Title = caption + " — OctoShip"; Width = 580; MinWidth = 360; SizeToContent = SizeToContent.Height;
        MaxHeight = Math.Min(720, SystemParameters.WorkArea.Height - 40); WindowStartupLocation = WindowStartupLocation.CenterOwner;
        Result = buttons == MessageBoxButton.YesNo ? MessageBoxResult.No : buttons == MessageBoxButton.OK ? MessageBoxResult.OK : MessageBoxResult.Cancel;
        var root = new Grid { Margin = new Thickness(24) };
        root.RowDefinitions.Add(new() { Height = GridLength.Auto }); root.RowDefinitions.Add(new() { Height = new GridLength(1, GridUnitType.Star) }); root.RowDefinitions.Add(new() { Height = GridLength.Auto });
        var heading = new TextBlock { Text = caption, FontSize = 24, FontWeight = FontWeights.SemiBold, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 16) };
        heading.SetResourceReference(TextBlock.ForegroundProperty, image == MessageBoxImage.Error ? "ErrorBrush" : image == MessageBoxImage.Warning ? "WarningBrush" : "TextBrush");
        root.Children.Add(heading);
        var body = new TextBlock { Text = message, TextWrapping = TextWrapping.Wrap };
        var scroll = new ScrollViewer { Content = body, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, MaxHeight = 440, Margin = new Thickness(0, 0, 0, 20) };
        Grid.SetRow(scroll, 1); root.Children.Add(scroll);
        var actions = new WrapPanel { HorizontalAlignment = HorizontalAlignment.Right }; Grid.SetRow(actions, 2); root.Children.Add(actions);
        var results = buttons switch
        {
            MessageBoxButton.YesNo => new[] { MessageBoxResult.No, MessageBoxResult.Yes },
            MessageBoxButton.YesNoCancel => new[] { MessageBoxResult.Cancel, MessageBoxResult.No, MessageBoxResult.Yes },
            MessageBoxButton.OKCancel => new[] { MessageBoxResult.Cancel, MessageBoxResult.OK },
            _ => new[] { MessageBoxResult.OK }
        };
        foreach (var result in results)
        {
            var button = new Button { Content = result.ToString(), MinWidth = 88,
                IsDefault = result == (defaultResult == MessageBoxResult.None ? Result : defaultResult),
                IsCancel = result == Result };
            AutomationProperties.SetName(button, result.ToString());
            button.Click += (_, _) => { Result = result; Close(); };
            actions.Children.Add(button);
        }
        Content = root;
    }
    public static MessageBoxResult Show(string message, string caption = "OctoShip", MessageBoxButton buttons = MessageBoxButton.OK,
        MessageBoxImage image = MessageBoxImage.None, MessageBoxResult defaultResult = MessageBoxResult.None)
        => Show(null, message, caption, buttons, image, defaultResult);
    public static MessageBoxResult Show(Window? owner, string message, string caption = "OctoShip", MessageBoxButton buttons = MessageBoxButton.OK,
        MessageBoxImage image = MessageBoxImage.None, MessageBoxResult defaultResult = MessageBoxResult.None)
    {
        var initiatingFocus = owner is { IsVisible: true } ? Keyboard.FocusedElement : null;
        var dialog = new OctoShipDialog(message, caption, buttons, image, defaultResult);
        if (owner is { IsVisible: true }) dialog.Owner = owner;
        else dialog.WindowStartupLocation = WindowStartupLocation.CenterScreen;
        dialog.ShowDialog();
        if (owner is { IsVisible: true })
        {
            owner.Dispatcher.BeginInvoke(DispatcherPriority.Input, new Action(() =>
            {
                if (initiatingFocus is UIElement element && element.IsVisible && element.IsEnabled && element.Focusable)
                    Keyboard.Focus(element);
                else if (owner.IsVisible)
                    owner.Focus();
            }));
        }
        return dialog.Result;
    }
}
