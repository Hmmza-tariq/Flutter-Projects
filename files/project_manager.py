"""
Hexagone Project Manager v2.0
A modern GUI application for managing multiple projects in a single README.md file.
Features: Create, Edit, Delete, Reorder projects with live preview.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional
import shutil
import webbrowser
import tempfile

# Try to import markdown library
try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False


def md_to_html(md_text: str) -> str:
    """Convert markdown to HTML with dark theme styling"""
    # Basic HTML conversion without markdown library
    html = md_text
    
    # Headers
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # Code/backticks
    html = re.sub(r'`([^`]+)`', r'<code style="background:#333;padding:2px 6px;border-radius:4px;">\1</code>', html)
    
    # Lists
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    
    # Line breaks
    html = html.replace('\n\n', '<br><br>')
    
    return html


class Theme:
    """Modern dark theme colors"""
    BG = "#09090b"
    BG_SECONDARY = "#18181b"
    BG_CARD = "#1c1c1f"
    BG_INPUT = "#27272a"
    BG_HOVER = "#3f3f46"
    
    FG = "#fafafa"
    FG_SECONDARY = "#a1a1aa"
    FG_MUTED = "#71717a"
    
    ACCENT = "#f4f4f5"
    BORDER = "#27272a"
    
    SUCCESS = "#22c55e"
    DANGER = "#ef4444"
    WARNING = "#eab308"
    
    FONT = "Segoe UI"
    FONT_MONO = "Cascadia Code"


class Project:
    """Project data model"""
    def __init__(self):
        self.id = ""
        self.title = ""
        self.short_description = ""
        self.long_description = ""
        self.categories: List[str] = []  # Multiple categories
        self.banner_image = ""  # Can be URL or local path
        self.banner_local_path = ""  # Original local file path
        self.technologies: List[str] = []
        self.features: List[str] = []
        self.links: Dict[str, str] = {}
        self.screenshots: List[str] = []  # List of image paths
        self.screenshots_local_paths: List[str] = []  # Original local paths
        
        # Styling options
        self.show_logo = True
        self.logo_url = ""
        self.logo_position = "center"  # left, center, right - default center
        self.show_border = False
        self.border_style = "rounded"  # rounded, square, none
        self.theme_color = "#000000"  # Accent color for badges
        self.screenshot_layout = "horizontal"  # horizontal, grid
        self.screenshot_size = 200  # Width in pixels
    
    def to_dict(self) -> dict:
        return vars(self).copy()
    
    @staticmethod
    def from_dict(data: dict) -> 'Project':
        p = Project()
        for key, value in data.items():
            if hasattr(p, key):
                setattr(p, key, value)
        return p
    
    @property
    def category_display(self) -> str:
        """Get categories as display string"""
        return ", ".join(self.categories) if self.categories else "—"


class ProjectManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Hexagone Project Manager")
        self.geometry("1500x950")
        self.configure(bg=Theme.BG)
        self.minsize(1200, 700)
        
        # Data
        self.projects: List[Project] = []
        self.selected_index: Optional[int] = None
        self.file_path: Optional[str] = None
        self.has_changes = False
        
        self._setup_styles()
        self._build_ui()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-s>", lambda e: self._export_file())
        self.bind("<Control-n>", lambda e: self._add_project())
        
    def _setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure(".", background=Theme.BG, foreground=Theme.FG)
        style.configure("TFrame", background=Theme.BG)
        style.configure("Card.TFrame", background=Theme.BG_CARD)
        style.configure("TLabel", background=Theme.BG, foreground=Theme.FG, font=(Theme.FONT, 10))
        style.configure("Title.TLabel", font=(Theme.FONT, 24, "bold"))
        style.configure("Subtitle.TLabel", foreground=Theme.FG_MUTED, font=(Theme.FONT, 10))
        style.configure("Section.TLabel", font=(Theme.FONT, 12, "bold"))
        style.configure("Card.TLabel", background=Theme.BG_CARD)
        
        style.configure("TButton", 
                       background=Theme.BG_INPUT,
                       foreground=Theme.FG,
                       font=(Theme.FONT, 10),
                       padding=(16, 10),
                       borderwidth=0)
        style.map("TButton", background=[("active", Theme.BG_HOVER)])
        
        style.configure("Primary.TButton",
                       background=Theme.FG,
                       foreground=Theme.BG,
                       font=(Theme.FONT, 10, "bold"))
        style.map("Primary.TButton", background=[("active", Theme.FG_SECONDARY)])
        
        style.configure("Danger.TButton", background="#7f1d1d")
        style.map("Danger.TButton", background=[("active", Theme.DANGER)])
        
        style.configure("Small.TButton", padding=(10, 6), font=(Theme.FONT, 9))
        
        style.configure("TNotebook", background=Theme.BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                       background=Theme.BG_SECONDARY,
                       foreground=Theme.FG_MUTED,
                       padding=(20, 12),
                       font=(Theme.FONT, 10))
        style.map("TNotebook.Tab",
                 background=[("selected", Theme.BG)],
                 foreground=[("selected", Theme.FG)])
        
        style.configure("Treeview",
                       background=Theme.BG_CARD,
                       foreground=Theme.FG,
                       fieldbackground=Theme.BG_CARD,
                       borderwidth=0,
                       font=(Theme.FONT, 10),
                       rowheight=40)
        style.map("Treeview",
                 background=[("selected", Theme.BG_HOVER)],
                 foreground=[("selected", Theme.FG)])
        style.configure("Treeview.Heading",
                       background=Theme.BG_INPUT,
                       foreground=Theme.FG,
                       font=(Theme.FONT, 10, "bold"))
                       
    def _build_ui(self):
        """Build the main UI"""
        # Container with padding
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)
        
        # Header
        self._build_header(container)
        
        # Main content - 3 column layout
        content = ttk.Frame(container)
        content.pack(fill=tk.BOTH, expand=True, pady=(24, 0))
        
        # Left: Project List (300px)
        self._build_project_list(content)
        
        # Center: Editor (flex)
        self._build_editor(content)
        
        # Right: Preview (400px)
        self._build_preview(content)
        
    def _build_header(self, parent):
        """Build header section"""
        header = ttk.Frame(parent)
        header.pack(fill=tk.X)
        
        # Left - Title & Status
        left = ttk.Frame(header)
        left.pack(side=tk.LEFT)
        
        ttk.Label(left, text="Project Manager", style="Title.TLabel").pack(anchor=tk.W)
        self.status_label = ttk.Label(left, text="No file loaded • 0 projects", style="Subtitle.TLabel")
        self.status_label.pack(anchor=tk.W, pady=(4, 0))
        
        # Right - Actions
        right = ttk.Frame(header)
        right.pack(side=tk.RIGHT)
        
        ttk.Button(right, text="Open", command=self._open_file).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(right, text="Export README.md", style="Primary.TButton",
                  command=self._export_file).pack(side=tk.LEFT)
                  
    def _build_project_list(self, parent):
        """Build project list panel"""
        panel = tk.Frame(parent, bg=Theme.BG_CARD, width=320)
        panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 16))
        panel.pack_propagate(False)
        
        # Inner padding
        inner = tk.Frame(panel, bg=Theme.BG_CARD)
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        
        # Header
        header = tk.Frame(inner, bg=Theme.BG_CARD)
        header.pack(fill=tk.X, pady=(0, 12))
        
        tk.Label(header, text="Projects", font=(Theme.FONT, 14, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(side=tk.LEFT)
        
        self.count_label = tk.Label(header, text="0", font=(Theme.FONT, 10),
                                    bg=Theme.BG_INPUT, fg=Theme.FG_MUTED,
                                    padx=8, pady=2)
        self.count_label.pack(side=tk.RIGHT)
        
        # Listbox
        list_frame = tk.Frame(inner, bg=Theme.BG_INPUT)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.project_listbox = tk.Listbox(
            list_frame,
            bg=Theme.BG_INPUT,
            fg=Theme.FG,
            selectbackground=Theme.BG_HOVER,
            selectforeground=Theme.FG,
            highlightthickness=0,
            borderwidth=0,
            font=(Theme.FONT, 11),
            activestyle='none'
        )
        self.project_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.project_listbox.bind("<<ListboxSelect>>", self._on_select)
        
        # Buttons
        btn_frame = tk.Frame(inner, bg=Theme.BG_CARD)
        btn_frame.pack(fill=tk.X, pady=(12, 0))
        
        ttk.Button(btn_frame, text="+ Add Project", command=self._add_project).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(btn_frame, text="Delete", style="Danger.TButton",
                  command=self._delete_project).pack(fill=tk.X, pady=(0, 6))
        
        # Move buttons row
        move_frame = tk.Frame(btn_frame, bg=Theme.BG_CARD)
        move_frame.pack(fill=tk.X)
        
        ttk.Button(move_frame, text="↑", style="Small.TButton", width=6,
                  command=self._move_up).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        ttk.Button(move_frame, text="↓", style="Small.TButton", width=6,
                  command=self._move_down).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))
                  
    def _build_editor(self, parent):
        """Build editor panel"""
        panel = tk.Frame(parent, bg=Theme.BG)
        panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 16))
        
        # Notebook
        self.notebook = ttk.Notebook(panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tabs
        self._build_basic_tab()
        self._build_tech_tab()
        self._build_links_tab()
        self._build_screenshots_tab()
        self._build_styling_tab()
        
    def _build_basic_tab(self):
        """Basic info tab"""
        tab = tk.Frame(self.notebook, bg=Theme.BG_CARD)
        self.notebook.add(tab, text="  Basic Info  ")
        
        # Scrollable content
        canvas = tk.Canvas(tab, bg=Theme.BG_CARD, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        content = tk.Frame(canvas, bg=Theme.BG_CARD)
        
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw", width=600)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=24, pady=24)
        
        # ID
        self._create_field(content, "Project ID", "id_entry",
                          "Unique identifier (e.g., my-app)")
        
        # Title
        self._create_field(content, "Title", "title_entry", "Project display name")
        
        # Categories (Multiple selection with checkboxes)
        cat_frame = tk.Frame(content, bg=Theme.BG_CARD)
        cat_frame.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(cat_frame, text="Categories", font=(Theme.FONT, 10, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        tk.Label(cat_frame, text="Select one or more categories", font=(Theme.FONT, 9),
                bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(2, 8))
        
        categories = ["Mobile App", "Website", "IoT", "Game", "AI/ML", "3D/AR/VR", "Other"]
        self.category_vars = {}
        
        cat_grid = tk.Frame(cat_frame, bg=Theme.BG_CARD)
        cat_grid.pack(fill=tk.X)
        
        for i, cat in enumerate(categories):
            var = tk.BooleanVar(value=False)
            self.category_vars[cat] = var
            
            cb = tk.Checkbutton(cat_grid, text=cat, variable=var,
                               bg=Theme.BG_CARD, fg=Theme.FG,
                               selectcolor=Theme.BG_INPUT,
                               activebackground=Theme.BG_CARD,
                               activeforeground=Theme.FG,
                               font=(Theme.FONT, 10),
                               command=self._on_change_simple)
            cb.grid(row=i//3, column=i%3, sticky=tk.W, padx=(0, 20), pady=2)
        
        # Short description
        self._create_field(content, "Short Description", "short_desc_entry",
                          "One-line summary")
        
        # Long description
        tk.Label(content, text="Full Description", font=(Theme.FONT, 10, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        tk.Label(content, text="Detailed project description", font=(Theme.FONT, 9),
                bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(2, 6))
        
        self.long_desc_text = tk.Text(content, bg=Theme.BG_INPUT, fg=Theme.FG,
                                      insertbackground=Theme.FG,
                                      font=(Theme.FONT, 10),
                                      relief=tk.FLAT, padx=12, pady=12,
                                      height=8, wrap=tk.WORD)
        self.long_desc_text.pack(fill=tk.X)
        self.long_desc_text.bind("<KeyRelease>", self._on_change)
        
    def _build_tech_tab(self):
        """Tech stack and features tab"""
        tab = tk.Frame(self.notebook, bg=Theme.BG_CARD)
        self.notebook.add(tab, text="  Tech & Features  ")
        
        content = tk.Frame(tab, bg=Theme.BG_CARD)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)
        
        # Two columns
        left = tk.Frame(content, bg=Theme.BG_CARD)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
        
        right = tk.Frame(content, bg=Theme.BG_CARD)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        
        # Technologies
        self._create_list_editor(left, "Technologies", "tech",
                                ["Flutter", "React", "Vue", "Angular", "Node.js", 
                                 "Python", "TypeScript", "Firebase", "MongoDB",
                                 "PostgreSQL", "Docker", "AWS", "TensorFlow"])
        
        # Features
        self._create_list_editor(right, "Features", "features")
        
    def _build_links_tab(self):
        """Links tab"""
        tab = tk.Frame(self.notebook, bg=Theme.BG_CARD)
        self.notebook.add(tab, text="  Links  ")
        
        content = tk.Frame(tab, bg=Theme.BG_CARD)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)
        
        tk.Label(content, text="Project Links", font=(Theme.FONT, 14, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        tk.Label(content, text="Leave empty if not applicable", font=(Theme.FONT, 9),
                bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(2, 16))
        
        links_data = [
            ("Play Store", "link_playstore", "play.google.com/store/apps/..."),
            ("App Store", "link_appstore", "apps.apple.com/app/..."),
            ("Website", "link_website", "https://example.com"),
            ("GitHub", "link_github", "github.com/user/repo"),
            ("APK Download", "link_apk", "Direct APK download link"),
        ]
        
        for label, attr, hint in links_data:
            self._create_field(content, label, attr, hint)
            
    def _build_screenshots_tab(self):
        """Screenshots and images tab"""
        tab = tk.Frame(self.notebook, bg=Theme.BG_CARD)
        self.notebook.add(tab, text="  Images  ")
        
        content = tk.Frame(tab, bg=Theme.BG_CARD)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)
        
        # Banner Image Section
        banner_section = tk.Frame(content, bg=Theme.BG_CARD)
        banner_section.pack(fill=tk.X, pady=(0, 24))
        
        tk.Label(banner_section, text="Banner Image", font=(Theme.FONT, 14, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        tk.Label(banner_section, text="Select a banner image or enter URL",
                font=(Theme.FONT, 9), bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(2, 8))
        
        banner_input = tk.Frame(banner_section, bg=Theme.BG_CARD)
        banner_input.pack(fill=tk.X)
        
        self.banner_entry = tk.Entry(banner_input, bg=Theme.BG_INPUT, fg=Theme.FG,
                                     insertbackground=Theme.FG, font=(Theme.FONT, 10),
                                     relief=tk.FLAT, bd=0)
        self.banner_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=10, ipadx=10)
        self.banner_entry.bind("<KeyRelease>", self._on_change)
        
        ttk.Button(banner_input, text="Browse...", style="Small.TButton",
                  command=self._browse_banner).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(banner_input, text="Clear", style="Small.TButton",
                  command=self._clear_banner).pack(side=tk.LEFT, padx=(4, 0))
        
        # Banner preview label
        self.banner_preview_label = tk.Label(banner_section, text="No banner selected",
                                             font=(Theme.FONT, 9), bg=Theme.BG_CARD, fg=Theme.FG_MUTED)
        self.banner_preview_label.pack(anchor=tk.W, pady=(8, 0))
        
        # Divider
        tk.Frame(content, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=16)
        
        # Screenshots Section
        ss_section = tk.Frame(content, bg=Theme.BG_CARD)
        ss_section.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(ss_section, text="Screenshots", font=(Theme.FONT, 14, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        tk.Label(ss_section, text="Add multiple screenshot images",
                font=(Theme.FONT, 9), bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(2, 8))
        
        # Buttons row
        btn_row = tk.Frame(ss_section, bg=Theme.BG_CARD)
        btn_row.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Button(btn_row, text="+ Add Screenshots", 
                  command=self._add_screenshots).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="Remove Selected", style="Small.TButton",
                  command=self._remove_screenshot).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="Clear All", style="Small.TButton",
                  command=self._clear_screenshots).pack(side=tk.LEFT)
        
        # Screenshots list
        list_frame = tk.Frame(ss_section, bg=Theme.BG_INPUT)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.screenshots_listbox = tk.Listbox(list_frame, bg=Theme.BG_INPUT, fg=Theme.FG,
                                              selectbackground=Theme.BG_HOVER,
                                              highlightthickness=0, borderwidth=0,
                                              font=(Theme.FONT, 10), activestyle='none')
        self.screenshots_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # Screenshot count label
        self.ss_count_label = tk.Label(ss_section, text="0 screenshots",
                                       font=(Theme.FONT, 9), bg=Theme.BG_CARD, fg=Theme.FG_MUTED)
        self.ss_count_label.pack(anchor=tk.W, pady=(8, 0))
        
    def _browse_banner(self):
        """Browse for banner image"""
        path = filedialog.askopenfilename(
            title="Select Banner Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.gif"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )
        if path:
            self.banner_entry.delete(0, tk.END)
            self.banner_entry.insert(0, path)
            filename = os.path.basename(path)
            self.banner_preview_label.config(text=f"Selected: {filename}")
            self._on_change(None)
            
    def _clear_banner(self):
        """Clear banner image"""
        self.banner_entry.delete(0, tk.END)
        self.banner_preview_label.config(text="No banner selected")
        self._on_change(None)
        
    def _add_screenshots(self):
        """Add screenshot images"""
        paths = filedialog.askopenfilenames(
            title="Select Screenshots",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.gif"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )
        if paths:
            for path in paths:
                filename = os.path.basename(path)
                self.screenshots_listbox.insert(tk.END, f"{filename}  ({path})")
            self._update_screenshot_count()
            self._on_change(None)
            
    def _remove_screenshot(self):
        """Remove selected screenshot"""
        sel = self.screenshots_listbox.curselection()
        if sel:
            self.screenshots_listbox.delete(sel[0])
            self._update_screenshot_count()
            self._on_change(None)
            
    def _clear_screenshots(self):
        """Clear all screenshots"""
        self.screenshots_listbox.delete(0, tk.END)
        self._update_screenshot_count()
        self._on_change(None)
        
    def _update_screenshot_count(self):
        """Update screenshot count label"""
        count = self.screenshots_listbox.size()
        self.ss_count_label.config(text=f"{count} screenshot{'s' if count != 1 else ''}")
    
    def _on_change_simple(self):
        """Handle change without event parameter"""
        self.has_changes = True
        self._update_status()
        self._update_preview_live()
        
    def _build_styling_tab(self):
        """Styling options tab"""
        tab = tk.Frame(self.notebook, bg=Theme.BG_CARD)
        self.notebook.add(tab, text="  Styling  ")
        
        # Scrollable content
        canvas = tk.Canvas(tab, bg=Theme.BG_CARD, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        content = tk.Frame(canvas, bg=Theme.BG_CARD)
        
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw", width=600)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=24, pady=24)
        
        # Header
        tk.Label(content, text="Project Styling", font=(Theme.FONT, 14, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        tk.Label(content, text="Customize the appearance of your project in the README",
                font=(Theme.FONT, 9), bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(2, 16))
        
        # Logo Section
        logo_section = tk.Frame(content, bg=Theme.BG_CARD)
        logo_section.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(logo_section, text="Logo", font=(Theme.FONT, 12, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        
        # Show logo checkbox
        self.show_logo_var = tk.BooleanVar(value=True)
        tk.Checkbutton(logo_section, text="Show project logo", variable=self.show_logo_var,
                      bg=Theme.BG_CARD, fg=Theme.FG, selectcolor=Theme.BG_INPUT,
                      activebackground=Theme.BG_CARD, activeforeground=Theme.FG,
                      font=(Theme.FONT, 10), command=self._on_change_simple).pack(anchor=tk.W, pady=(8, 4))
        
        # Logo URL
        logo_url_frame = tk.Frame(logo_section, bg=Theme.BG_CARD)
        logo_url_frame.pack(fill=tk.X, pady=(4, 8))
        
        tk.Label(logo_url_frame, text="Logo URL (optional):", font=(Theme.FONT, 9),
                bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W)
        
        logo_input = tk.Frame(logo_url_frame, bg=Theme.BG_CARD)
        logo_input.pack(fill=tk.X, pady=(4, 0))
        
        self.logo_url_entry = tk.Entry(logo_input, bg=Theme.BG_INPUT, fg=Theme.FG,
                                       insertbackground=Theme.FG, font=(Theme.FONT, 10),
                                       relief=tk.FLAT, bd=0)
        self.logo_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, ipadx=8)
        self.logo_url_entry.bind("<KeyRelease>", self._on_change)
        
        ttk.Button(logo_input, text="Browse...", style="Small.TButton",
                  command=self._browse_logo).pack(side=tk.LEFT, padx=(8, 0))
        
        # Logo position
        tk.Label(logo_section, text="Logo Position:", font=(Theme.FONT, 9),
                bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(8, 4))
        
        self.logo_position_var = tk.StringVar(value="center")
        pos_frame = tk.Frame(logo_section, bg=Theme.BG_CARD)
        pos_frame.pack(anchor=tk.W)
        
        for pos in [("Left", "left"), ("Center", "center"), ("Right", "right")]:
            tk.Radiobutton(pos_frame, text=pos[0], value=pos[1], variable=self.logo_position_var,
                          bg=Theme.BG_CARD, fg=Theme.FG, selectcolor=Theme.BG_INPUT,
                          activebackground=Theme.BG_CARD, activeforeground=Theme.FG,
                          font=(Theme.FONT, 10), command=self._on_change_simple).pack(side=tk.LEFT, padx=(0, 16))
        
        # Divider
        tk.Frame(content, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=16)
        
        # Border Section
        border_section = tk.Frame(content, bg=Theme.BG_CARD)
        border_section.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(border_section, text="Border Style", font=(Theme.FONT, 12, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        
        self.show_border_var = tk.BooleanVar(value=False)
        tk.Checkbutton(border_section, text="Add border around project section", variable=self.show_border_var,
                      bg=Theme.BG_CARD, fg=Theme.FG, selectcolor=Theme.BG_INPUT,
                      activebackground=Theme.BG_CARD, activeforeground=Theme.FG,
                      font=(Theme.FONT, 10), command=self._on_change_simple).pack(anchor=tk.W, pady=(8, 4))
        
        tk.Label(border_section, text="Border Style:", font=(Theme.FONT, 9),
                bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(8, 4))
        
        self.border_style_var = tk.StringVar(value="rounded")
        border_frame = tk.Frame(border_section, bg=Theme.BG_CARD)
        border_frame.pack(anchor=tk.W)
        
        for style in [("Rounded", "rounded"), ("Square", "square"), ("Dashed", "dashed")]:
            tk.Radiobutton(border_frame, text=style[0], value=style[1], variable=self.border_style_var,
                          bg=Theme.BG_CARD, fg=Theme.FG, selectcolor=Theme.BG_INPUT,
                          activebackground=Theme.BG_CARD, activeforeground=Theme.FG,
                          font=(Theme.FONT, 10), command=self._on_change_simple).pack(side=tk.LEFT, padx=(0, 16))
        
        # Divider
        tk.Frame(content, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=16)
        
        # Screenshot Layout Section
        ss_section = tk.Frame(content, bg=Theme.BG_CARD)
        ss_section.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(ss_section, text="Screenshot Layout", font=(Theme.FONT, 12, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        
        tk.Label(ss_section, text="Layout Style:", font=(Theme.FONT, 9),
                bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(8, 4))
        
        self.screenshot_layout_var = tk.StringVar(value="horizontal")
        layout_frame = tk.Frame(ss_section, bg=Theme.BG_CARD)
        layout_frame.pack(anchor=tk.W)
        
        for layout in [("Horizontal Row", "horizontal"), ("Grid (2 cols)", "grid"), ("Vertical Stack", "vertical")]:
            tk.Radiobutton(layout_frame, text=layout[0], value=layout[1], variable=self.screenshot_layout_var,
                          bg=Theme.BG_CARD, fg=Theme.FG, selectcolor=Theme.BG_INPUT,
                          activebackground=Theme.BG_CARD, activeforeground=Theme.FG,
                          font=(Theme.FONT, 10), command=self._on_change_simple).pack(side=tk.LEFT, padx=(0, 16))
        
        # Screenshot size
        size_frame = tk.Frame(ss_section, bg=Theme.BG_CARD)
        size_frame.pack(fill=tk.X, pady=(12, 0))
        
        tk.Label(size_frame, text="Screenshot Width (px):", font=(Theme.FONT, 9),
                bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(side=tk.LEFT)
        
        self.screenshot_size_var = tk.StringVar(value="200")
        size_entry = tk.Entry(size_frame, textvariable=self.screenshot_size_var,
                             bg=Theme.BG_INPUT, fg=Theme.FG, insertbackground=Theme.FG,
                             font=(Theme.FONT, 10), relief=tk.FLAT, bd=0, width=8)
        size_entry.pack(side=tk.LEFT, padx=(8, 0), ipady=6, ipadx=6)
        size_entry.bind("<KeyRelease>", self._on_change)
        
        # Divider
        tk.Frame(content, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=16)
        
        # Theme Color Section
        theme_section = tk.Frame(content, bg=Theme.BG_CARD)
        theme_section.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(theme_section, text="Theme Color", font=(Theme.FONT, 12, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        tk.Label(theme_section, text="Accent color for custom badges (hex format)",
                font=(Theme.FONT, 9), bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(2, 8))
        
        color_frame = tk.Frame(theme_section, bg=Theme.BG_CARD)
        color_frame.pack(fill=tk.X)
        
        self.theme_color_entry = tk.Entry(color_frame, bg=Theme.BG_INPUT, fg=Theme.FG,
                                         insertbackground=Theme.FG, font=(Theme.FONT, 10),
                                         relief=tk.FLAT, bd=0, width=10)
        self.theme_color_entry.insert(0, "#000000")
        self.theme_color_entry.pack(side=tk.LEFT, ipady=8, ipadx=8)
        self.theme_color_entry.bind("<KeyRelease>", self._on_change)
        
        # Color preview
        self.color_preview = tk.Label(color_frame, text="  ", bg="#000000", width=4)
        self.color_preview.pack(side=tk.LEFT, padx=(8, 0), ipady=8)
        
        # Preset colors
        presets_frame = tk.Frame(theme_section, bg=Theme.BG_CARD)
        presets_frame.pack(anchor=tk.W, pady=(8, 0))
        
        preset_colors = [("Black", "#000000"), ("Blue", "#3b82f6"), ("Green", "#22c55e"), 
                        ("Purple", "#8b5cf6"), ("Red", "#ef4444"), ("Orange", "#f97316")]
        
        for name, color in preset_colors:
            btn = tk.Button(presets_frame, text="", bg=color, width=3, height=1,
                           relief=tk.FLAT, bd=0,
                           command=lambda c=color: self._set_theme_color(c))
            btn.pack(side=tk.LEFT, padx=(0, 6))
            
    def _browse_logo(self):
        """Browse for logo image"""
        path = filedialog.askopenfilename(
            title="Select Logo Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.svg *.webp *.gif"),
                ("PNG", "*.png"),
                ("SVG", "*.svg"),
                ("All files", "*.*")
            ]
        )
        if path:
            self.logo_url_entry.delete(0, tk.END)
            self.logo_url_entry.insert(0, path)
            self._on_change(None)
            
    def _set_theme_color(self, color: str):
        """Set theme color from preset"""
        self.theme_color_entry.delete(0, tk.END)
        self.theme_color_entry.insert(0, color)
        try:
            self.color_preview.config(bg=color)
        except:
            pass
        self._on_change(None)
                          
    def _build_preview(self, parent):
        """Build preview panel with rendered HTML view"""
        panel = tk.Frame(parent, bg=Theme.BG_CARD, width=480)
        panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        panel.pack_propagate(False)
        
        inner = tk.Frame(panel, bg=Theme.BG_CARD)
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        
        # Header with toggle buttons
        header = tk.Frame(inner, bg=Theme.BG_CARD)
        header.pack(fill=tk.X, pady=(0, 12))
        
        tk.Label(header, text="Preview", font=(Theme.FONT, 14, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(side=tk.LEFT)
        
        # Toggle buttons
        btn_frame = tk.Frame(header, bg=Theme.BG_CARD)
        btn_frame.pack(side=tk.RIGHT)
        
        self.preview_mode = tk.StringVar(value="rendered")
        
        ttk.Button(btn_frame, text="Open in Browser", style="Small.TButton",
                  command=self._open_preview_in_browser).pack(side=tk.LEFT, padx=(0, 8))
        
        tk.Radiobutton(btn_frame, text="Rendered", value="rendered", 
                      variable=self.preview_mode, command=self._toggle_preview_mode,
                      bg=Theme.BG_CARD, fg=Theme.FG, selectcolor=Theme.BG_INPUT,
                      activebackground=Theme.BG_CARD, activeforeground=Theme.FG,
                      font=(Theme.FONT, 9)).pack(side=tk.LEFT)
        
        tk.Radiobutton(btn_frame, text="Code", value="code", 
                      variable=self.preview_mode, command=self._toggle_preview_mode,
                      bg=Theme.BG_CARD, fg=Theme.FG, selectcolor=Theme.BG_INPUT,
                      activebackground=Theme.BG_CARD, activeforeground=Theme.FG,
                      font=(Theme.FONT, 9)).pack(side=tk.LEFT)
        
        # Preview container
        self.preview_container = tk.Frame(inner, bg=Theme.BG_INPUT)
        self.preview_container.pack(fill=tk.BOTH, expand=True)
        
        # Code preview (hidden by default)
        self.preview_text = tk.Text(self.preview_container, bg=Theme.BG_INPUT, fg=Theme.FG_SECONDARY,
                                    insertbackground=Theme.FG,
                                    font=(Theme.FONT_MONO, 9),
                                    relief=tk.FLAT, padx=12, pady=12,
                                    wrap=tk.WORD, state=tk.DISABLED)
        
        # Rendered preview using Text widget with tags for styling
        self.preview_rendered = tk.Text(self.preview_container, bg="#1a1a1a", fg="#e0e0e0",
                                        font=(Theme.FONT, 10),
                                        relief=tk.FLAT, padx=16, pady=16,
                                        wrap=tk.WORD, state=tk.DISABLED,
                                        cursor="arrow")
        self.preview_rendered.pack(fill=tk.BOTH, expand=True)
        
        # Configure text tags for styling
        self.preview_rendered.tag_configure("h1", font=(Theme.FONT, 20, "bold"), foreground="#ffffff", spacing3=10)
        self.preview_rendered.tag_configure("h2", font=(Theme.FONT, 16, "bold"), foreground="#ffffff", spacing1=15, spacing3=8)
        self.preview_rendered.tag_configure("h3", font=(Theme.FONT, 13, "bold"), foreground="#e0e0e0", spacing1=12, spacing3=6)
        self.preview_rendered.tag_configure("bold", font=(Theme.FONT, 10, "bold"), foreground="#ffffff")
        self.preview_rendered.tag_configure("code", font=(Theme.FONT_MONO, 9), background="#333333", foreground="#22c55e")
        self.preview_rendered.tag_configure("badge", font=(Theme.FONT, 9), background="#3b82f6", foreground="#ffffff")
        self.preview_rendered.tag_configure("link", foreground="#60a5fa", underline=True)
        self.preview_rendered.tag_configure("muted", foreground="#888888", font=(Theme.FONT, 9))
        self.preview_rendered.tag_configure("bullet", foreground="#22c55e")
        self.preview_rendered.tag_configure("divider", foreground="#444444")
        self.preview_rendered.tag_configure("center", justify="center")
        
    def _toggle_preview_mode(self):
        """Toggle between rendered and code preview"""
        if self.preview_mode.get() == "rendered":
            self.preview_text.pack_forget()
            self.preview_rendered.pack(fill=tk.BOTH, expand=True)
        else:
            self.preview_rendered.pack_forget()
            self.preview_text.pack(fill=tk.BOTH, expand=True)
        self._update_preview_live()
        
    def _open_preview_in_browser(self):
        """Open rendered preview in web browser"""
        if self.selected_index is None:
            return
        try:
            p = self._get_current_project_data()
            
            # Convert to HTML with actual image paths
            html_content = self._md_to_full_html_with_images(p)
            
            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                temp_path = f.name
            
            webbrowser.open(f'file://{temp_path}')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open preview: {e}")
    
    def _md_to_full_html_with_images(self, p: Project) -> str:
        """Convert project to full HTML with actual image paths"""
        import urllib.parse
        
        # Get base directory for resolving relative paths
        base_dir = os.path.dirname(self.file_path) if self.file_path else os.path.dirname(os.path.abspath(__file__))
        images_dir = os.path.join(base_dir, "images", p.id) if p.id else ""
        
        def to_file_url(path: str) -> str:
            """Convert local path to file:// URL"""
            if not path or not os.path.exists(path):
                return ""
            # Get absolute path and convert to URL format
            abs_path = os.path.abspath(path)
            # Use proper URL encoding for file paths
            return "file:///" + urllib.parse.quote(abs_path.replace("\\", "/"), safe=":/")
        
        def resolve_image_path(path: str) -> str:
            """Try to resolve an image path to an actual file"""
            if not path:
                return ""
            # Already absolute and exists
            if os.path.isabs(path) and os.path.exists(path):
                return path
            # Try relative to file path
            if self.file_path:
                rel_path = os.path.join(os.path.dirname(self.file_path), path)
                if os.path.exists(rel_path):
                    return rel_path
            # Try in images/{project-id}/ folder
            if images_dir:
                # Try direct filename match
                basename = os.path.basename(path)
                img_path = os.path.join(images_dir, basename)
                if os.path.exists(img_path):
                    return img_path
                # Try numeric filename (1.jpg, 2.jpg from screenshot_1.jpg)
                num_match = re.search(r'(\d+)\.\w+$', basename)
                if num_match:
                    num = num_match.group(1)
                    for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
                        img_path = os.path.join(images_dir, f"{num}{ext}")
                        if os.path.exists(img_path):
                            return img_path
            return ""
        
        # Build HTML directly with actual paths
        html_parts = []
        
        # Logo - check if it's a local file
        logo_url = ""
        if p.show_logo and p.logo_url:
            resolved = resolve_image_path(p.logo_url)
            if resolved:
                logo_url = to_file_url(resolved)
            # Also try logo.png in images folder
            elif images_dir:
                for ext in ['.png', '.jpg', '.svg']:
                    logo_path = os.path.join(images_dir, f"logo{ext}")
                    if os.path.exists(logo_path):
                        logo_url = to_file_url(logo_path)
                        break
        if logo_url:
            html_parts.append(f'<div style="text-align:center;"><img src="{logo_url}" alt="logo" style="height:80px;"></div>')
        
        # Title
        html_parts.append(f'<h1 style="text-align:center;">{p.title or "Untitled"}</h1>')
        
        # Categories
        if p.categories:
            badges = ' '.join([f'<span style="background:#3b82f6;color:white;padding:4px 12px;border-radius:12px;margin:2px;display:inline-block;">{cat}</span>' for cat in p.categories])
            html_parts.append(f'<div style="text-align:center;margin:10px 0;">{badges}</div>')
        
        # Banner - check if it's a local file
        banner_url = ""
        if p.banner_image:
            resolved = resolve_image_path(p.banner_image)
            if resolved:
                banner_url = to_file_url(resolved)
            # Also try banner.jpg in images folder
            elif images_dir:
                for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    banner_path = os.path.join(images_dir, f"banner{ext}")
                    if os.path.exists(banner_path):
                        banner_url = to_file_url(banner_path)
                        break
        if banner_url:
            html_parts.append(f'<div style="text-align:center;"><img src="{banner_url}" alt="banner" style="max-width:100%;border-radius:12px;"></div>')
        
        # Description
        if p.short_description:
            html_parts.append(f'<p style="text-align:center;"><strong>{p.short_description}</strong></p>')
        if p.long_description:
            html_parts.append(f'<p style="text-align:center;">{p.long_description}</p>')
        
        # Links as badges
        links = p.links or {}
        link_badges = []
        if links.get("playStore"):
            link_badges.append(f'<a href="{links["playStore"]}"><img src="https://img.shields.io/badge/Play_Store-414141?style=for-the-badge&logo=google-play&logoColor=white"></a>')
        if links.get("appStore"):
            link_badges.append(f'<a href="{links["appStore"]}"><img src="https://img.shields.io/badge/App_Store-0D96F6?style=for-the-badge&logo=app-store&logoColor=white"></a>')
        if links.get("website"):
            link_badges.append(f'<a href="{links["website"]}"><img src="https://img.shields.io/badge/Website-000000?style=for-the-badge&logo=safari&logoColor=white"></a>')
        if links.get("github"):
            link_badges.append(f'<a href="{links["github"]}"><img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white"></a>')
        if links.get("apk"):
            link_badges.append(f'<a href="{links["apk"]}"><img src="https://img.shields.io/badge/APK-3DDC84?style=for-the-badge&logo=android&logoColor=white"></a>')
        if link_badges:
            html_parts.append(f'<div style="text-align:center;margin:20px 0;">{" ".join(link_badges)}</div>')
        
        # Tech Stack
        if p.technologies:
            html_parts.append('<h3 style="text-align:center;">Tech Stack</h3>')
            tech_badges = ' '.join([f'<code style="background:#1e1e1e;color:#22c55e;padding:4px 8px;border-radius:4px;margin:2px;">{t}</code>' for t in p.technologies])
            html_parts.append(f'<div style="text-align:center;">{tech_badges}</div>')
        
        # Features
        if p.features:
            html_parts.append('<h3 style="text-align:center;">Features</h3>')
            html_parts.append('<ul style="max-width:600px;margin:0 auto;">')
            for f in p.features:
                html_parts.append(f'<li>{f}</li>')
            html_parts.append('</ul>')
        
        # Screenshots - use actual paths with resolution
        if p.screenshots:
            html_parts.append('<h3 style="text-align:center;">Screenshots</h3>')
            html_parts.append('<div style="text-align:center;display:flex;flex-wrap:wrap;justify-content:center;gap:10px;">')
            for i, ss in enumerate(p.screenshots):
                # Get local path
                local_path = p.screenshots_local_paths[i] if i < len(p.screenshots_local_paths) else ss
                # Try to resolve the path
                resolved = resolve_image_path(local_path)
                if not resolved:
                    # Try with index number (1.jpg, 2.jpg, etc.)
                    if images_dir:
                        for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
                            img_path = os.path.join(images_dir, f"{i+1}{ext}")
                            if os.path.exists(img_path):
                                resolved = img_path
                                break
                
                if resolved:
                    file_url = to_file_url(resolved)
                    html_parts.append(f'<img src="{file_url}" style="width:{p.screenshot_size}px;border-radius:8px;margin:5px;">')
                else:
                    html_parts.append(f'<div style="width:{p.screenshot_size}px;height:300px;background:#333;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#666;">Image: {os.path.basename(local_path)}</div>')
            html_parts.append('</div>')
        
        body = '\n'.join(html_parts)
        
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{p.title or "Preview"}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d0d0d;
            color: #e0e0e0;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            line-height: 1.6;
        }}
        h1, h2, h3 {{ color: #ffffff; margin-top: 30px; }}
        a {{ color: #60a5fa; text-decoration: none; }}
        img {{ max-width: 100%; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 8px 0; }}
    </style>
</head>
<body>
{body}
</body>
</html>'''
            
    def _md_to_full_html(self, md: str) -> str:
        """Convert markdown to full HTML page with styling"""
        # Use markdown library if available
        if HAS_MARKDOWN:
            body = markdown.markdown(md, extensions=['tables', 'fenced_code'])
        else:
            body = md_to_html(md)
        
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Preview</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d0d0d;
            color: #e0e0e0;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            line-height: 1.6;
        }}
        h1, h2, h3 {{ color: #ffffff; }}
        h1 {{ font-size: 2em; border-bottom: 1px solid #333; padding-bottom: 10px; }}
        h2 {{ font-size: 1.5em; margin-top: 30px; }}
        h3 {{ font-size: 1.2em; margin-top: 20px; color: #ccc; }}
        a {{ color: #60a5fa; }}
        code {{
            background: #1e1e1e;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Cascadia Code', monospace;
            color: #22c55e;
        }}
        img {{ max-width: 100%; border-radius: 8px; margin: 10px 0; }}
        p {{ margin: 10px 0; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 5px 0; }}
        hr {{ border: none; border-top: 1px solid #333; margin: 30px 0; }}
        .badge {{
            display: inline-block;
            background: #3b82f6;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            margin: 2px;
        }}
        div[align="center"] {{ text-align: center; }}
        table {{ border-collapse: collapse; margin: 20px 0; }}
        td {{ padding: 8px; }}
    </style>
</head>
<body>
{body}
</body>
</html>'''
    
    def _render_preview(self, md: str):
        """Render markdown in the preview text widget with formatting"""
        self.preview_rendered.config(state=tk.NORMAL)
        self.preview_rendered.delete("1.0", tk.END)
        
        lines = md.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Skip HTML tags but process content
            if stripped.startswith('<div') or stripped.startswith('</div') or stripped == '':
                if stripped == '':
                    self.preview_rendered.insert(tk.END, '\n')
                i += 1
                continue
            
            # Headers
            if stripped.startswith('## '):
                text = stripped[3:]
                self.preview_rendered.insert(tk.END, text + '\n', "h2")
            elif stripped.startswith('### '):
                text = stripped[4:]
                self.preview_rendered.insert(tk.END, text + '\n', "h3")
            elif stripped.startswith('# '):
                text = stripped[2:]
                self.preview_rendered.insert(tk.END, text + '\n', "h1")
            
            # Badges in backticks
            elif stripped.startswith('`') and stripped.endswith('`'):
                badges = re.findall(r'`([^`]+)`', stripped)
                for badge in badges:
                    self.preview_rendered.insert(tk.END, f" {badge} ", "badge")
                    self.preview_rendered.insert(tk.END, "  ")
                self.preview_rendered.insert(tk.END, '\n')
            
            # Bold text
            elif stripped.startswith('**') and stripped.endswith('**'):
                text = stripped[2:-2]
                self.preview_rendered.insert(tk.END, text + '\n', "bold")
            
            # List items
            elif stripped.startswith('- '):
                self.preview_rendered.insert(tk.END, "  • ", "bullet")
                self.preview_rendered.insert(tk.END, stripped[2:] + '\n')
            
            # Code tags
            elif '<code>' in stripped:
                codes = re.findall(r'<code>([^<]+)</code>', stripped)
                for j, code in enumerate(codes):
                    self.preview_rendered.insert(tk.END, f" {code} ", "code")
                    if j < len(codes) - 1:
                        self.preview_rendered.insert(tk.END, "  ")
                self.preview_rendered.insert(tk.END, '\n')
            
            # Image references
            elif '<img' in stripped:
                src_match = re.search(r'src="([^"]+)"', stripped)
                if src_match:
                    src = src_match.group(1)
                    # Check if it's a badge/shield
                    if 'shields.io' in src or 'badge' in src.lower():
                        badge_match = re.search(r'/badge/([^?]+)', src)
                        if badge_match:
                            badge_text = badge_match.group(1).replace('_', ' ').replace('-', ' ').split('?')[0]
                            self.preview_rendered.insert(tk.END, f" [{badge_text}] ", "link")
                    else:
                        filename = os.path.basename(src)
                        self.preview_rendered.insert(tk.END, f"[Image: {filename}]\n", "muted")
            
            # Links
            elif '<a href' in stripped:
                href_match = re.search(r'href="([^"]+)"', stripped)
                if href_match:
                    url = href_match.group(1)
                    # Already handled images above
                    if '<img' not in stripped:
                        self.preview_rendered.insert(tk.END, f"🔗 {url}\n", "link")
            
            # Plain paragraph text
            elif stripped.startswith('<p>') and stripped.endswith('</p>'):
                text = stripped[3:-4]
                self.preview_rendered.insert(tk.END, text + '\n\n')
            elif stripped.startswith('<p>'):
                text = stripped[3:]
                self.preview_rendered.insert(tk.END, text)
            elif stripped.endswith('</p>'):
                text = stripped[:-4]
                self.preview_rendered.insert(tk.END, text + '\n\n')
            
            # Horizontal rule
            elif stripped == '<hr>' or stripped == '---':
                self.preview_rendered.insert(tk.END, "─" * 40 + '\n', "divider")
            
            # Skip other HTML tags
            elif stripped.startswith('<') and stripped.endswith('>'):
                pass
            
            # Regular text
            elif stripped and not stripped.startswith('<'):
                self.preview_rendered.insert(tk.END, stripped + '\n')
            
            i += 1
        
        self.preview_rendered.config(state=tk.DISABLED)
        
    def _create_field(self, parent, label: str, attr: str, hint: str = ""):
        """Create labeled input field"""
        frame = tk.Frame(parent, bg=Theme.BG_CARD)
        frame.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(frame, text=label, font=(Theme.FONT, 10, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        
        if hint:
            tk.Label(frame, text=hint, font=(Theme.FONT, 9),
                    bg=Theme.BG_CARD, fg=Theme.FG_MUTED).pack(anchor=tk.W, pady=(2, 0))
        
        entry = tk.Entry(frame, bg=Theme.BG_INPUT, fg=Theme.FG,
                        insertbackground=Theme.FG,
                        font=(Theme.FONT, 10),
                        relief=tk.FLAT, bd=0)
        entry.pack(fill=tk.X, pady=(6, 0), ipady=10, ipadx=10)
        entry.bind("<KeyRelease>", self._on_change)
        
        setattr(self, attr, entry)
        
    def _create_list_editor(self, parent, title: str, attr: str, suggestions: List[str] = None):
        """Create list editor with add/remove"""
        tk.Label(parent, text=title, font=(Theme.FONT, 12, "bold"),
                bg=Theme.BG_CARD, fg=Theme.FG).pack(anchor=tk.W)
        
        # Input row
        input_frame = tk.Frame(parent, bg=Theme.BG_CARD)
        input_frame.pack(fill=tk.X, pady=(8, 0))
        
        if suggestions:
            var = tk.StringVar()
            entry = ttk.Combobox(input_frame, textvariable=var, values=suggestions,
                                font=(Theme.FONT, 10))
            setattr(self, f"{attr}_var", var)
        else:
            entry = tk.Entry(input_frame, bg=Theme.BG_INPUT, fg=Theme.FG,
                           insertbackground=Theme.FG, font=(Theme.FONT, 10),
                           relief=tk.FLAT, bd=0)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, ipadx=8)
        setattr(self, f"{attr}_entry", entry)
        
        ttk.Button(input_frame, text="+", style="Small.TButton", width=3,
                  command=lambda: self._add_list_item(attr)).pack(side=tk.LEFT, padx=(8, 0))
        
        # List display
        list_frame = tk.Frame(parent, bg=Theme.BG_INPUT)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        
        listbox = tk.Listbox(list_frame, bg=Theme.BG_INPUT, fg=Theme.FG,
                            selectbackground=Theme.BG_HOVER,
                            highlightthickness=0, borderwidth=0,
                            font=(Theme.FONT, 10), activestyle='none')
        listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        setattr(self, f"{attr}_listbox", listbox)
        
        ttk.Button(parent, text="Remove", style="Small.TButton",
                  command=lambda: self._remove_list_item(attr)).pack(anchor=tk.W, pady=(8, 0))
                  
    def _add_list_item(self, attr: str):
        """Add item to list"""
        if hasattr(self, f"{attr}_var"):
            value = getattr(self, f"{attr}_var").get().strip()
            getattr(self, f"{attr}_var").set("")
        else:
            entry = getattr(self, f"{attr}_entry")
            value = entry.get().strip()
            entry.delete(0, tk.END)
        
        if value:
            getattr(self, f"{attr}_listbox").insert(tk.END, value)
            self._on_change(None)
            
    def _remove_list_item(self, attr: str):
        """Remove selected item"""
        listbox = getattr(self, f"{attr}_listbox")
        sel = listbox.curselection()
        if sel:
            listbox.delete(sel[0])
            self._on_change(None)
            
    # Data operations
    def _refresh_list(self):
        """Refresh project listbox"""
        self.project_listbox.delete(0, tk.END)
        for i, p in enumerate(self.projects):
            title = p.title or f"Untitled {i+1}"
            self.project_listbox.insert(tk.END, f"  {title}")
        self.count_label.config(text=str(len(self.projects)))
        self._update_status()
        
    def _on_select(self, event):
        """Handle project selection"""
        sel = self.project_listbox.curselection()
        if not sel:
            return
        
        self._save_current()
        self.selected_index = sel[0]
        self._load_project(self.projects[self.selected_index])
        self._update_preview()
        
    def _load_project(self, p: Project):
        """Load project into editor"""
        self.id_entry.delete(0, tk.END)
        self.id_entry.insert(0, p.id)
        
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, p.title)
        
        # Categories (multiple checkboxes)
        for cat, var in self.category_vars.items():
            var.set(cat in p.categories)
        
        self.short_desc_entry.delete(0, tk.END)
        self.short_desc_entry.insert(0, p.short_description)
        
        self.long_desc_text.delete("1.0", tk.END)
        self.long_desc_text.insert("1.0", p.long_description)
        
        # Tech
        self.tech_listbox.delete(0, tk.END)
        for t in p.technologies:
            self.tech_listbox.insert(tk.END, t)
            
        # Features
        self.features_listbox.delete(0, tk.END)
        for f in p.features:
            self.features_listbox.insert(tk.END, f)
            
        # Links
        links = p.links or {}
        self.link_playstore.delete(0, tk.END)
        self.link_playstore.insert(0, links.get("playStore", ""))
        
        self.link_appstore.delete(0, tk.END)
        self.link_appstore.insert(0, links.get("appStore", ""))
        
        self.link_website.delete(0, tk.END)
        self.link_website.insert(0, links.get("website", ""))
        
        self.link_github.delete(0, tk.END)
        self.link_github.insert(0, links.get("github", ""))
        
        self.link_apk.delete(0, tk.END)
        self.link_apk.insert(0, links.get("apk", ""))
        
        # Banner
        self.banner_entry.delete(0, tk.END)
        self.banner_entry.insert(0, p.banner_image)
        if p.banner_image:
            filename = os.path.basename(p.banner_image) if os.path.exists(p.banner_image) else p.banner_image
            self.banner_preview_label.config(text=f"Selected: {filename}")
        else:
            self.banner_preview_label.config(text="No banner selected")
        
        # Screenshots
        self.screenshots_listbox.delete(0, tk.END)
        for i, ss in enumerate(p.screenshots):
            local = p.screenshots_local_paths[i] if i < len(p.screenshots_local_paths) else ss
            filename = os.path.basename(local)
            self.screenshots_listbox.insert(tk.END, f"{filename}  ({local})")
        self._update_screenshot_count()
        
        # Styling options
        self.show_logo_var.set(p.show_logo)
        self.logo_url_entry.delete(0, tk.END)
        self.logo_url_entry.insert(0, p.logo_url)
        self.logo_position_var.set(p.logo_position or "left")
        self.show_border_var.set(p.show_border)
        self.border_style_var.set(p.border_style or "rounded")
        self.screenshot_layout_var.set(p.screenshot_layout or "horizontal")
        self.screenshot_size_var.set(str(p.screenshot_size or 200))
        self.theme_color_entry.delete(0, tk.END)
        self.theme_color_entry.insert(0, p.theme_color or "#000000")
        try:
            self.color_preview.config(bg=p.theme_color or "#000000")
        except:
            pass
        
    def _save_current(self):
        """Save current editor to project"""
        if self.selected_index is None or self.selected_index >= len(self.projects):
            return
            
        p = self.projects[self.selected_index]
        
        p.id = self.id_entry.get().strip()
        p.title = self.title_entry.get().strip()
        
        # Categories (multiple)
        p.categories = [cat for cat, var in self.category_vars.items() if var.get()]
        
        p.short_description = self.short_desc_entry.get().strip()
        p.long_description = self.long_desc_text.get("1.0", tk.END).strip()
        
        p.technologies = list(self.tech_listbox.get(0, tk.END))
        p.features = list(self.features_listbox.get(0, tk.END))
        
        p.links = {
            "playStore": self.link_playstore.get().strip(),
            "appStore": self.link_appstore.get().strip(),
            "website": self.link_website.get().strip(),
            "github": self.link_github.get().strip(),
            "apk": self.link_apk.get().strip(),
        }
        
        # Banner
        p.banner_image = self.banner_entry.get().strip()
        if os.path.exists(p.banner_image):
            p.banner_local_path = p.banner_image
        
        # Screenshots - parse from listbox
        p.screenshots = []
        p.screenshots_local_paths = []
        for i in range(self.screenshots_listbox.size()):
            item = self.screenshots_listbox.get(i)
            # Extract path from "filename  (full/path)"
            if "(" in item and ")" in item:
                path = item.split("(")[-1].rstrip(")")
            else:
                path = item
            p.screenshots_local_paths.append(path)
            p.screenshots.append(path)
        
        # Styling options
        p.show_logo = self.show_logo_var.get()
        p.logo_url = self.logo_url_entry.get().strip()
        p.logo_position = self.logo_position_var.get()
        p.show_border = self.show_border_var.get()
        p.border_style = self.border_style_var.get()
        p.screenshot_layout = self.screenshot_layout_var.get()
        try:
            p.screenshot_size = int(self.screenshot_size_var.get())
        except:
            p.screenshot_size = 200
        p.theme_color = self.theme_color_entry.get().strip()
        
        self._refresh_list()
        if self.selected_index is not None:
            self.project_listbox.selection_set(self.selected_index)
            
    def _add_project(self):
        """Add new project"""
        self._save_current()
        
        p = Project()
        p.title = f"New Project {len(self.projects) + 1}"
        p.id = f"new-project-{len(self.projects) + 1}"
        
        self.projects.append(p)
        self._refresh_list()
        
        self.selected_index = len(self.projects) - 1
        self.project_listbox.selection_clear(0, tk.END)
        self.project_listbox.selection_set(self.selected_index)
        self._load_project(p)
        
        self.has_changes = True
        self._update_status()
        
    def _delete_project(self):
        """Delete selected project"""
        if self.selected_index is None:
            return
            
        title = self.projects[self.selected_index].title or "this project"
        if not messagebox.askyesno("Delete", f"Delete '{title}'?"):
            return
            
        del self.projects[self.selected_index]
        self.selected_index = None
        self._refresh_list()
        
        if self.projects:
            self.selected_index = 0
            self.project_listbox.selection_set(0)
            self._load_project(self.projects[0])
            
        self.has_changes = True
        self._update_status()
        
    def _move_up(self):
        """Move project up"""
        if self.selected_index is None or self.selected_index == 0:
            return
        self._save_current()
        i = self.selected_index
        self.projects[i], self.projects[i-1] = self.projects[i-1], self.projects[i]
        self.selected_index = i - 1
        self._refresh_list()
        self.project_listbox.selection_set(self.selected_index)
        self.has_changes = True
        
    def _move_down(self):
        """Move project down"""
        if self.selected_index is None or self.selected_index >= len(self.projects) - 1:
            return
        self._save_current()
        i = self.selected_index
        self.projects[i], self.projects[i+1] = self.projects[i+1], self.projects[i]
        self.selected_index = i + 1
        self._refresh_list()
        self.project_listbox.selection_set(self.selected_index)
        self.has_changes = True
        
    def _on_change(self, event):
        """Handle field change"""
        self.has_changes = True
        self._update_status()
        # Auto-update preview with current data
        self._update_preview_live()
        
    def _update_status(self):
        """Update status label"""
        name = os.path.basename(self.file_path) if self.file_path else "No file"
        mod = " •" if self.has_changes else ""
        self.status_label.config(text=f"{name}{mod} • {len(self.projects)} projects")
    
    def _get_current_project_data(self) -> Project:
        """Get project data from current UI state without saving"""
        p = Project()
        p.id = self.id_entry.get().strip()
        p.title = self.title_entry.get().strip()
        p.categories = [cat for cat, var in self.category_vars.items() if var.get()]
        p.short_description = self.short_desc_entry.get().strip()
        p.long_description = self.long_desc_text.get("1.0", tk.END).strip()
        p.technologies = list(self.tech_listbox.get(0, tk.END))
        p.features = list(self.features_listbox.get(0, tk.END))
        p.links = {
            "playStore": self.link_playstore.get().strip(),
            "appStore": self.link_appstore.get().strip(),
            "website": self.link_website.get().strip(),
            "github": self.link_github.get().strip(),
            "apk": self.link_apk.get().strip(),
        }
        p.banner_image = self.banner_entry.get().strip()
        # Screenshots - extract paths properly
        p.screenshots = []
        p.screenshots_local_paths = []
        for i in range(self.screenshots_listbox.size()):
            item = self.screenshots_listbox.get(i)
            if "(" in item and ")" in item:
                path = item.split("(")[-1].rstrip(")")
            else:
                path = item
            p.screenshots.append(path)
            p.screenshots_local_paths.append(path)
        # Styling
        p.show_logo = self.show_logo_var.get()
        p.logo_url = self.logo_url_entry.get().strip()
        p.logo_position = self.logo_position_var.get()
        p.show_border = self.show_border_var.get()
        p.border_style = self.border_style_var.get()
        p.screenshot_layout = self.screenshot_layout_var.get()
        try:
            p.screenshot_size = int(self.screenshot_size_var.get())
        except:
            p.screenshot_size = 200
        p.theme_color = self.theme_color_entry.get().strip()
        return p
    
    def _update_preview_live(self):
        """Update preview with current UI data (live typing)"""
        if self.selected_index is None:
            return
        try:
            p = self._get_current_project_data()
            md = self._generate_project_md(p)
            
            # Update code view
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert("1.0", md)
            self.preview_text.config(state=tk.DISABLED)
            
            # Update rendered view
            self._render_preview(md)
        except Exception as e:
            # Show error in preview for debugging
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert("1.0", f"Error: {e}")
            self.preview_text.config(state=tk.DISABLED)
        
    def _update_preview(self):
        """Update preview panel"""
        if self.selected_index is None or self.selected_index >= len(self.projects):
            return
        
        try:
            p = self.projects[self.selected_index]
            md = self._generate_project_md(p)
            
            # Update code view
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert("1.0", md)
            self.preview_text.config(state=tk.DISABLED)
            
            # Update rendered view
            self._render_preview(md)
        except Exception as e:
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert("1.0", f"Preview error: {e}")
            self.preview_text.config(state=tk.DISABLED)
        
    # Markdown generation
    def _generate_project_md(self, p: Project) -> str:
        """Generate markdown for single project"""
        lines = []
        content_lines = []
        
        # Get styling options
        show_logo = p.show_logo
        logo_url = p.logo_url
        logo_position = p.logo_position or "center"  # Default to center
        show_border = p.show_border
        border_style = p.border_style or "rounded"
        screenshot_layout = p.screenshot_layout or "horizontal"
        screenshot_size = p.screenshot_size or 200
        theme_color = (p.theme_color or "#000000").lstrip('#')
        
        # Border styling
        border_css = ""
        if show_border:
            if border_style == "rounded":
                border_css = "border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; margin: 16px 0;"
            elif border_style == "square":
                border_css = "border: 1px solid #e5e7eb; padding: 24px; margin: 16px 0;"
            elif border_style == "dashed":
                border_css = "border: 2px dashed #e5e7eb; border-radius: 8px; padding: 24px; margin: 16px 0;"
        
        # Start centered div
        content_lines.append('<div align="center">')
        content_lines.append('')
        
        # Title with logo
        if show_logo and logo_url:
            # Determine logo path
            if os.path.exists(logo_url):
                ext = os.path.splitext(logo_url)[1]
                logo_path = f"images/{p.id}/logo{ext}"
            else:
                logo_path = logo_url
            content_lines.append(f'<img src="{logo_path}" alt="{p.title} logo" height="64">')
            content_lines.append('')
        
        # Title with anchor
        content_lines.append(f"## {p.title or 'Untitled'}")
        content_lines.append("")
        
        # Category badges (multiple) with theme color
        if p.categories:
            badges = " ".join([f"`{cat}`" for cat in p.categories])
            content_lines.append(badges)
            content_lines.append("")
        
        # Banner
        if p.banner_image:
            # Use filename for path if it's a local file
            if os.path.exists(p.banner_image):
                ext = os.path.splitext(p.banner_image)[1]
                banner_path = f"images/{p.id}/banner{ext}"
            else:
                banner_path = p.banner_image
            content_lines.append(f'<img src="{banner_path}" alt="{p.title}" width="100%">')
            content_lines.append("")
        
        # Description
        if p.short_description:
            content_lines.append(f"**{p.short_description}**")
            content_lines.append("")
            
        if p.long_description:
            content_lines.append(f"<p>{p.long_description}</p>")
            content_lines.append("")
        
        # Links as badges
        badges = []
        links = p.links or {}
        
        if links.get("playStore"):
            badges.append(f'<a href="{links["playStore"]}"><img src="https://img.shields.io/badge/Play_Store-414141?style=for-the-badge&logo=google-play&logoColor=white"></a>')
        if links.get("appStore"):
            badges.append(f'<a href="{links["appStore"]}"><img src="https://img.shields.io/badge/App_Store-0D96F6?style=for-the-badge&logo=app-store&logoColor=white"></a>')
        if links.get("website"):
            badges.append(f'<a href="{links["website"]}"><img src="https://img.shields.io/badge/Website-{theme_color}?style=for-the-badge&logo=safari&logoColor=white"></a>')
        if links.get("github"):
            badges.append(f'<a href="{links["github"]}"><img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white"></a>')
        if links.get("apk"):
            badges.append(f'<a href="{links["apk"]}"><img src="https://img.shields.io/badge/APK-3DDC84?style=for-the-badge&logo=android&logoColor=white"></a>')
            
        if badges:
            content_lines.append("<p>")
            for b in badges:
                content_lines.append(f"  {b}")
            content_lines.append("</p>")
            content_lines.append("")
        
        # Tech stack
        if p.technologies:
            content_lines.append("### Tech Stack")
            content_lines.append("")
            content_lines.append("<p>")
            for tech in p.technologies:
                content_lines.append(f"  <code>{tech}</code>")
            content_lines.append("</p>")
            content_lines.append("")
        
        # Features
        if p.features:
            content_lines.append("### Features")
            content_lines.append("")
            for f in p.features:
                content_lines.append(f"- {f}")
            content_lines.append("")
        
        # Screenshots with layout options
        if p.screenshots:
            content_lines.append("### Screenshots")
            content_lines.append("")
            
            if screenshot_layout == "horizontal":
                # Horizontal row - centered
                content_lines.append("<p>")
                for i, ss in enumerate(p.screenshots, 1):
                    ext = os.path.splitext(ss)[1] or ".png"
                    content_lines.append(f'  <img src="images/{p.id}/{i}{ext}" width="{screenshot_size}">')
                content_lines.append("</p>")
            elif screenshot_layout == "grid":
                # 2-column grid table - centered
                content_lines.append("<table align=\"center\">")
                screenshots_list = list(enumerate(p.screenshots, 1))
                for i in range(0, len(screenshots_list), 2):
                    content_lines.append("  <tr>")
                    for j in range(2):
                        if i + j < len(screenshots_list):
                            idx, ss = screenshots_list[i + j]
                            ext = os.path.splitext(ss)[1] or ".png"
                            content_lines.append(f'    <td align="center"><img src="images/{p.id}/{idx}{ext}" width="{screenshot_size}"></td>')
                        else:
                            content_lines.append("    <td></td>")
                    content_lines.append("  </tr>")
                content_lines.append("</table>")
            elif screenshot_layout == "vertical":
                # Vertical stack - centered
                content_lines.append("<p>")
                for i, ss in enumerate(p.screenshots, 1):
                    ext = os.path.splitext(ss)[1] or ".png"
                    content_lines.append(f'  <img src="images/{p.id}/{i}{ext}" width="{screenshot_size}"><br>')
                content_lines.append("</p>")
            content_lines.append("")
        
        # Close the centered div
        content_lines.append('</div>')
        content_lines.append('')
        
        # Wrap in border div if enabled
        if show_border and border_css:
            lines.append(f'<div style="{border_css}">')
            lines.append("")
            lines.extend(content_lines)
            lines.append("</div>")
        else:
            lines.extend(content_lines)
        
        return "\n".join(lines)
        
    def _generate_full_md(self) -> str:
        """Generate complete README.md"""
        lines = []
        
        # Header with Logo and Title
        lines.append('<div align="center">')
        lines.append('')
        lines.append('<img src="images/icon-dark.png" alt="Hexagone" height="120">')
        lines.append('')
        lines.append('# Hexagone Projects')
        lines.append('')
        lines.append('### About this Repository')
        lines.append('')
        lines.append('This repository contains a collection of projects we have built across industries including e-commerce, fintech, travel, education, healthcare, IoT, and lifestyle.')
        lines.append('')
        lines.append('<p>')
        lines.append('  <a href="https://theHexagone.com"><img src="https://img.shields.io/badge/theHexagone.com-000000?style=for-the-badge&logo=safari&logoColor=white"></a>')
        lines.append('</p>')
        lines.append('')
        lines.append('</div>')
        lines.append('')
        lines.append('---')
        lines.append('')
        
        # Table of contents
        if self.projects:
            lines.append('<div align="center">')
            lines.append('')
            lines.append('## 📋 Contents')
            lines.append('')
            lines.append('| # | Project | Categories |')
            lines.append('|:---:|:----------|:------------|')
            for i, p in enumerate(self.projects, 1):
                title = p.title or f"Project {i}"
                anchor = re.sub(r'[^a-z0-9\-]', '', title.lower().replace(' ', '-'))
                cat = p.category_display
                lines.append(f'| {i} | [{title}](#{anchor}) | {cat} |')
            lines.append('')
            lines.append('</div>')
            lines.append('')
            lines.append('---')
            lines.append('')
        
        # Projects
        for i, p in enumerate(self.projects):
            if i > 0:
                lines.append("")
                lines.append("<hr>")
                lines.append("")
            lines.append(self._generate_project_md(p))
        
        # Footer
        lines.append('')
        lines.append('---')
        lines.append('')
        lines.append('<div align="center">')
        lines.append('')
        lines.append(f'<sub>Last updated: {datetime.now().strftime("%B %d, %Y")}</sub>')
        lines.append('')
        lines.append('</div>')
        
        return '\n'.join(lines)
        
    # File operations
    def _open_file(self):
        """Open markdown file"""
        path = filedialog.askopenfilename(
            title="Open Projects File",
            filetypes=[("Markdown", "*.md"), ("All", "*.*")]
        )
        if not path:
            return
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._parse_md(content)
            self.file_path = path
            self.has_changes = False
            self._update_status()
            
            if self.projects:
                self.selected_index = 0
                self.project_listbox.selection_set(0)
                self._load_project(self.projects[0])
                self._update_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open: {e}")
            
    def _parse_md(self, content: str):
        """Parse markdown into projects"""
        self.projects = []
        
        # Split by <hr> or horizontal rule
        parts = re.split(r'<hr>|(?:\n---\n)', content)
        
        for part in parts:
            if "## " not in part:
                continue
                
            p = Project()
            
            # Title
            m = re.search(r'##\s+(.+)', part)
            if m:
                p.title = m.group(1).strip()
                p.id = re.sub(r'[^a-z0-9\-]', '', p.title.lower().replace(' ', '-'))
            
            # Category badges (multiple) - find all backtick categories
            category_matches = re.findall(r'`([^`]+)`', part)
            # Filter out code blocks (tech stack uses <code> tags)
            known_categories =  ["Mobile App", "Website", "IoT", "Game", "AI/ML", "3D/AR/VR", "Other"]
            p.categories = [c for c in category_matches if c in known_categories]
            
            # Short description (bold)
            m = re.search(r'\*\*([^*]+)\*\*', part)
            if m:
                p.short_description = m.group(1).strip()
            
            # Long description in <p>
            m = re.search(r'<p>([^<]+)</p>', part)
            if m and '<a href' not in m.group(0) and '<img' not in m.group(0):
                p.long_description = m.group(1).strip()
            
            # Tech stack
            tech_section = re.search(r'###\s*Tech Stack.*?<p>(.*?)</p>', part, re.DOTALL)
            if tech_section:
                p.technologies = re.findall(r'<code>([^<]+)</code>', tech_section.group(1))
            
            # Features
            features_section = re.search(r'###\s*Features(.*?)(?=###|$)', part, re.DOTALL)
            if features_section:
                p.features = re.findall(r'-\s+(.+)', features_section.group(1))
            
            # Links
            if 'play.google.com' in part:
                m = re.search(r'href="(https://play\.google\.com[^"]+)"', part)
                if m:
                    p.links["playStore"] = m.group(1)
            if 'apps.apple.com' in part:
                m = re.search(r'href="(https://apps\.apple\.com[^"]+)"', part)
                if m:
                    p.links["appStore"] = m.group(1)
            if 'github.com' in part:
                m = re.search(r'href="(https://github\.com[^"]+)"', part)
                if m:
                    p.links["github"] = m.group(1)
            # Website link - match any URL with Website badge
            website_match = re.search(r'href="([^"]+)"[^>]*>\s*<img[^>]*Website', part)
            if website_match:
                p.links["website"] = website_match.group(1)
            # APK link
            apk_match = re.search(r'href="([^"]+)"[^>]*>\s*<img[^>]*APK', part)
            if apk_match:
                p.links["apk"] = apk_match.group(1)
            
            # Screenshots - find all image references
            ss_matches = re.findall(r'images/[^/]+/(\d+)\.(png|jpg|jpeg|webp|gif)', part)
            if ss_matches:
                for num, ext in ss_matches:
                    p.screenshots.append(f"screenshot_{num}.{ext}")
                    p.screenshots_local_paths.append(f"screenshot_{num}.{ext}")
            
            # Banner
            banner_match = re.search(r'<img src="([^"]+)"[^>]*alt="[^"]*"[^>]*width="100%"', part)
            if banner_match:
                p.banner_image = banner_match.group(1)
            
            # Logo
            logo_match = re.search(r'<img src="([^"]+)"[^>]*alt="[^"]*logo"[^>]*height="64"', part)
            if logo_match:
                p.logo_url = logo_match.group(1)
                p.show_logo = True
            
            # Border styling
            if 'border: 1px solid' in part or 'border: 2px dashed' in part:
                p.show_border = True
                if 'border-radius: 12px' in part:
                    p.border_style = "rounded"
                elif 'dashed' in part:
                    p.border_style = "dashed"
                else:
                    p.border_style = "square"
            
            # Screenshot layout
            if '<table' in part:
                p.screenshot_layout = "grid"
            elif 'align="center"' in part and '<br>' in part:
                p.screenshot_layout = "vertical"
            else:
                p.screenshot_layout = "horizontal"
            
            # Screenshot size
            size_match = re.search(r'width="(\d+)"', part)
            if size_match:
                try:
                    p.screenshot_size = int(size_match.group(1))
                except:
                    pass
            
            if p.title:
                self.projects.append(p)
                
        self._refresh_list()
        
    def _export_file(self):
        """Export to markdown"""
        self._save_current()
        
        if not self.file_path:
            path = filedialog.asksaveasfilename(
                title="Export README.md",
                defaultextension=".md",
                initialfile="README.md",
                filetypes=[("Markdown", "*.md")]
            )
            if not path:
                return
            self.file_path = path
            
        try:
            content = self._generate_full_md()
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Ask to copy images
            has_images = any(
                (p.banner_image and os.path.exists(p.banner_image)) or 
                any(os.path.exists(ss) for ss in p.screenshots_local_paths)
                for p in self.projects
            )
            
            if has_images:
                if messagebox.askyesno("Copy Images", 
                    "Do you want to copy images to the output directory?\n\n"
                    "Images will be organized as:\n"
                    "  images/{project-id}/banner.ext\n"
                    "  images/{project-id}/1.ext, 2.ext, ..."):
                    self._copy_images()
            
            self.has_changes = False
            self._update_status()
            messagebox.showinfo("Success", f"Exported to:\n{self.file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
            
    def _copy_images(self):
        """Copy images to output directory"""
        if not self.file_path:
            return
            
        base_dir = os.path.dirname(self.file_path)
        copied = 0
        
        for p in self.projects:
            if not p.id:
                continue
                
            project_images_dir = os.path.join(base_dir, "images", p.id)
            
            # Copy logo
            if p.show_logo and p.logo_url and os.path.exists(p.logo_url):
                os.makedirs(project_images_dir, exist_ok=True)
                ext = os.path.splitext(p.logo_url)[1]
                dest = os.path.join(project_images_dir, f"logo{ext}")
                try:
                    shutil.copy2(p.logo_url, dest)
                    copied += 1
                except Exception as e:
                    print(f"Failed to copy logo: {e}")
            
            # Copy banner
            if p.banner_image and os.path.exists(p.banner_image):
                os.makedirs(project_images_dir, exist_ok=True)
                ext = os.path.splitext(p.banner_image)[1]
                dest = os.path.join(project_images_dir, f"banner{ext}")
                try:
                    shutil.copy2(p.banner_image, dest)
                    copied += 1
                except Exception as e:
                    print(f"Failed to copy banner: {e}")
            
            # Copy screenshots
            for i, ss_path in enumerate(p.screenshots_local_paths, 1):
                if os.path.exists(ss_path):
                    os.makedirs(project_images_dir, exist_ok=True)
                    ext = os.path.splitext(ss_path)[1]
                    dest = os.path.join(project_images_dir, f"{i}{ext}")
                    try:
                        shutil.copy2(ss_path, dest)
                        copied += 1
                    except Exception as e:
                        print(f"Failed to copy screenshot: {e}")
        
        if copied > 0:
            messagebox.showinfo("Images Copied", f"Copied {copied} image(s) to the images folder.")
            
    def _on_close(self):
        """Handle close"""
        if self.has_changes:
            r = messagebox.askyesnocancel("Unsaved Changes", "Save before closing?")
            if r is None:
                return
            if r:
                self._export_file()
        self.destroy()


if __name__ == "__main__":
    app = ProjectManagerApp()
    app.mainloop()
