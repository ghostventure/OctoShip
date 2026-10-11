using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace FileToGitHub;

/// <summary>Covers native file dialogs as well as the WPF workspace during an app lock.</summary>
internal sealed class SessionNativeWindows
{
    private readonly Dictionary<IntPtr, bool> _hidden = new();
    private uint _lastInput;
    public bool HasNewAppInput()
    {
        var input = new LastInput { Size = (uint)Marshal.SizeOf<LastInput>() };
        if (!GetLastInputInfo(ref input) || input.Tick == _lastInput) return false;
        _lastInput = input.Tick;
        GetWindowThreadProcessId(GetForegroundWindow(), out var process);
        return process == Environment.ProcessId;
    }
    public void HideDialogs(ISet<IntPtr> wpfWindows)
    {
        EnumThreadWindows(GetCurrentThreadId(), (handle, _) =>
        {
            if (wpfWindows.Contains(handle) || _hidden.ContainsKey(handle) || !IsWindowVisible(handle)) return true;
            // Only hide windows owned by an application window: leave unrelated OS surfaces alone.
            var owner = GetWindow(handle, 4);
            if (owner == IntPtr.Zero) return true;
            GetWindowThreadProcessId(owner, out var process);
            if (process != Environment.ProcessId) return true;
            _hidden[handle] = IsWindowEnabled(handle);
            EnableWindow(handle, false); ShowWindow(handle, 0);
            return true;
        }, IntPtr.Zero);
    }
    public void Restore()
    {
        foreach (var pair in _hidden)
            if (IsWindow(pair.Key)) { EnableWindow(pair.Key, pair.Value); ShowWindow(pair.Key, 8); }
        _hidden.Clear();
    }
    [StructLayout(LayoutKind.Sequential)] private struct LastInput { public uint Size; public uint Tick; }
    private delegate bool EnumWindow(IntPtr window, IntPtr data);
    [DllImport("user32.dll")] private static extern bool GetLastInputInfo(ref LastInput input);
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] private static extern bool EnumThreadWindows(uint thread, EnumWindow callback, IntPtr data);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] private static extern bool IsWindowEnabled(IntPtr window);
    [DllImport("user32.dll")] private static extern bool IsWindow(IntPtr window);
    [DllImport("user32.dll")] private static extern IntPtr GetWindow(IntPtr window, uint command);
    [DllImport("user32.dll")] private static extern bool EnableWindow(IntPtr window, bool enabled);
    [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr window, int command);
}
