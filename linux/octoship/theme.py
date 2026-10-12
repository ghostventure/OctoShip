"""Shared modern desktop palette, typography and scalable rounded controls."""
import math
import tkinter as tk
from tkinter import ttk, font

BACKGROUND = '#111318'
SURFACE = '#1a1d25'
SIDEBAR = '#0d0f14'
TEXT = '#edf0f7'
MUTED = '#939baa'
BORDER = '#2b303c'
ACCENT = '#9270ff'
HOVER = '#a58aff'
FOCUS = '#b5a0ff'
SELECT = '#342c50'
FONT = 'Sans'


def rounded_image(root, fill, outline, background=BACKGROUND, size=16, radius=5):
    """Nine-slice artwork with antialiased corners; no image dependencies."""
    def rgb(value): return tuple(int(value[i:i+2],16) for i in (1,3,5))
    outer, inner, bg = rgb(outline), rgb(fill), rgb(background)
    rows=[]
    for y in range(size):
        row=[]
        for x in range(size):
            dx=max(radius-x-.5,0,x+.5-(size-radius))
            dy=max(radius-y-.5,0,y+.5-(size-radius))
            distance=math.hypot(dx,dy)
            edge=max(0,min(1,radius-distance))
            inset=max(0,min(1,radius-1-distance)) if dx or dy else (0 if min(x,y,size-x-1,size-y-1)==0 else 1)
            color=[round(bg[i]*(1-edge)+(outer[i]*(1-inset)+inner[i]*inset)*edge) for i in range(3)]
            row.append('#%02x%02x%02x'%tuple(color))
        rows.append('{'+' '.join(row)+'}')
    image=tk.PhotoImage(master=root,width=size,height=size)
    image.put(' '.join(rows));return image


def apply_dark_theme(root):
    global FONT
    available=set(font.families(root))
    FONT=next((name for name in ('Inter','Noto Sans','DejaVu Sans','Liberation Sans') if name in available),'Sans')
    for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont','TkTooltipFont'):
        font.nametofont(name,root).configure(family=FONT,size=10)
    font.nametofont('TkFixedFont',root).configure(family='DejaVu Sans Mono',size=10)
    root.configure(background=BACKGROUND)
    for pattern,value in {
        '*background':BACKGROUND,'*foreground':TEXT,
        '*activeBackground':SELECT,'*activeForeground':TEXT,'*disabledForeground':MUTED,
        '*selectBackground':SELECT,'*selectForeground':TEXT,'*insertBackground':TEXT,
        '*highlightBackground':BORDER,'*highlightColor':FOCUS,
        '*Text.background':SURFACE,'*Text.foreground':TEXT,'*Text.relief':'flat',
        '*Text.highlightThickness':1,'*Text.highlightBackground':BORDER,
        '*Text.font':'TkTextFont','*Listbox.background':SURFACE,'*Entry.background':SURFACE,
        '*Menu.background':SURFACE,'*TCombobox*Listbox.background':SURFACE,
        '*TCombobox*Listbox.foreground':TEXT,'*TCombobox*Listbox.selectBackground':SELECT,
    }.items(): root.option_add(pattern,value)
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',background=BACKGROUND,foreground=TEXT,font=(FONT,10),
                    bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER,
                    troughcolor=BACKGROUND,selectbackground=SELECT,selectforeground=TEXT)
    style.configure('TFrame',background=BACKGROUND)
    style.configure('TLabel',background=BACKGROUND,foreground=TEXT)
    style.configure('Header.TLabel',font=(FONT,24,'bold'))
    style.configure('Title.TLabel',font=(FONT,22,'bold'))
    style.configure('Section.TLabel',font=(FONT,12,'bold'))
    style.configure('Muted.TLabel',foreground=MUTED)
    style.configure('Eyebrow.TLabel',foreground=MUTED,font=(FONT,9,'bold'))
    style.configure('Badge.TLabel',background=SELECT,foreground=FOCUS,padding=(9,4),font=(FONT,9,'bold'))
    style.configure('Sidebar.TFrame',background=SIDEBAR)
    style.configure('Sidebar.TLabel',background=SIDEBAR,foreground=MUTED)
    style.configure('Brand.TLabel',background=SIDEBAR,foreground=TEXT,font=(FONT,17,'bold'))
    style.configure('TLabelframe',background=BACKGROUND,bordercolor=BORDER,relief='flat')
    style.configure('TLabelframe.Label',background=BACKGROUND,foreground=MUTED,font=(FONT,9,'bold'))
    root._theme_images=[]
    for name,base,hover,foreground,bg in (
        ('TButton',SURFACE,'#262b36',TEXT,BACKGROUND),
        ('Primary.TButton',ACCENT,HOVER,'#ffffff',BACKGROUND),
        ('Ghost.TButton',BACKGROUND,SURFACE,MUTED,BACKGROUND),
        ('Nav.TButton',SIDEBAR,SURFACE,MUTED,SIDEBAR),
        ('Active.Nav.TButton',SELECT,'#413460',TEXT,SIDEBAR),
    ):
        images=[rounded_image(root,c,c if name!='TButton' else BORDER,bg) for c in (base,hover,SURFACE)]
        root._theme_images.extend(images)
        element=name+'.rounded'
        if element not in style.element_names():
            style.element_create(element,'image',images[0],('disabled',images[2]),('active',images[1]),('pressed',images[1]),border=5,sticky='nsew')
        style.layout(name,[(element,{'sticky':'nsew','children':[('Button.focus',{'sticky':'nsew','children':[('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})]})])
        style.configure(name,foreground=foreground,padding=(8,3),anchor='center',font=(FONT,10),focuscolor=FOCUS)
        style.map(name,foreground=[('disabled','#626b7c')])
    style.configure('Nav.TButton',anchor='w',padding=(6,7))
    style.configure('Active.Nav.TButton',anchor='w',padding=(6,7))
    for name in ('TEntry','TCombobox','TSpinbox'):
        style.configure(name,fieldbackground=SURFACE,background=SURFACE,foreground=TEXT,
                        arrowcolor=MUTED,insertcolor=TEXT,selectbackground=SELECT,
                        bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER,padding=5,relief='flat')
        style.map(name,fieldbackground=[('readonly',SURFACE),('disabled',BACKGROUND)],
                  foreground=[('readonly',TEXT),('disabled',MUTED)],
                  bordercolor=[('focus',FOCUS)],lightcolor=[('focus',FOCUS)],darkcolor=[('focus',FOCUS)],
                  arrowcolor=[('disabled',MUTED),('active',TEXT)])
    for name in ('TCheckbutton','TRadiobutton'):
        style.configure(name,background=BACKGROUND,foreground=MUTED,indicatorbackground=SURFACE,
                        indicatorforeground=TEXT,focuscolor=FOCUS,padding=(0,3))
        style.map(name,background=[('active',BACKGROUND)],foreground=[('active',TEXT),('disabled','#626b7c')],
                  indicatorbackground=[('selected',ACCENT),('active',SELECT)])
    style.configure('TNotebook',background=BACKGROUND,borderwidth=0,tabmargins=(0,0,0,10))
    style.configure('TNotebook.Tab',background=BACKGROUND,foreground=MUTED,padding=(13,9),borderwidth=0)
    style.map('TNotebook.Tab',background=[('selected',SURFACE),('active',SURFACE)],foreground=[('selected',TEXT),('active',TEXT)])
    style.layout('Workspace.TNotebook.Tab',[])
    style.configure('Workspace.TNotebook',background=BACKGROUND,borderwidth=0,tabmargins=0)
    style.configure('Treeview',background=SURFACE,fieldbackground=SURFACE,foreground=TEXT,
                    rowheight=34,borderwidth=0,relief='flat')
    style.map('Treeview',background=[('selected',SELECT)],foreground=[('selected',TEXT)])
    style.configure('Treeview.Heading',background=SURFACE,foreground=MUTED,font=(FONT,9,'bold'),
                    borderwidth=0,relief='flat',padding=(12,10))
    style.map('Treeview.Heading',background=[('active','#242936')])
    for name in ('Vertical.TScrollbar','Horizontal.TScrollbar'):
        style.configure(name,background=BORDER,troughcolor=BACKGROUND,arrowcolor=MUTED,
                        borderwidth=0,lightcolor=BORDER,darkcolor=BORDER,arrowsize=11)
        style.map(name,background=[('active',MUTED)])
    style.configure('Horizontal.TProgressbar',background=ACCENT,troughcolor=SURFACE,borderwidth=0,
                    lightcolor=ACCENT,darkcolor=ACCENT,thickness=3)
    style.configure('TSeparator',background=BORDER)
    return style
