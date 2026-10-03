using System;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;

namespace FileToGitHub
{
    /// <summary>
    /// Interaction logic for App.xaml
    /// </summary>
    public partial class App : Application
    {
        private Mutex? _instanceMutex;

        protected override async void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);
            bool createdNew;
            try
            {
                _instanceMutex = new Mutex(true, @"Local\OctoCat.SingleInstance", out createdNew);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"OctoShip for GitHub could not check whether another copy is running.\n\n{ex.Message}", "OctoShip startup", MessageBoxButton.OK, MessageBoxImage.Error);
                Shutdown(1);
                return;
            }

            if (!createdNew)
            {
                _instanceMutex.Dispose();
                _instanceMutex = null;
                MessageBox.Show("OctoShip for GitHub is already running. Switch to the open window to continue.", "OctoShip for GitHub is already open", MessageBoxButton.OK, MessageBoxImage.Information);
                Shutdown();
                return;
            }
            var splash = new SplashWindow();
            splash.Show();
            await Task.Delay(950);
            var main = new MainWindow();
            MainWindow = main;
            main.Show();
            splash.Close();
            main.Activate();
        }

        protected override void OnExit(ExitEventArgs e)
        {
            try { _instanceMutex?.ReleaseMutex(); }
            catch (ApplicationException) { }
            finally
            {
                _instanceMutex?.Dispose();
                _instanceMutex = null;
            }
            base.OnExit(e);
        }
    }
}
