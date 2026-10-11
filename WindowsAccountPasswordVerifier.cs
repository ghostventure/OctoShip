using System;
using System.Runtime.InteropServices;
using System.Security.Principal;
using Microsoft.Win32.SafeHandles;

namespace FileToGitHub;

/// <summary>Native Windows password fallback. No password is converted to a managed string or saved.</summary>
public static class WindowsAccountPasswordVerifier
{
    public static bool Verify(IntPtr owner)
    {
        var info = new CredentialUiInfo { Size = Marshal.SizeOf<CredentialUiInfo>(), Owner = owner,
            Caption = "Unlock OctoShip", Message = "Enter the password for your current Windows account. OctoShip does not save it." };
        uint package = 0, length = 0;
        IntPtr packed = IntPtr.Zero, user = IntPtr.Zero, domain = IntPtr.Zero, password = IntPtr.Zero;
        int userBytes = 0, domainBytes = 0, passwordBytes = 0;
        try
        {
            // Generic credentials allow a password fallback; do not offer a Save checkbox.
            if (CredUIPromptForWindowsCredentialsW(ref info, 0, ref package, IntPtr.Zero, 0, out packed, out length, IntPtr.Zero, 1) != 0) return false;
            uint users = 0, domains = 0, passwords = 0;
            CredUnPackAuthenticationBufferW(0, packed, length, IntPtr.Zero, ref users, IntPtr.Zero, ref domains, IntPtr.Zero, ref passwords);
            if (Marshal.GetLastWin32Error() != 122 || users == 0 || users > 32768 || domains > 32768 || passwords == 0 || passwords > 32768) return false;
            userBytes = checked((int)users * 2); domainBytes = checked((int)Math.Max(1, domains) * 2); passwordBytes = checked((int)passwords * 2);
            user = Marshal.AllocCoTaskMem(userBytes); domain = Marshal.AllocCoTaskMem(domainBytes); password = Marshal.AllocCoTaskMem(passwordBytes);
            if (!CredUnPackAuthenticationBufferW(0, packed, length, user, ref users, domain, ref domains, password, ref passwords)) return false;
            var username = Marshal.PtrToStringUni(user) ?? "";
            var domainName = domains > 0 ? Marshal.PtrToStringUni(domain) : null;
            if (username.Length == 0 || Marshal.ReadInt16(password) == 0) return false;
            var separator = username.IndexOf('\\');
            if (separator >= 0) { domainName = username[..separator]; username = username[(separator + 1)..]; }
            if (!LogonUserW(username, string.IsNullOrEmpty(domainName) ? null : domainName, password, 2, 0, out var token)) return false;
            using (token)
            using (var verified = new WindowsIdentity(token.DangerousGetHandle()))
            using (var current = WindowsIdentity.GetCurrent())
                return current.User is not null && verified.User is not null && current.User.Equals(verified.User);
        }
        finally
        {
            ClearAndFree(password, passwordBytes); ClearAndFree(user, userBytes); ClearAndFree(domain, domainBytes);
            ClearAndFree(packed, checked((int)length));
        }
    }
    private static void ClearAndFree(IntPtr memory, int bytes)
    {
        if (memory == IntPtr.Zero) return;
        for (var offset = 0; offset < bytes; offset++) Marshal.WriteByte(memory, offset, 0);
        Marshal.FreeCoTaskMem(memory);
    }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct CredentialUiInfo
    {
        public int Size;
        public IntPtr Owner;
        public string Message;
        public string Caption;
        public IntPtr Banner;
    }
    [DllImport("credui.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint CredUIPromptForWindowsCredentialsW(ref CredentialUiInfo info, uint error, ref uint package,
        IntPtr input, uint inputSize, out IntPtr output, out uint outputSize, IntPtr save, uint flags);
    [DllImport("credui.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CredUnPackAuthenticationBufferW(uint flags, IntPtr buffer, uint size, IntPtr user, ref uint userSize,
        IntPtr domain, ref uint domainSize, IntPtr password, ref uint passwordSize);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool LogonUserW(string user, string? domain, IntPtr password, int type, int provider, out SafeAccessTokenHandle token);
}
