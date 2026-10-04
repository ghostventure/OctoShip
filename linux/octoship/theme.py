"""Shared dark palette for ttk controls, classic Tk widgets, and popup windows."""
from tkinter import ttk

BACKGROUND = '#0b1020'
SURFACE = '#182335'
TEXT = '#e6edf3'
MUTED = '#93a4ba'
BORDER = '#35455d'
ACCENT = '#1c4f57'
HOVER = '#286872'
FOCUS = '#80cbc4'
SELECT = '#245d73'


def apply_dark_theme(root):
    root.configure(background=BACKGROUND)
    # Tk's option database also reaches subsequently created Toplevels, text
    # editors, combobox listboxes, and Tk file/message dialogs.
    defaults = {
        '*background': BACKGROUND, '*foreground': TEXT,
        '*activeBackground': HOVER, '*activeForeground': TEXT,
        '*disabledForeground': MUTED, '*selectBackground': SELECT,
        '*selectForeground': TEXT, '*insertBackground': TEXT,
        '*highlightBackground': BORDER, '*highlightColor': FOCUS,
        '*Text.background': SURFACE, '*Text.foreground': TEXT,
        '*Text.insertBackground': TEXT, '*Text.selectBackground': SELECT,
        '*Text.selectForeground': TEXT, '*Text.relief': 'flat',
        '*Text.highlightThickness': 1, '*Text.highlightBackground': BORDER,
        '*Text.highlightColor': FOCUS,
        '*Listbox.background': SURFACE, '*Listbox.foreground': TEXT,
        '*Listbox.selectBackground': SELECT, '*Listbox.selectForeground': TEXT,
        '*Entry.background': SURFACE, '*Entry.foreground': TEXT,
        '*Menu.background': SURFACE, '*Menu.foreground': TEXT,
        '*TCombobox*Listbox.background': SURFACE,
        '*TCombobox*Listbox.foreground': TEXT,
        '*TCombobox*Listbox.selectBackground': SELECT,
        '*TCombobox*Listbox.selectForeground': TEXT,
    }
    for pattern, value in defaults.items():
        root.option_add(pattern, value)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=BACKGROUND, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    troughcolor=BACKGROUND, selectbackground=SELECT,
                    selectforeground=TEXT, insertcolor=TEXT)
    style.configure('TFrame', background=BACKGROUND)
    style.configure('TLabel', background=BACKGROUND, foreground=TEXT)
    style.configure('Header.TLabel', font=('Sans', 23, 'bold'))
    style.configure('TLabelframe', background=BACKGROUND, bordercolor=BORDER)
    style.configure('TLabelframe.Label', background=BACKGROUND, foreground=MUTED)
    style.configure('TButton', background=ACCENT, foreground=TEXT, padding=4,
                    bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT,
                    focuscolor=FOCUS)
    style.map('TButton', background=[('disabled', SURFACE), ('pressed', SELECT), ('active', HOVER)],
              foreground=[('disabled', MUTED)], bordercolor=[('focus', FOCUS)],
              lightcolor=[('active', HOVER)], darkcolor=[('active', HOVER)])
    for name in ('TEntry', 'TCombobox'):
        style.configure(name, fieldbackground=SURFACE, background=SURFACE,
                        foreground=TEXT, arrowcolor=TEXT, insertcolor=TEXT,
                        selectbackground=SELECT, selectforeground=TEXT,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.map(name, fieldbackground=[('disabled', BACKGROUND), ('readonly', SURFACE)],
                  foreground=[('disabled', MUTED), ('readonly', TEXT)],
                  background=[('active', HOVER), ('readonly', SURFACE)],
                  selectbackground=[('!disabled', SELECT)], selectforeground=[('!disabled', TEXT)],
                  bordercolor=[('focus', FOCUS)], arrowcolor=[('disabled', MUTED)])
    for name in ('TCheckbutton', 'TRadiobutton'):
        style.configure(name, background=BACKGROUND, foreground=TEXT,
                        indicatorbackground=SURFACE, indicatorforeground=TEXT,
                        focuscolor=FOCUS)
        style.map(name, background=[('active', SURFACE)], foreground=[('disabled', MUTED)],
                  indicatorbackground=[('disabled', BACKGROUND), ('selected', ACCENT), ('active', HOVER)],
                  indicatorforeground=[('disabled', MUTED), ('selected', TEXT)])
    style.configure('TNotebook', background=BACKGROUND, bordercolor=BORDER)
    style.configure('TNotebook.Tab', background=SURFACE, foreground=MUTED,
                    lightcolor=BORDER, padding=(10, 5))
    style.map('TNotebook.Tab', background=[('selected', ACCENT), ('active', HOVER)],
              foreground=[('selected', TEXT), ('active', TEXT)])
    style.configure('Treeview', background=SURFACE, fieldbackground=SURFACE,
                    foreground=TEXT, rowheight=26, bordercolor=BORDER)
    style.map('Treeview', background=[('selected', SELECT)], foreground=[('selected', TEXT)])
    style.configure('Treeview.Heading', background=ACCENT, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)
    style.map('Treeview.Heading', background=[('active', HOVER)], foreground=[('active', TEXT)])
    for name in ('Vertical.TScrollbar', 'Horizontal.TScrollbar'):
        style.configure(name, background=BORDER, troughcolor=BACKGROUND,
                        arrowcolor=TEXT, bordercolor=BACKGROUND,
                        lightcolor=BORDER, darkcolor=BORDER)
        style.map(name, background=[('active', HOVER), ('pressed', SELECT)])
    style.configure('Horizontal.TProgressbar', background=HOVER, troughcolor=SURFACE,
                    bordercolor=BORDER, lightcolor=HOVER, darkcolor=HOVER)
    style.configure('TSeparator', background=BORDER)
    return style
