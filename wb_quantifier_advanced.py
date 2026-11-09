"""
Western Blot Lane Quantification Tool - Advanced Version

This script provides an interactive interface for selecting lanes in Western blot images
and generating intensity profiles with advanced quantification features.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.widgets import Cursor, SpanSelector
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageDraw
from image_utils import load_image, export_png
from scipy import signal
from scipy.interpolate import UnivariateSpline
from scipy.optimize import curve_fit
import csv
import os
import hashlib
from datetime import datetime, timezone

import quant_core as qc

try:
    from version import __version__, get_git_commit
except ImportError:
    __version__ = 'dev'
    get_git_commit = lambda: 'unknown'


class WesternBlotQuantifier:
    """Main class for Western blot quantification"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Western Blot Quantifier - Advanced")
        self.root.minsize(1100, 750)  # Set minimum window size to fit all elements
        
        # Image variables
        self.original_image = None
        self.display_image = None
        self.image_path = None
        self.photo = None
        self.image_page = 0

        # Display parameters (non-destructive)
        self.p_low = 0.5
        self.p_high = 99.5
        self.gamma = 1.0
        self.apply_display_to_quant = False
        # Band polarity: if True bands are bright on dark background
        self.bands_are_bright = tk.BooleanVar(value=False)
        # Explicit invert option (user can flip image for bright/dark convenience)
        self.invert_image_var = tk.BooleanVar(value=False)
                
        # Lane selection variables
        self.lanes = []  # List of lane rectangles (x, y, width, height)
        self.lane_size = None  # (width, height) set by first lane
        self.current_rect = None  # Current rectangle being drawn
        self.rect_start = None
        self.drawing = False
        self.selected_lane_idx = None  # Currently selected lane for moving

        # Background ROI boxes for LOQ analysis
        self.background_boxes = []  # List of (x, y, w, h) background rectangles
        self.background_lane_map = []  # Lane association for each BG box (lane idx or None)
        self.selected_background_idx = None
        self.draw_mode_var = tk.StringVar(value='lane')  # 'lane' or 'background'
        self.bg_offset_var = tk.IntVar(value=20)
        self.selected_lane_indices = set()
        self.selected_background_indices = set()

        # Mouse drag state
        self.dragging_existing = False
        self.drag_target_type = None  # 'lane' or 'background'
        self.drag_target_idx = None
        self.drag_anchor = None

        # Quantification variables
        self.lane_profiles = []  # Store intensity profiles
        self.band_data = []  # Store quantification results
        self.reference_band_width = None
        self.baseline_method = tk.StringVar(value="minimum")
        self.integration_method = tk.StringVar(value="fixed_width")
        self.peak_threshold = tk.DoubleVar(value=0.1)  # 10% of peak height
        
        # Canvas variables
        self.canvas = None
        self.canvas_width = 600  # Reduced from 800
        self.canvas_height = 450  # Reduced from 600
        
        # Setup GUI
        self.setup_gui()
        
    def setup_gui(self):
        """Initialize GUI components with tabbed interface"""
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load Image", command=self.load_image)
        file_menu.add_separator()
        file_menu.add_command(label="Save Lane Configuration", command=self.save_lane_config)
        file_menu.add_command(label="Load Lane Configuration", command=self.load_lane_config)
        file_menu.add_separator()
        file_menu.add_command(label="Export Data", command=self.export_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Main frame with notebook (tabs)
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Lane Selection
        tab1_frame = tk.Frame(notebook)
        notebook.add(tab1_frame, text="Lane Selection")
        self.setup_lane_selection_tab(tab1_frame)
        
        # Tab 2: Export Image
        tab2_frame = tk.Frame(notebook)
        notebook.add(tab2_frame, text="Export Image")
        self.setup_export_image_tab(tab2_frame)
    
    def setup_lane_selection_tab(self, parent):
        """Setup lane selection and quantification tab"""
        # Left panel - Image canvas
        left_frame = tk.Frame(parent)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        left_frame.pack_propagate(False)  # Prevent frame from shrinking
        
        # Canvas for image display (fixed size)
        self.canvas = tk.Canvas(left_frame, width=self.canvas_width, height=self.canvas_height, bg='gray')
        self.canvas.pack(padx=5, pady=5)
        
        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        
        # Bind keyboard events
        self.root.bind("<Left>", self.move_lane_left)
        self.root.bind("<Right>", self.move_lane_right)
        self.root.bind("<Up>", self.move_lane_up)
        self.root.bind("<Down>", self.move_lane_down)
        self.root.bind("<Delete>", self.delete_selected_lane)
        self.root.bind("<BackSpace>", self.delete_selected_lane)
        
        # Control panel
        control_frame = tk.Frame(left_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=3)
        
        tk.Button(control_frame, text="Load Image", command=self.load_image, wraplength=80, width=10).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(control_frame, text="Clear Lanes", command=self.clear_lanes, wraplength=80, width=10).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(control_frame, text="Add Lanes", command=self.add_multiple_lanes, wraplength=80, width=10).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(control_frame, text="Ref Band", command=self.set_reference_band, wraplength=80, width=10).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(control_frame, text="Analyze", command=self.analyze_bands, wraplength=80, width=10).pack(side=tk.LEFT, padx=2, pady=2)

        # Background / LOQ drawing controls
        bg_ctrl_frame = tk.Frame(left_frame)
        bg_ctrl_frame.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(bg_ctrl_frame, text="Draw mode:", font=('Arial', 8)).pack(side=tk.LEFT, padx=(0, 3))
        tk.Radiobutton(bg_ctrl_frame, text="Lanes", variable=self.draw_mode_var, value='lane',
                       font=('Arial', 8)).pack(side=tk.LEFT, padx=2)
        tk.Radiobutton(bg_ctrl_frame, text="Background", variable=self.draw_mode_var, value='background',
                       font=('Arial', 8)).pack(side=tk.LEFT, padx=2)
        tk.Label(bg_ctrl_frame, text="Offset:", font=('Arial', 8)).pack(side=tk.LEFT, padx=(6, 2))
        tk.Spinbox(
            bg_ctrl_frame,
            from_=-2000,
            to=2000,
            textvariable=self.bg_offset_var,
            width=5,
            font=('Arial', 8)
        ).pack(side=tk.LEFT, padx=1)
        tk.Button(
            bg_ctrl_frame,
            text="BG from lanes",
            command=self.generate_background_boxes_from_lanes,
            font=('Arial', 8),
            width=12
        ).pack(side=tk.LEFT, padx=3)
        tk.Label(
            bg_ctrl_frame,
            text="Shift+Click = multi-select",
            font=('Arial', 8),
            fg='gray40'
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(bg_ctrl_frame, text="Clear BG", command=self.clear_background_boxes,
                  font=('Arial', 8), width=7).pack(side=tk.LEFT, padx=4)
        tk.Button(bg_ctrl_frame, text="Calc LOQ", command=self.calculate_loq,
                  bg='dodgerblue', fg='white', font=('Arial', 8, 'bold'), width=8,
                  activebackground='darkblue', activeforeground='white',
                  relief=tk.RAISED, bd=2, highlightthickness=0).pack(side=tk.LEFT, padx=2)

        # Scrollable instructions frame
        inst_label = tk.Label(left_frame, text="Instructions:", font=('Arial', 10, 'bold'))
        inst_label.pack(anchor=tk.W, padx=5, pady=2)
        
        inst_frame = tk.Frame(left_frame, height=60, bg='lightyellow')
        inst_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=3)
        inst_frame.pack_propagate(False)
        
        inst_scrollbar = tk.Scrollbar(inst_frame)
        inst_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        inst_text = tk.Text(inst_frame, height=6, font=('Arial', 8), yscrollcommand=inst_scrollbar.set, wrap=tk.WORD)
        inst_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inst_scrollbar.config(command=inst_text.yview)
        
        instructions = """1. Load a Western blot image
2. Draw lane rectangles (first sets size for all)
3. Use 'Add Lanes' to quickly create many lanes
4. Use arrow keys to fine-tune positions
5. Save lane configuration for reuse
6. Click 'Analyze' for quantification"""
        
        inst_text.insert(tk.END, instructions)
        inst_text.config(state=tk.DISABLED)  # Read-only
        
        # Right panel - Scrollable controls and Lane list
        right_frame = tk.Frame(parent)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=5, pady=5)
        right_frame.pack_propagate(False)
        right_frame.config(width=280)
        
        # Quantification settings
        settings_frame = tk.LabelFrame(right_frame, text="Quantification Settings", font=('Arial', 9, 'bold'))
        settings_frame.pack(fill=tk.X, pady=3, padx=5)
        
        # Integration method
        tk.Label(settings_frame, text="Integration Method:", font=('Arial', 8)).pack(anchor=tk.W, padx=5, pady=1)
        methods = [
            ("Fixed Width (Reference)", "fixed_width"),
            ("Peak % Height", "percent_height"),
            ("Whole Lane (Box Total)", "full_profile"),
            ("Interactive Selection", "interactive")
        ]
        for text, value in methods:
            tk.Radiobutton(settings_frame, text=text, variable=self.integration_method, 
                          value=value, font=('Arial', 7)).pack(anchor=tk.W, padx=20)
        
        # Peak threshold for percent height method
        threshold_frame = tk.Frame(settings_frame)
        threshold_frame.pack(fill=tk.X, padx=5, pady=3)
        tk.Label(threshold_frame, text="Peak Threshold:", font=('Arial', 8)).pack(side=tk.LEFT)
        tk.Scale(threshold_frame, from_=0.05, to=0.5, resolution=0.05, 
                orient=tk.HORIZONTAL, variable=self.peak_threshold, 
                length=60, font=('Arial', 7)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Baseline correction
        tk.Label(settings_frame, text="Baseline Correction:", font=('Arial', 8)).pack(anchor=tk.W, padx=5, pady=1)
        baselines = [
            # ("Linear", "linear"),  # disabled for now
            ("Minimum", "minimum"),
            ("Background Boxes (Median)", "background_boxes"),
            ("Manual Region (Interactive)", "manual_region")
        ]
        for text, value in baselines:
            tk.Radiobutton(settings_frame, text=text, variable=self.baseline_method, 
                          value=value, font=('Arial', 7)).pack(anchor=tk.W, padx=20)
        
        # Small options
        tk.Checkbutton(settings_frame, text="Bands are bright", 
                      variable=self.bands_are_bright, font=('Arial', 7)).pack(anchor=tk.W, padx=20, pady=1)
        tk.Checkbutton(settings_frame, text="Invert for analysis", 
                      variable=self.invert_image_var, font=('Arial', 7)).pack(anchor=tk.W, padx=20, pady=1)
                
        # Lane list
        tk.Label(right_frame, text="Lanes:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=3, padx=5)
        
        # Lanes listbox with scrollbar
        lanes_frame = tk.Frame(right_frame)
        lanes_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
        
        lanes_scrollbar = tk.Scrollbar(lanes_frame)
        lanes_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.lane_listbox = tk.Listbox(lanes_frame, height=5, font=('Arial', 8), yscrollcommand=lanes_scrollbar.set)
        self.lane_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lanes_scrollbar.config(command=self.lane_listbox.yview)
        self.lane_listbox.bind('<<ListboxSelect>>', self.on_lane_select)
        
        # Reference band info
        self.ref_info_label = tk.Label(right_frame, text="Reference Width: Not Set", 
                                       font=('Arial', 8), fg='blue')
        self.ref_info_label.pack(anchor=tk.W, padx=5, pady=3)
    
    def setup_export_image_tab(self, parent):
        """Setup export image tab with live preview"""
        def bind_preview_update(widget):
            widget.bind("<Return>", lambda event: self.update_export_preview())
            widget.bind("<FocusOut>", lambda event: self.update_export_preview())

        def bind_coarse_scale_click(scale_widget, coarse_step):
            """Use coarse jumps when clicking the scale trough (not the slider)."""
            def on_scale_click(event):
                try:
                    part = scale_widget.identify(event.x, event.y)
                except Exception:
                    part = None

                # Let native behavior handle direct slider drag.
                if part == 'slider':
                    return None

                try:
                    current = float(scale_widget.get())
                    slider_x, _ = scale_widget.coords(current)
                    step = float(coarse_step)
                    delta = step if event.x > slider_x else -step
                    new_val = current + delta
                    lo = float(scale_widget.cget('from'))
                    hi = float(scale_widget.cget('to'))
                    new_val = max(min(new_val, max(lo, hi)), min(lo, hi))
                    scale_widget.set(new_val)
                    self.update_export_preview()
                    return "break"
                except Exception:
                    return None

            scale_widget.bind("<Button-1>", on_scale_click, add="+")

        # Left panel - Preview canvas
        left_frame = tk.Frame(parent)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(left_frame, text="Live Preview", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Create matplotlib figure for preview
        self.export_fig, self.export_ax = plt.subplots(figsize=(8, 6))
        self.export_canvas = FigureCanvasTkAgg(self.export_fig, master=left_frame)
        self.export_canvas.draw()
        self.export_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Right panel - Controls
        right_frame = tk.Frame(parent, width=250)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=10)
        
        # Display controls
        controls_frame = tk.LabelFrame(right_frame, text="Display Adjustments", font=('Arial', 10, 'bold'))
        controls_frame.pack(fill=tk.X, pady=5)
        
        # Percentile low
        p_low_frame = tk.Frame(controls_frame)
        p_low_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(p_low_frame, text="Percentile Low:", width=15).pack(side=tk.LEFT)
        self.p_low_var = tk.DoubleVar(value=self.p_low)
        p_low_scale = tk.Scale(p_low_frame, from_=0, to=75, resolution=0.01, bigincrement=0.5,
                              orient=tk.HORIZONTAL, variable=self.p_low_var,
                              command=self.update_export_preview)
        p_low_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        bind_coarse_scale_click(p_low_scale, coarse_step=0.1)
        p_low_spin = tk.Spinbox(
            p_low_frame,
            from_=0,
            to=75,
            increment=0.01,
            textvariable=self.p_low_var,
            width=7,
            format="%.2f",
            command=self.update_export_preview
        )
        p_low_spin.pack(side=tk.RIGHT)
        bind_preview_update(p_low_spin)
        
        # Percentile high
        p_high_frame = tk.Frame(controls_frame)
        p_high_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(p_high_frame, text="Percentile High:", width=15).pack(side=tk.LEFT)
        self.p_high_var = tk.DoubleVar(value=self.p_high)
        p_high_scale = tk.Scale(p_high_frame, from_=50, to=100, resolution=0.01, bigincrement=0.5,
                               orient=tk.HORIZONTAL, variable=self.p_high_var,
                               command=self.update_export_preview)
        p_high_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        bind_coarse_scale_click(p_high_scale, coarse_step=0.1)
        p_high_spin = tk.Spinbox(
            p_high_frame,
            from_=50,
            to=100,
            increment=0.01,
            textvariable=self.p_high_var,
            width=7,
            format="%.2f",
            command=self.update_export_preview
        )
        p_high_spin.pack(side=tk.RIGHT)
        bind_preview_update(p_high_spin)
        
        # Gamma
        gamma_frame = tk.Frame(controls_frame)
        gamma_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(gamma_frame, text="Gamma:", width=15).pack(side=tk.LEFT)
        self.gamma_var = tk.DoubleVar(value=self.gamma)
        gamma_scale = tk.Scale(gamma_frame, from_=0.1, to=3.0, resolution=0.01, bigincrement=0.1,
                              orient=tk.HORIZONTAL, variable=self.gamma_var,
                              command=self.update_export_preview)
        gamma_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        bind_coarse_scale_click(gamma_scale, coarse_step=0.1)
        gamma_spin = tk.Spinbox(
            gamma_frame,
            from_=0.1,
            to=3.0,
            increment=0.01,
            textvariable=self.gamma_var,
            width=7,
            format="%.2f",
            command=self.update_export_preview
        )
        gamma_spin.pack(side=tk.RIGHT)
        bind_preview_update(gamma_spin)
        
        # Invert checkbox
        invert_frame = tk.Frame(controls_frame)
        invert_frame.pack(fill=tk.X, padx=5, pady=5)
        self.export_invert_var = tk.BooleanVar(value=False)
        tk.Checkbutton(invert_frame, text="Invert Colors", variable=self.export_invert_var,
                      command=self.update_export_preview).pack(anchor=tk.W)
        
        # Button frame
        button_frame_top = tk.Frame(right_frame)
        button_frame_top.pack(fill=tk.X, pady=5)
        tk.Button(button_frame_top, text="Load\nPreview", command=self.update_export_preview,
                 bg='green3', fg='white', font=('Arial', 9, 'bold'),
                 width=15, height=2, activebackground='green4', activeforeground='white',
                 relief=tk.RAISED, bd=2, highlightthickness=0).pack(pady=3)
        
        # Export button
        export_frame = tk.Frame(right_frame)
        export_frame.pack(fill=tk.X, pady=5)
        tk.Button(export_frame, text="Export\nPNG", command=self.export_image_from_tab,
                 bg='dodgerblue', fg='white', font=('Arial', 9, 'bold'),
                 width=15, height=2, activebackground='darkblue', activeforeground='white',
                 relief=tk.RAISED, bd=2, highlightthickness=0).pack(pady=3)
        
        # Info label
        info_label = tk.Label(right_frame, text="Click 'Load Preview' to load image.\nAdjust sliders to preview.\nClick 'Export PNG' to save.",
                             font=('Arial', 8), fg='#333333', wraplength=180, justify=tk.CENTER)
        info_label.pack(pady=10)
        
        # Initial preview
        self.update_export_preview()
    
    def update_export_preview(self, *args):
        """Update the export preview canvas with current settings"""
        if self.original_image is None:
            self.export_ax.clear()
            self.export_ax.text(0.5, 0.5, 'If you have loaded an image,\nplease click "Load Preview" to view it here', 
                               ha='center', va='center', transform=self.export_ax.transAxes,
                               fontsize=11, color='darkgray', style='italic')
            self.export_ax.axis('off')
            self.export_canvas.draw()
            return
        
        # Get current values from sliders
        p_low = self.p_low_var.get()
        p_high = self.p_high_var.get()
        gamma = self.gamma_var.get()
        invert = self.export_invert_var.get()
        
        try:
            # Load raw image
            arr, meta = load_image(self.image_path, page=self.image_page, return_raw=True)
        except Exception:
            arr = np.array(self.original_image.convert('L'), dtype=np.float64)
        
        # Convert to float64
        arr = np.array(arr, dtype=np.float64)
        
        # Handle multi-dimensional arrays
        if arr.ndim == 3:
            if arr.shape[2] in (3, 4):
                arr = np.mean(arr[..., :3], axis=2)
            else:
                arr = arr[0] if arr.shape[0] < 10 else np.mean(arr, axis=0)
        elif arr.ndim > 2:
            arr = arr[0]
        
        # Normalize using percentiles
        vmin = np.percentile(arr, p_low)
        vmax = np.percentile(arr, p_high)
        arr_norm = (arr - vmin) / (vmax - vmin + 1e-8)
        arr_norm = np.clip(arr_norm, 0, 1)
        
        # Apply gamma
        arr_norm = np.power(arr_norm, 1.0 / gamma)
        
        # Apply invert if needed
        if invert:
            arr_norm = 1.0 - arr_norm
        
        # Convert to uint8 for display
        arr_display = (arr_norm * 255).astype(np.uint8)
        
        # Update preview
        self.export_ax.clear()
        self.export_ax.imshow(arr_display, cmap='gray')
        self.export_ax.set_title('Export Preview', fontweight='bold')
        self.export_ax.axis('off')
        self.export_canvas.draw()
    
    def export_image_from_tab(self):
        """Export the current preview as PNG"""
        if self.original_image is None:
            messagebox.showwarning("Warning", "Load an image first")
            return
        
        out_path = filedialog.asksaveasfilename(defaultextension='.png', 
                                               filetypes=[('PNG', '*.png'), ('All', '*.*')])
        if not out_path:
            return
        
        try:
            # Get values from sliders
            p_low = self.p_low_var.get()
            p_high = self.p_high_var.get()
            gamma = self.gamma_var.get()
            invert = self.export_invert_var.get()
            
            # Load raw and process
            arr, meta = load_image(self.image_path, page=self.image_page, return_raw=True)
            arr = np.array(arr, dtype=np.float64)
            
            if arr.ndim == 3:
                if arr.shape[2] in (3, 4):
                    arr = np.mean(arr[..., :3], axis=2)
                else:
                    arr = arr[0] if arr.shape[0] < 10 else np.mean(arr, axis=0)
            elif arr.ndim > 2:
                arr = arr[0]
            
            # Normalize
            vmin = np.percentile(arr, p_low)
            vmax = np.percentile(arr, p_high)
            arr_norm = (arr - vmin) / (vmax - vmin + 1e-8)
            arr_norm = np.clip(arr_norm, 0, 1)
            arr_norm = np.power(arr_norm, 1.0 / gamma)
            
            if invert:
                arr_norm = 1.0 - arr_norm
            
            # Convert to uint8 and save
            arr_uint8 = (arr_norm * 255).astype(np.uint8)
            img_out = Image.fromarray(arr_uint8, mode='L')
            img_out.save(out_path, 'PNG', quality=95)
            
            messagebox.showinfo("Success", f"Image exported to {out_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
        
    def load_image(self):
        """Load an image file"""
        file_path = filedialog.askopenfilename(
            title="Select Western Blot Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            self.image_path = file_path
            try:
                img, meta = load_image(file_path, page=None, p_low=self.p_low, p_high=self.p_high, gamma=self.gamma)
                # If multi-page TIFF, ask user which page to use
                if meta.get('n_pages', 1) > 1:
                    page = tk.simpledialog.askinteger(
                        "Multi-page TIFF",
                        "File contains {} pages. Select page (0-{}):".format(meta['n_pages'], meta['n_pages']-1),
                        minvalue=0, maxvalue=meta['n_pages']-1,
                        initialvalue=0
                    )
                    if page is None:
                        return
                    self.image_page = page
                    img, meta = load_image(file_path, page=page, p_low=self.p_low, p_high=self.p_high, gamma=self.gamma)
                else:
                    self.image_page = 0
                self.original_image = img
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {e}")
                return

            # Clear previous data
            self.clear_lanes()
            self.band_data = []
            self.lane_profiles = []

            # Display image
            self.update_display()
            
    def update_display(self):
        """Update the canvas with current image and lanes"""
        if self.original_image is None:
            return
        
        # Create a copy for display
        display_img = self.original_image.copy()
        draw = ImageDraw.Draw(display_img)
        
        # Draw existing lanes
        for idx, (x, y, w, h) in enumerate(self.lanes):
            is_sel = idx in self.selected_lane_indices
            color = (0, 255, 0) if is_sel else (255, 255, 0)
            width = 3 if is_sel else 2
            
            # Draw rectangle
            for i in range(width):
                draw.rectangle([x-i, y-i, x+w+i, y+h+i], outline=color)
            
            # Draw label
            draw.text((x, max(0, y-15)), "L{}".format(idx+1), fill=color)

        # Draw background ROI boxes in cyan
        for bg_idx, (bx, by, bw, bh) in enumerate(self.background_boxes):
            is_sel = bg_idx in self.selected_background_indices
            bg_color = (50, 255, 255) if is_sel else (0, 210, 210)
            for i in range(2):
                draw.rectangle([bx-i, by-i, bx+bw+i, by+bh+i], outline=bg_color)
            lane_tag = ""
            if bg_idx < len(self.background_lane_map) and self.background_lane_map[bg_idx] is not None:
                lane_tag = "(L{})".format(self.background_lane_map[bg_idx] + 1)
            draw.text((bx+2, max(0, by-13)), "BG{}{}".format(bg_idx+1, lane_tag), fill=bg_color)

        # Draw current rectangle being created
        if self.current_rect is not None:
            x, y, w, h = self.current_rect
            for i in range(2):
                draw.rectangle([x-i, y-i, x+w+i, y+h+i], outline=(0, 255, 255))
        
        # Resize image to fit canvas while maintaining aspect ratio
        img_w, img_h = display_img.size
        scale = min(self.canvas_width / img_w, self.canvas_height / img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        
        self.display_scale = scale
        resized = display_img.resize((new_w, new_h), Image.LANCZOS)
        
        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(resized)
        
        # Update canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        
        # Update canvas size
        self.canvas.config(width=new_w, height=new_h)
        
    def canvas_to_image_coords(self, canvas_x, canvas_y):
        """Convert canvas coordinates to image coordinates"""
        if not hasattr(self, 'display_scale'):
            return canvas_x, canvas_y
        img_x = int(canvas_x / self.display_scale)
        img_y = int(canvas_y / self.display_scale)
        return img_x, img_y

    def _rect_contains(self, rect, x, y):
        rx, ry, rw, rh = rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def _event_has_shift(self, event):
        # Tk state bitmask: Shift is bit 0x0001
        return bool(getattr(event, 'state', 0) & 0x0001)

    def _focused_widget_is_text_input(self, widget=None):
        """Return True when keyboard focus is in an input widget.

        This prevents global keybindings (e.g., BackSpace/Delete for lane deletion)
        from firing while the user edits values in Entry/Spinbox/Combobox/Text controls.
        """
        if widget is None:
            widget = self.root.focus_get()
        if widget is None:
            return False

        widget_class = str(widget.winfo_class())
        if widget_class in {'Entry', 'TEntry', 'Spinbox', 'TSpinbox', 'Text', 'Combobox', 'TCombobox'}:
            return True

        text_input_types = [tk.Entry, tk.Spinbox, tk.Text, ttk.Entry, ttk.Combobox]
        ttk_spinbox = getattr(ttk, 'Spinbox', None)
        if ttk_spinbox is not None:
            text_input_types.append(ttk_spinbox)

        try:
            return isinstance(widget, tuple(text_input_types))
        except Exception:
            return False

    def _clamp_rect(self, x, y, w, h):
        if self.original_image is None:
            return int(x), int(y)
        img_w, img_h = self.original_image.size
        cx = max(0, min(img_w - w, int(x)))
        cy = max(0, min(img_h - h, int(y)))
        return cx, cy

    def _move_background_by_index(self, bg_idx, dx, dy):
        if bg_idx is None or bg_idx < 0 or bg_idx >= len(self.background_boxes):
            return 0, 0
        bx, by, bw, bh = self.background_boxes[bg_idx]
        new_x, new_y = self._clamp_rect(bx + dx, by + dy, bw, bh)
        self.background_boxes[bg_idx] = (new_x, new_y, bw, bh)
        return new_x - bx, new_y - by

    def _move_lane_by_index(self, lane_idx, dx, dy, move_associated_bg=True):
        if lane_idx is None or lane_idx < 0 or lane_idx >= len(self.lanes):
            return 0, 0
        x, y, w, h = self.lanes[lane_idx]
        new_x, new_y = self._clamp_rect(x + dx, y + dy, w, h)
        actual_dx = new_x - x
        actual_dy = new_y - y
        self.lanes[lane_idx] = (new_x, new_y, w, h)

        if move_associated_bg and (actual_dx != 0 or actual_dy != 0):
            for bg_idx, assoc_lane in enumerate(self.background_lane_map):
                if assoc_lane == lane_idx:
                    self._move_background_by_index(bg_idx, actual_dx, actual_dy)

        return actual_dx, actual_dy

    def _move_lane_group(self, lane_indices, dx, dy):
        lane_indices = sorted(set(i for i in lane_indices if 0 <= i < len(self.lanes)))
        if not lane_indices or self.original_image is None:
            return 0, 0

        group_boxes = [self.lanes[i] for i in lane_indices]
        # Include lane-associated BG boxes in constraints so they move together safely
        assoc_bg_indices = [
            bg_idx for bg_idx, assoc_lane in enumerate(self.background_lane_map)
            if assoc_lane in lane_indices and 0 <= bg_idx < len(self.background_boxes)
        ]
        group_boxes.extend(self.background_boxes[i] for i in assoc_bg_indices)

        img_w, img_h = self.original_image.size
        left_limit = min(x for x, _, _, _ in group_boxes)
        top_limit = min(y for _, y, _, _ in group_boxes)
        right_limit = min(img_w - (x + w) for x, _, w, _ in group_boxes)
        bottom_limit = min(img_h - (y + h) for _, y, _, h in group_boxes)

        actual_dx = max(-left_limit, min(right_limit, int(dx)))
        actual_dy = max(-top_limit, min(bottom_limit, int(dy)))
        if actual_dx == 0 and actual_dy == 0:
            return 0, 0

        for lane_idx in lane_indices:
            x, y, w, h = self.lanes[lane_idx]
            self.lanes[lane_idx] = (x + actual_dx, y + actual_dy, w, h)

        for bg_idx in assoc_bg_indices:
            bx, by, bw, bh = self.background_boxes[bg_idx]
            self.background_boxes[bg_idx] = (bx + actual_dx, by + actual_dy, bw, bh)

        return actual_dx, actual_dy

    def _move_background_group(self, bg_indices, dx, dy):
        bg_indices = sorted(set(i for i in bg_indices if 0 <= i < len(self.background_boxes)))
        if not bg_indices or self.original_image is None:
            return 0, 0

        group_boxes = [self.background_boxes[i] for i in bg_indices]
        img_w, img_h = self.original_image.size
        left_limit = min(x for x, _, _, _ in group_boxes)
        top_limit = min(y for _, y, _, _ in group_boxes)
        right_limit = min(img_w - (x + w) for x, _, w, _ in group_boxes)
        bottom_limit = min(img_h - (y + h) for _, y, _, h in group_boxes)

        actual_dx = max(-left_limit, min(right_limit, int(dx)))
        actual_dy = max(-top_limit, min(bottom_limit, int(dy)))
        if actual_dx == 0 and actual_dy == 0:
            return 0, 0

        for bg_idx in bg_indices:
            bx, by, bw, bh = self.background_boxes[bg_idx]
            self.background_boxes[bg_idx] = (bx + actual_dx, by + actual_dy, bw, bh)

        return actual_dx, actual_dy

    def generate_background_boxes_from_lanes(self):
        """Create one background box per lane using a user-selected Y offset."""
        if self.original_image is None:
            messagebox.showwarning("Warning", "Please load an image first.")
            return
        if len(self.lanes) == 0:
            messagebox.showwarning("Warning", "Please define lanes first.")
            return

        try:
            offset = int(self.bg_offset_var.get())
        except (tk.TclError, ValueError, TypeError):
            # Recover from a temporarily empty/invalid spinbox value.
            offset = 0
            self.bg_offset_var.set(offset)
        img_w, img_h = self.original_image.size

        generated_boxes = []
        generated_map = []
        for lane_idx, (x, y, w, h) in enumerate(self.lanes):
            # Offset starts from lane bottom, then places a full-height BG box.
            bg_y = y + h + offset
            if bg_y < 0:
                bg_y = 0
            if bg_y + h > img_h:
                bg_y = max(0, img_h - h)
            bg_x = min(max(0, x), max(0, img_w - w))
            generated_boxes.append((bg_x, bg_y, w, h))
            generated_map.append(lane_idx)

        self.background_boxes = generated_boxes
        self.background_lane_map = generated_map
        self.selected_background_idx = None
        self.selected_background_indices = set()
        self.draw_mode_var.set('background')
        self.update_display()
        messagebox.showinfo(
            "Background Boxes Created",
            "Created {} background boxes from lanes with offset {} px.".format(len(generated_boxes), offset)
        )
    
    def on_mouse_down(self, event):
        """Handle mouse button press"""
        if self.original_image is None:
            return

        # Returning focus to the canvas ensures BackSpace/Delete hotkeys work
        # after editing spinboxes or other text inputs.
        self.canvas.focus_set()

        self.dragging_existing = False
        self.drag_target_type = None
        self.drag_target_idx = None
        self.drag_anchor = None

        img_x, img_y = self.canvas_to_image_coords(event.x, event.y)
        shift_pressed = self._event_has_shift(event)

        # Click-to-select and drag existing lane boxes
        if self.draw_mode_var.get() == 'lane':
            for idx, lane in enumerate(self.lanes):
                if self._rect_contains(lane, img_x, img_y):
                    if shift_pressed:
                        if idx not in self.selected_lane_indices:
                            self.selected_lane_indices.add(idx)
                    else:
                        self.selected_lane_indices = {idx}
                    if len(self.selected_lane_indices) == 0:
                        self.selected_lane_indices = {idx}
                    self.selected_lane_idx = idx
                    self.selected_background_idx = None
                    self.selected_background_indices = set()
                    self.lane_listbox.selection_clear(0, tk.END)
                    self.lane_listbox.selection_set(idx)
                    self.dragging_existing = True
                    self.drag_target_type = 'lane'
                    self.drag_target_idx = idx
                    self.drag_anchor = (img_x, img_y)
                    self.update_display()
                    return

        # Click-to-select and drag existing background boxes
        if self.draw_mode_var.get() == 'background':
            for idx, bg_rect in enumerate(self.background_boxes):
                if self._rect_contains(bg_rect, img_x, img_y):
                    if shift_pressed:
                        if idx not in self.selected_background_indices:
                            self.selected_background_indices.add(idx)
                    else:
                        self.selected_background_indices = {idx}
                    if len(self.selected_background_indices) == 0:
                        self.selected_background_indices = {idx}
                    self.selected_background_idx = idx
                    self.selected_lane_idx = None
                    self.selected_lane_indices = set()
                    self.dragging_existing = True
                    self.drag_target_type = 'background'
                    self.drag_target_idx = idx
                    self.drag_anchor = (img_x, img_y)
                    self.update_display()
                    return

        # Start drawing new rectangle
        self.drawing = True
        self.rect_start = (img_x, img_y)
        self.selected_lane_idx = None
        self.selected_lane_indices = set()
        self.selected_background_idx = None
        self.selected_background_indices = set()
        
    def on_mouse_drag(self, event):
        """Handle mouse drag"""
        img_x, img_y = self.canvas_to_image_coords(event.x, event.y)

        if self.dragging_existing and self.drag_anchor is not None:
            dx = img_x - self.drag_anchor[0]
            dy = img_y - self.drag_anchor[1]

            if dx == 0 and dy == 0:
                return

            if self.drag_target_type == 'lane':
                self._move_lane_group(self.selected_lane_indices, dx, dy)
            elif self.drag_target_type == 'background':
                self._move_background_group(self.selected_background_indices, dx, dy)

            self.drag_anchor = (img_x, img_y)
            self.update_display()
            return

        if not self.drawing or self.rect_start is None:
            return

        start_x, start_y = self.rect_start
        
        if self.lane_size is None or self.draw_mode_var.get() == 'background':
            # Free-draw: first lane defines size; background boxes are always free-drawn
            width = abs(img_x - start_x)
            height = abs(img_y - start_y)
            x = min(start_x, img_x)
            y = min(start_y, img_y)
        else:
            # Subsequent lanes - use predefined size, just position
            width, height = self.lane_size
            x = img_x - width // 2
            y = img_y - height // 2
        
        self.current_rect = (x, y, width, height)
        self.update_display()
        
    def on_mouse_up(self, event):
        """Handle mouse button release"""
        if self.dragging_existing:
            self.dragging_existing = False
            self.drag_target_type = None
            self.drag_target_idx = None
            self.drag_anchor = None
            return

        if not self.drawing:
            return
        
        self.drawing = False
        
        if self.current_rect is None:
            return
        
        x, y, w, h = self.current_rect
        
        # Validate rectangle size
        if w < 5 or h < 5:
            self.current_rect = None
            self.update_display()
            return
        
        # Route to background boxes or lanes depending on draw mode
        if self.draw_mode_var.get() == 'background':
            self.background_boxes.append((x, y, w, h))
            self.background_lane_map.append(None)
            self.selected_background_indices = {len(self.background_boxes) - 1}
            self.selected_background_idx = len(self.background_boxes) - 1
            self.current_rect = None
            self.update_display()
            return

        # Add lane
        if self.lane_size is None:
            # First lane sets the size
            self.lane_size = (w, h)

        self.lanes.append((x, y, w, h))
        self.selected_lane_idx = len(self.lanes) - 1
        self.selected_lane_indices = {self.selected_lane_idx}
        self.current_rect = None

        # Update lane list
        self.update_lane_list()
        self.update_display()
        
    def update_lane_list(self):
        """Update the lane listbox"""
        self.lane_listbox.delete(0, tk.END)
        for idx in range(len(self.lanes)):
            self.lane_listbox.insert(tk.END, "Lane {}".format(idx+1))
    
    def on_lane_select(self, event):
        """Handle lane selection from listbox"""
        selection = self.lane_listbox.curselection()
        if selection:
            self.selected_lane_idx = selection[0]
            self.selected_lane_indices = {self.selected_lane_idx}
            self.selected_background_idx = None
            self.selected_background_indices = set()
            self.update_display()
    
    def move_lane_left(self, event):
        """Move selected lane left"""
        self.move_selected_lane(-5, 0)
    
    def move_lane_right(self, event):
        """Move selected lane right"""
        self.move_selected_lane(5, 0)
    
    def move_lane_up(self, event):
        """Move selected lane up"""
        self.move_selected_lane(0, -5)
    
    def move_lane_down(self, event):
        """Move selected lane down"""
        self.move_selected_lane(0, 5)
    
    def move_selected_lane(self, dx, dy):
        """Move the selected lane by dx, dy"""
        if self.original_image is None:
            return

        if self.draw_mode_var.get() == 'background':
            if len(self.selected_background_indices) == 0 and (self.selected_background_idx is not None):
                self.selected_background_indices = {self.selected_background_idx}
            if len(self.selected_background_indices) == 0:
                return
            self._move_background_group(self.selected_background_indices, dx, dy)
            self.update_display()
            return

        if len(self.selected_lane_indices) == 0 and (self.selected_lane_idx is not None):
            self.selected_lane_indices = {self.selected_lane_idx}
        if len(self.selected_lane_indices) == 0:
            return

        self._move_lane_group(self.selected_lane_indices, dx, dy)
        self.update_display()
    
    def delete_selected_lane(self, event):
        """Delete the selected lane"""
        event_widget = getattr(event, 'widget', None) if event is not None else None
        if self._focused_widget_is_text_input(event_widget) or self._focused_widget_is_text_input():
            return

        if self.selected_lane_idx is None or self.selected_lane_idx >= len(self.lanes):
            return

        deleted_idx = self.selected_lane_idx
        del self.lanes[deleted_idx]

        # Remove or remap associated background boxes
        kept_boxes = []
        kept_map = []
        for bg_rect, lane_idx in zip(self.background_boxes, self.background_lane_map):
            if lane_idx == deleted_idx:
                continue
            if lane_idx is not None and lane_idx > deleted_idx:
                lane_idx -= 1
            kept_boxes.append(bg_rect)
            kept_map.append(lane_idx)
        self.background_boxes = kept_boxes
        self.background_lane_map = kept_map
        self.selected_background_idx = None
        self.selected_background_indices = set()
        
        # If all lanes deleted, reset lane size
        if len(self.lanes) == 0:
            self.lane_size = None
        
        self.selected_lane_idx = None
        self.selected_lane_indices = set()
        self.update_lane_list()
        self.update_display()
    
    def clear_lanes(self):
        """Clear all lanes"""
        self.lanes = []
        self.lane_size = None
        self.selected_lane_idx = None
        self.selected_lane_indices = set()
        self.background_boxes = []
        self.background_lane_map = []
        self.selected_background_idx = None
        self.selected_background_indices = set()
        self.reference_band_width = None
        self.ref_info_label.config(text="Reference Width: Not Set")
        self.update_lane_list()
        self.update_display()
    
    def add_multiple_lanes(self):
        """Add multiple lanes automatically"""
        if self.original_image is None:
            messagebox.showwarning("Warning", "Please load an image first.")
            return
        
        if self.lane_size is None:
            messagebox.showwarning("Warning", "Please draw the first lane to set the size first.")
            return
        
        # Create dialog for lane creation
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Multiple Lanes")
        dialog.geometry("400x300")
        
        tk.Label(dialog, text="Add Multiple Lanes", font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Number of lanes
        num_frame = tk.Frame(dialog)
        num_frame.pack(pady=10)
        tk.Label(num_frame, text="Number of lanes to add:", font=('Arial', 11)).pack(side=tk.LEFT, padx=5)
        num_var = tk.IntVar(value=5)
        tk.Spinbox(num_frame, from_=1, to=50, textvariable=num_var, width=10, font=('Arial', 11)).pack(side=tk.LEFT)
        
        # Spacing
        spacing_frame = tk.Frame(dialog)
        spacing_frame.pack(pady=10)
        tk.Label(spacing_frame, text="Spacing between lanes (px):", font=('Arial', 11)).pack(side=tk.LEFT, padx=5)
        spacing_var = tk.IntVar(value=10)
        tk.Spinbox(spacing_frame, from_=0, to=200, textvariable=spacing_var, width=10, font=('Arial', 11)).pack(side=tk.LEFT)
        
        # Direction
        direction_frame = tk.Frame(dialog)
        direction_frame.pack(pady=10)
        tk.Label(direction_frame, text="Direction:", font=('Arial', 11)).pack(side=tk.LEFT, padx=5)
        direction_var = tk.StringVar(value="horizontal")
        tk.Radiobutton(direction_frame, text="Horizontal", variable=direction_var, value="horizontal").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(direction_frame, text="Vertical", variable=direction_var, value="vertical").pack(side=tk.LEFT, padx=5)

        # Horizontal growth direction
        h_growth_frame = tk.Frame(dialog)
        h_growth_frame.pack(pady=5)
        tk.Label(h_growth_frame, text="Horizontal growth:", font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        horizontal_growth_var = tk.StringVar(value="right")
        tk.Radiobutton(h_growth_frame, text="Right", variable=horizontal_growth_var,
                   value="right").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(h_growth_frame, text="Left", variable=horizontal_growth_var,
                   value="left").pack(side=tk.LEFT, padx=5)
        
        # Starting position
        start_frame = tk.Frame(dialog)
        start_frame.pack(pady=10)
        
        if len(self.lanes) > 0:
            # Use last lane as starting point
            last_lane = self.lanes[-1]
            default_x, default_y = last_lane[0], last_lane[1]
        else:
            default_x, default_y = 50, 50
        
        tk.Label(start_frame, text="Start X:", font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        start_x_var = tk.IntVar(value=default_x)
        tk.Spinbox(start_frame, from_=0, to=5000, textvariable=start_x_var, width=8).pack(side=tk.LEFT, padx=2)
        
        tk.Label(start_frame, text="Start Y:", font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        start_y_var = tk.IntVar(value=default_y)
        tk.Spinbox(start_frame, from_=0, to=5000, textvariable=start_y_var, width=8).pack(side=tk.LEFT, padx=2)
        
        # Buttons
        def create_lanes():
            num_lanes = num_var.get()
            spacing = spacing_var.get()
            direction = direction_var.get()
            start_x = start_x_var.get()
            start_y = start_y_var.get()
            w, h = self.lane_size
            
            img_w, img_h = self.original_image.size
            
            for i in range(num_lanes):
                if direction == "horizontal":
                    step = (w + spacing) * (1 if horizontal_growth_var.get() == "right" else -1)
                    x = start_x + i * step
                    y = start_y
                else:  # vertical
                    x = start_x
                    y = start_y + i * (h + spacing)
                
                # Check bounds
                if x >= 0 and y >= 0 and x + w <= img_w and y + h <= img_h:
                    self.lanes.append((x, y, w, h))
                else:
                    messagebox.showwarning("Warning", 
                                         "Lane {} would be out of bounds. Created {} lanes.".format(i+1, i))
                    break
            
            self.update_lane_list()
            self.update_display()
            dialog.destroy()
            messagebox.showinfo("Success", "Added {} lanes".format(min(num_lanes, len(self.lanes))))
        
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)
        tk.Button(button_frame, text="Create Lanes", command=create_lanes, 
                 bg='green', fg='white', font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def save_lane_config(self):
        """Save lane configuration to a JSON file"""
        if len(self.lanes) == 0:
            messagebox.showwarning("Warning", "No lanes to save.")
            return
        
        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Lane Configuration"
        )
        
        if save_path:
            import json
            config = {
                'lanes': self.lanes,
                'lane_size': self.lane_size,
                'reference_band_width': self.reference_band_width,
                'background_boxes': self.background_boxes,
                'background_lane_map': self.background_lane_map,
                'image_path': self.image_path,
                'image_size': self.original_image.size if self.original_image else None,
                'image_page': self.image_page,
                'tool_version': __version__,
                'git_commit': get_git_commit(),
                'baseline_method': getattr(self, 'baseline_method', None) and self.baseline_method.get(),
                'integration_method': getattr(self, 'integration_method', None) and self.integration_method.get(),
                'bands_are_bright': bool(getattr(self, 'bands_are_bright', None) and self.bands_are_bright.get()),
                'invert_for_analysis': bool(getattr(self, 'invert_image_var', None) and self.invert_image_var.get()),
                'peak_threshold': getattr(self, 'peak_threshold', None) and self.peak_threshold.get(),
                'display_params': {
                    'p_low': self.p_low,
                    'p_high': self.p_high,
                    'gamma': self.gamma
                }
            }
            
            try:
                with open(save_path, 'w') as f:
                    json.dump(config, f, indent=2)
                messagebox.showinfo("Success", "Lane configuration saved to:\n{}".format(save_path))
            except Exception as e:
                messagebox.showerror("Error", "Failed to save configuration:\n{}".format(str(e)))
    
    def load_lane_config(self):
        """Load lane configuration from a JSON file"""
        load_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Lane Configuration"
        )
        
        if load_path:
            import json
            try:
                with open(load_path, 'r') as f:
                    config = json.load(f)
                
                # Check if image size matches (optional warning)
                if self.original_image and config.get('image_size'):
                    current_size = self.original_image.size
                    saved_size = tuple(config['image_size'])
                    if current_size != saved_size:
                        response = messagebox.askyesno(
                            "Image Size Mismatch",
                            "The saved configuration was for an image of size {}x{},\n"
                            "but current image is {}x{}.\n\n"
                            "Load anyway?".format(
                                saved_size[0], saved_size[1],
                                current_size[0], current_size[1]
                            )
                        )
                        if not response:
                            return
                
                # Load configuration
                self.lanes = [tuple(lane) for lane in config.get('lanes', [])]
                self.lane_size = tuple(config['lane_size']) if config.get('lane_size') else None
                self.reference_band_width = config.get('reference_band_width')
                self.background_boxes = [tuple(bg) for bg in config.get('background_boxes', [])]
                self.background_lane_map = list(config.get('background_lane_map', [None] * len(self.background_boxes)))
                if len(self.background_lane_map) < len(self.background_boxes):
                    self.background_lane_map.extend([None] * (len(self.background_boxes) - len(self.background_lane_map)))
                elif len(self.background_lane_map) > len(self.background_boxes):
                    self.background_lane_map = self.background_lane_map[:len(self.background_boxes)]
                self.selected_background_idx = None
                self.selected_background_indices = set()
                self.selected_lane_idx = None
                self.selected_lane_indices = set()
                # Load persisted page and display params if present
                self.image_page = config.get('image_page', 0)
                dp = config.get('display_params', {})
                if dp:
                    self.p_low = dp.get('p_low', self.p_low)
                    self.p_high = dp.get('p_high', self.p_high)
                    self.gamma = dp.get('gamma', self.gamma)
                
                # Update UI
                self.update_lane_list()
                self.update_display()
                
                if self.reference_band_width:
                    self.ref_info_label.config(
                        text="Reference Width: {} pixels".format(self.reference_band_width)
                    )
                
                messagebox.showinfo("Success", 
                                  "Loaded {} lanes from configuration.\n"
                                  "Reference width: {}".format(
                                      len(self.lanes),
                                      self.reference_band_width if self.reference_band_width else "Not set"
                                  ))
                
            except Exception as e:
                messagebox.showerror("Error", "Failed to load configuration:\n{}".format(str(e)))
    
    def set_reference_band(self):
        """Interactively set reference band width from a clean peak"""
        if len(self.lanes) == 0:
            messagebox.showwarning("Warning", "No lanes defined. Please select lanes first.")
            return
        
        # Extract profiles
        profiles = self.extract_profiles()
        
        # Create selection window
        ref_window = tk.Toplevel(self.root)
        ref_window.title("Set Reference Band Width")
        ref_window.geometry("900x700")
        
        instructions = tk.Label(ref_window,
                               text="METHOD 1: Click and drag horizontally across a clean band\nMETHOD 2: Click two points to mark band boundaries",
                               font=('Arial', 10, 'bold'), bg='lightyellow', pady=15)
        instructions.pack(fill=tk.X)
        
        # Lane selector
        selector_frame = tk.Frame(ref_window)
        selector_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(selector_frame, text="Select Lane:", font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        
        current_lane = [0]
        selected_width = [None]
        self.span_selector = None  # Store reference to prevent garbage collection
        click_points = []  # Store click positions for two-click method
        
        lane_var = tk.StringVar(value="Lane 1")
        lane_menu = ttk.Combobox(selector_frame, textvariable=lane_var, 
                                 values=["Lane {}".format(i+1) for i in range(len(profiles))],
                                 state='readonly', width=15)
        lane_menu.pack(side=tk.LEFT, padx=5)
        
        # Plot
        fig, ax = plt.subplots(figsize=(9, 5))
        
        def update_plot():
            ax.clear()
            lane_idx = current_lane[0]
            profile = profiles[lane_idx]
            
            # Detect peaks
            peaks, _ = self.detect_peaks(profile)
            
            x = np.arange(len(profile))
            ax.plot(x, profile, 'b-', linewidth=2, label='Profile')
            
            if len(peaks) > 0:
                ax.plot(peaks, profile[peaks], 'ro', markersize=8, label='Detected Peaks')
            
            ax.set_title('Lane {} - Click and drag across a clean band'.format(lane_idx + 1), 
                        fontweight='bold', fontsize=12)
            ax.set_xlabel('Position (pixels)', fontsize=10)
            ax.set_ylabel('Intensity', fontsize=10)
            ax.grid(True, alpha=0.3)
            ax.legend()
            ax.invert_yaxis()
            
            # Clear previous click points when changing lanes
            click_points.clear()
            
            # Mouse click handler for two-click method
            def onclick(event):
                if event.inaxes != ax:
                    return
                
                x_pos = int(event.xdata)
                click_points.append(x_pos)
                
                # Mark click position
                ax.axvline(x_pos, color='red', linestyle='--', linewidth=2)
                canvas.draw()
                
                if len(click_points) == 1:
                    status_label.config(text="First point marked. Click second point to complete selection.",
                                      fg='orange')
                elif len(click_points) >= 2:
                    # Calculate width from two points
                    x1, x2 = sorted(click_points[-2:])
                    width = x2 - x1
                    selected_width[0] = width
                    
                    # Visual feedback
                    ax.axvspan(x1, x2, alpha=0.3, color='green')
                    ax.text((x1 + x2) / 2, ax.get_ylim()[0] * 0.95,
                           'Selected Width: {} pixels'.format(width),
                           ha='center', fontsize=11, fontweight='bold',
                           bbox=dict(boxstyle='round', facecolor='lightgreen', 
                                   edgecolor='green', linewidth=2))
                    canvas.draw()
                    
                    status_label.config(
                        text="Selected Width: {} pixels - Click 'Apply' or click two new points".format(width),
                        fg='green')
                    
                    # Reset for next selection
                    click_points.clear()
            
            # Recreate span selector for drag method
            def onselect(xmin, xmax):
                if xmax - xmin < 5:
                    return
                
                width = int(xmax - xmin)
                selected_width[0] = width
                
                # Visual feedback
                ax.axvspan(xmin, xmax, alpha=0.3, color='green')
                ax.text((xmin + xmax) / 2, ax.get_ylim()[0] * 0.95,
                       'Selected Width: {} pixels'.format(width),
                       ha='center', fontsize=11, fontweight='bold',
                       bbox=dict(boxstyle='round', facecolor='lightgreen', 
                               edgecolor='green', linewidth=2))
                canvas.draw()
                
                status_label.config(text="Selected Width: {} pixels - Click 'Apply' to use this width".format(width),
                                  fg='green')
            
            # Connect click event
            fig.canvas.mpl_connect('button_press_event', onclick)
            
            self.span_selector = SpanSelector(ax, onselect, 'horizontal', useblit=True,
                              props=dict(alpha=0.5, facecolor='green'),
                              interactive=True, drag_from_anywhere=True)
            
            canvas.draw()
        
        def on_lane_change(event):
            lane_text = lane_var.get()
            current_lane[0] = int(lane_text.split()[1]) - 1
            selected_width[0] = None  # Reset selection when changing lanes
            click_points.clear()  # Clear click points
            update_plot()
        
        lane_menu.bind('<<ComboboxSelected>>', on_lane_change)
        
        # Canvas
        canvas = FigureCanvasTkAgg(fig, master=ref_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Status label
        status_label = tk.Label(ref_window, 
                               text="Click-drag across band OR click two boundary points",
                               font=('Arial', 10), fg='blue', wraplength=800)
        status_label.pack(pady=5)
        
        # Show initial plot (this will create the span selector)
        update_plot()
        
        # Buttons
        button_frame = tk.Frame(ref_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def apply_width():
            if selected_width[0] is None:
                messagebox.showwarning("Warning", "Please select a band width first.")
                return
            
            self.reference_band_width = selected_width[0]
            self.ref_info_label.config(text="Reference Width: {} pixels".format(self.reference_band_width))
            messagebox.showinfo("Success", 
                              "Reference band width set to {} pixels.\nThis will be used for fixed-width integration.".format(self.reference_band_width))
            ref_window.destroy()
        
        def reset_width():
            self.reference_band_width = None
            self.ref_info_label.config(text="Reference Width: Not Set")
            ref_window.destroy()
        
        tk.Button(button_frame, text="Apply Width", command=apply_width, 
                 bg='green', fg='white', font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Reset Width", command=reset_width).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=ref_window.destroy).pack(side=tk.RIGHT, padx=5)
    
    def extract_profiles(self):
        """Extract intensity profiles from all lanes"""
        if len(self.lanes) == 0:
            return []

        gray_array = self._load_raw_analysis_array(apply_invert=True)
        if gray_array is None:
            return []

        profiles = []
        for x, y, w, h in self.lanes:
            # Extract lane region
            lane_roi = gray_array[y:y+h, x:x+w]
            
            # Calculate intensity profile (average across width)
            profile = np.mean(lane_roi, axis=1)
            profiles.append(profile)
        
        return profiles
    
    def detect_peaks(self, profile, min_distance=20):
        """Detect peaks in intensity profile"""
        return qc.detect_strongest_peak(
            profile,
            min_distance=min_distance,
            bands_are_bright=bool(getattr(self, 'bands_are_bright', None) and self.bands_are_bright.get())
        )
    
    def calculate_baseline(self, profile, method='linear', lane_idx=None, bg_baselines=None):
        """Calculate baseline for profile"""
        if method == 'background_boxes' and bg_baselines is None:
            bg_baselines = self._compute_background_baselines()
        return qc.calculate_baseline(
            profile,
            method,
            lane_idx=lane_idx,
            bg_baselines=bg_baselines,
            bands_are_bright=bool(getattr(self, 'bands_are_bright', None) and self.bands_are_bright.get())
        )
    
    def integrate_peak(self, profile, peak_idx, method='fixed_width', width=None, threshold=0.1, lane_idx=None, bg_baselines=None):
        """Integrate area under peak"""
        baseline = self.calculate_baseline(
            profile,
            self.baseline_method.get(),
            lane_idx=lane_idx,
            bg_baselines=bg_baselines
        )
        corrected = profile - baseline
        # If bands are bright, we want positive 'corrected' values for bands; if background-subtracted
        # yields negative for bright bands (unlikely), flip sign to make area positive
        if getattr(self, 'bands_are_bright', None) and self.bands_are_bright.get():
            # prefer positive peaks -> ensure corrected has positive peaks
            if np.nanmax(corrected) < abs(np.nanmin(corrected)):
                corrected = -corrected

        return qc.integrate_peak(
            corrected, peak_idx, method=method, width=width, threshold=threshold
        )
    
    def analyze_bands(self):
        """Analyze bands with advanced quantification"""
        if len(self.lanes) == 0:
            messagebox.showwarning("Warning", "No lanes defined. Please select lanes first.")
            return
        
        # Extract profiles
        self.lane_profiles = self.extract_profiles()
        
        method = self.integration_method.get()
        
        if method == 'interactive':
            self.interactive_band_analysis()
        else:
            self.automatic_band_analysis()
    
    def automatic_band_analysis(self):
        """Automatic band detection and quantification"""
        method = self.integration_method.get()
        baseline_method = self.baseline_method.get()
        bg_baselines = self._compute_background_baselines() if baseline_method == 'background_boxes' else None
        
        # Create results window
        results_window = tk.Toplevel(self.root)
        results_window.title("Band Analysis Results")
        results_window.geometry("1000x800")

        instructions = tk.Label(
            results_window,
            text="Review one lane at a time using Previous/Next.",
            font=('Arial', 10), bg='lightyellow', pady=10
        )
        instructions.pack(fill=tk.X)

        # Analyze all lanes first, then render lane-by-lane pages.
        n_lanes = len(self.lane_profiles)
        lane_results = []
        self.band_data = []
        
        # Analyze each lane
        for idx, profile in enumerate(self.lane_profiles):
            baseline = self.calculate_baseline(profile, baseline_method, lane_idx=idx, bg_baselines=bg_baselines)
            corrected = profile - baseline

            # Detect peaks unless full-profile integration is selected
            if method == 'full_profile':
                peaks = np.array([], dtype=int)
            else:
                peaks, _ = self.detect_peaks(profile)
            
            # Integrate peaks
            lane_bands = []
            if method == 'full_profile':
                # Integrate everything in the lane box as one band.
                if getattr(self, 'bands_are_bright', None) and self.bands_are_bright.get():
                    peak_idx = int(np.argmax(corrected))
                else:
                    peak_idx = int(np.argmin(corrected))

                band_info = self.integrate_peak(
                    profile,
                    peak_idx,
                    method='full_profile',
                    lane_idx=idx,
                    bg_baselines=bg_baselines
                )
                band_info['lane'] = idx + 1
                band_info['baseline_source'] = baseline_method
                band_info['baseline_value'] = float(np.median(baseline))
                band_info['baseline_region'] = None
                band_info['integration_method'] = method
                band_info['fit_method'] = 'none'
                band_info['fit_params'] = None
                band_info['fit_polarity'] = None
                band_info['fit_area'] = None
                band_info['fit_area_scope'] = None
                lane_bands.append(band_info)
            else:
                for peak_idx in peaks:
                    if method == 'fixed_width':
                        # Use reference width or estimate from first peak
                        if self.reference_band_width is None and len(peaks) > 0:
                            # Estimate width from first peak (fallback)
                            self.reference_band_width = self.estimate_band_width(profile, peaks[0])
                            self.ref_info_label.config(
                                text="Reference Width: {} px (auto)".format(self.reference_band_width)
                            )

                        band_info = self.integrate_peak(
                            profile, peak_idx,
                            method='fixed_width',
                            width=self.reference_band_width,
                            lane_idx=idx,
                            bg_baselines=bg_baselines
                        )
                    elif method == 'percent_height':
                        band_info = self.integrate_peak(
                            profile, peak_idx,
                            method='percent_height',
                            threshold=self.peak_threshold.get(),
                            lane_idx=idx,
                            bg_baselines=bg_baselines
                        )

                    # Add lane info
                    band_info['lane'] = idx + 1
                    band_info['baseline_source'] = baseline_method
                    band_info['baseline_value'] = float(np.median(baseline))
                    band_info['baseline_region'] = None
                    band_info['integration_method'] = method
                    band_info['fit_method'] = 'none'
                    band_info['fit_params'] = None
                    band_info['fit_polarity'] = None
                    band_info['fit_area'] = None
                    band_info['fit_area_scope'] = None
                    lane_bands.append(band_info)
            
            self.band_data.extend(lane_bands)

            lane_results.append({
                'lane_index': idx,
                'profile': profile,
                'baseline': baseline,
                'corrected': corrected,
                'peaks': peaks,
                'bands': lane_bands
            })

        fig, ax = plt.subplots(figsize=(10, 6))
        canvas = FigureCanvasTkAgg(fig, master=results_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        status_label = tk.Label(
            results_window,
            text="",
            font=('Arial', 9),
            fg='blue',
            pady=4
        )
        status_label.pack(fill=tk.X)

        current_lane = [0]

        def show_lane(lane_pos):
            if lane_pos < 0 or lane_pos >= len(lane_results):
                return

            lane_data = lane_results[lane_pos]
            lane_idx = lane_data['lane_index']
            profile = lane_data['profile']
            baseline = lane_data['baseline']
            corrected = lane_data['corrected']
            peaks = lane_data['peaks']
            lane_bands = lane_data['bands']

            ax.clear()
            x = np.arange(len(profile))
            ax.plot(x, profile, 'b-', linewidth=2, label='Raw Profile')
            ax.plot(x, baseline, 'g--', linewidth=1, label='Baseline')
            ax.plot(x, corrected, 'r-', linewidth=1.5, label='Corrected', alpha=0.7)

            if len(peaks) > 0:
                ax.plot(peaks, profile[peaks], 'ro', markersize=8, label='Detected Peaks')

            for band in lane_bands:
                start, end = band['start'], band['end']
                peak_pos = band.get('peak_position', (start + end) // 2)
                area = band.get('area', 0.0)

                ax.axvspan(start, end, alpha=0.2, color='yellow')
                ax.axvline(peak_pos, color='red', linestyle=':', alpha=0.5)

                mid_point = (start + end) / 2
                if method == 'full_profile':
                    label_txt = 'Whole-lane area: {:.0f}'.format(area)
                else:
                    label_txt = 'Area: {:.0f}'.format(area)
                ax.text(mid_point, np.max(profile) * 0.9,
                        label_txt,
                        ha='center', fontsize=8,
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            if method == 'full_profile':
                ax.set_title('Lane {} - dominant peak from whole-lane profile'.format(lane_idx + 1), fontweight='bold')
            else:
                ax.set_title('Lane {} - {} peaks detected'.format(lane_idx + 1, len(peaks)), fontweight='bold')
            ax.set_xlabel('Position (pixels)')
            ax.set_ylabel('Intensity')
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8, loc='upper right')
            ax.invert_yaxis()

            status_label.config(
                text='Lane {} of {} | {} bands quantified'.format(lane_pos + 1, len(lane_results), len(lane_bands))
            )

            fig.tight_layout()
            canvas.draw()
        
        # Add buttons
        button_frame = tk.Frame(results_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        def next_lane():
            if current_lane[0] < len(lane_results) - 1:
                current_lane[0] += 1
                show_lane(current_lane[0])

        def prev_lane():
            if current_lane[0] > 0:
                current_lane[0] -= 1
                show_lane(current_lane[0])
        
        tk.Button(button_frame, text="Previous Lane", command=prev_lane).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Next Lane", command=next_lane).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Save Plot", command=lambda: self.save_plot(fig)).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Export Data (CSV)", command=self.export_data).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Show Summary", command=self.show_summary).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Finish", command=lambda: results_window.destroy()).pack(side=tk.RIGHT, padx=5)

        show_lane(0)
    
    def interactive_band_analysis(self):
        """Interactive band selection and quantification"""
        # Create interactive window
        results_window = tk.Toplevel(self.root)
        results_window.title("Interactive Band Analysis")
        results_window.geometry("1000x800")
        self.interactive_span_selector = None
        
        instructions = tk.Label(results_window, 
                               text="Drag to select band boundaries. Optional: manual baseline region, Gaussian fit over selection, or full-area Gaussian extrapolation.",
                               font=('Arial', 10), bg='lightyellow', pady=10)
        instructions.pack(fill=tk.X)
        
        # Current lane index
        current_lane = [0]
        selected_bands = []
        selection_state = {'mode': 'band', 'pending_band': None}
        use_manual_baseline_var = tk.BooleanVar(value=(self.baseline_method.get() == 'manual_region'))
        use_peak_fit_var = tk.BooleanVar(value=False)
        use_peak_fit_full_var = tk.BooleanVar(value=False)
        baseline_method = self.baseline_method.get()
        bg_baselines = self._compute_background_baselines() if baseline_method == 'background_boxes' else None
        
        fig, ax = plt.subplots(figsize=(10, 6))

        # Embed plot
        canvas = FigureCanvasTkAgg(fig, master=results_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        status_label = tk.Label(
            results_window,
            text="Drag to select a band region.",
            font=('Arial', 9),
            fg='blue',
            pady=4
        )
        status_label.pack(fill=tk.X)

        def reset_selection_state():
            selection_state['mode'] = 'band'
            selection_state['pending_band'] = None

        def fit_single_peak_gaussian(x_vals, y_vals):
            """Fit a single Gaussian to a selected corrected-signal region."""
            return qc.fit_single_peak_gaussian(x_vals, y_vals)

        def finalize_band_for_lane(profile, lane_idx, start, end, baseline_region=None):
            start = max(0, min(int(start), len(profile) - 1))
            end = max(0, min(int(end), len(profile)))
            if end - start < 2:
                return

            if baseline_region is not None:
                b_start, b_end = baseline_region
                b_start = max(0, min(int(b_start), len(profile) - 1))
                b_end = max(0, min(int(b_end), len(profile)))
                if b_end <= b_start:
                    baseline_value = float(np.median(profile))
                else:
                    baseline_value = float(np.median(profile[b_start:b_end]))
                baseline = np.full_like(profile, baseline_value, dtype=np.float64)
                baseline_source = 'manual_region'
                baseline_region_saved = (b_start, b_end)
            else:
                baseline_method_used = self.baseline_method.get()
                if baseline_method_used == 'manual_region':
                    baseline_method_used = 'minimum'
                baseline = self.calculate_baseline(
                    profile,
                    baseline_method_used,
                    lane_idx=lane_idx,
                    bg_baselines=bg_baselines
                )
                baseline_value = float(np.median(baseline))
                baseline_source = baseline_method_used
                baseline_region_saved = None

            corrected = profile - baseline
            region = corrected[start:end]
            if len(region) == 0:
                return

            peak_in_region = np.argmin(region)
            peak_idx = start + int(peak_in_region)

            fit_method = 'none'
            fit_params = None
            fit_polarity = None
            fit_area = None
            fit_area_scope = None

            if use_peak_fit_var.get() or use_peak_fit_full_var.get():
                x_region = np.arange(start, end, dtype=np.float64)
                fit_result = fit_single_peak_gaussian(x_region, region)
                if fit_result is not None:
                    if use_peak_fit_full_var.get():
                        area = float(fit_result['full_area'])
                        fit_area_scope = 'full_gaussian'
                        fit_method = 'single_gaussian_full_area'
                    else:
                        area = float(fit_result['selected_area'])
                        fit_area_scope = 'selected_region'
                        fit_method = 'single_gaussian'
                    height = float(fit_result['peak_height'])
                    peak_idx = int(fit_result['peak_position'])
                    fit_params = (
                        float(fit_result['amp']),
                        float(fit_result['mu']),
                        float(fit_result['sigma'])
                    )
                    fit_polarity = float(fit_result['polarity'])
                    fit_area = float(area)
                else:
                    area = np.trapz(corrected[start:end])
                    height = corrected[peak_idx]
                    if area < 0:
                        area = -area
                        height = -height
            else:
                area = np.trapz(corrected[start:end])
                height = corrected[peak_idx]
                if area < 0:
                    area = -area
                    height = -height

            band_info = {
                'lane': lane_idx + 1,
                'area': float(area),
                'height': float(height),
                'width': int(end - start),
                'start': int(start),
                'end': int(end),
                'peak_position': int(peak_idx),
                'baseline_source': baseline_source,
                'baseline_value': baseline_value,
                'baseline_region': baseline_region_saved,
                'integration_method': 'interactive',
                'fit_method': fit_method,
                'fit_params': fit_params,
                'fit_polarity': fit_polarity,
                'fit_area': fit_area,
                'fit_area_scope': fit_area_scope
            }
            selected_bands.append(band_info)
        
        def show_lane(lane_idx):
            ax.clear()
            if lane_idx >= len(self.lane_profiles):
                messagebox.showinfo("Complete", "All lanes analyzed!")
                results_window.destroy()
                self.band_data = selected_bands
                self.show_summary()
                return

            reset_selection_state()
            
            profile = self.lane_profiles[lane_idx]
            baseline_method_for_display = self.baseline_method.get()
            if baseline_method_for_display == 'manual_region':
                baseline_method_for_display = 'minimum'
            baseline = self.calculate_baseline(
                profile,
                baseline_method_for_display,
                lane_idx=lane_idx,
                bg_baselines=bg_baselines
            )
            corrected = profile - baseline
            
            x = np.arange(len(profile))
            ax.plot(x, profile, 'b-', linewidth=2, label='Profile')
            ax.plot(x, baseline, 'g--', linewidth=1, label='Baseline')
            ax.set_title('Lane {} - Click and drag to select bands'.format(lane_idx + 1), fontweight='bold')
            ax.set_xlabel('Position (pixels)')
            ax.set_ylabel('Intensity')
            ax.grid(True, alpha=0.3)
            ax.legend()
            ax.invert_yaxis()

            # Redraw previously selected bands for this lane
            lane_saved = [b for b in selected_bands if b.get('lane') == lane_idx + 1]
            for band in lane_saved:
                b_start = band.get('start', 0)
                b_end = band.get('end', 0)
                b_area = band.get('area', 0.0)
                ax.axvspan(b_start, b_end, alpha=0.3, color='yellow')
                ax.text((b_start + b_end) / 2, np.max(profile) * 0.9,
                        'Area: {:g}'.format(b_area),
                        ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='wheat'))

                if band.get('baseline_source') == 'manual_region':
                    ax.hlines(
                        band.get('baseline_value', 0.0),
                        b_start,
                        b_end,
                        colors='purple',
                        linestyles='--',
                        linewidth=1.5
                    )

                if band.get('fit_method') in ('single_gaussian', 'single_gaussian_full_area') and band.get('fit_params') is not None:
                    amp, mu, sigma = band.get('fit_params')
                    polarity = band.get('fit_polarity', 1.0)
                    sigma_safe = max(float(sigma), 1e-6)

                    x_min = max(0.0, float(mu - 4.0 * sigma_safe))
                    x_max = min(float(len(profile) - 1), float(mu + 4.0 * sigma_safe))
                    x_fit = np.linspace(x_min, x_max, 300)
                    if len(x_fit) > 0:
                        y_fit_corr = polarity * (amp * np.exp(-0.5 * ((x_fit - mu) / sigma_safe) ** 2))

                        if band.get('baseline_source') == 'manual_region':
                            y_base = np.full_like(x_fit, band.get('baseline_value', 0.0), dtype=np.float64)
                        else:
                            base_x = np.arange(len(baseline), dtype=np.float64)
                            y_base = np.interp(x_fit, base_x, baseline)

                        y_fit_profile = y_base + y_fit_corr
                        fit_label = 'Gaussian fit'
                        if band.get('fit_method') == 'single_gaussian_full_area':
                            fit_label = 'Gaussian fit (full area)'
                        ax.plot(x_fit, y_fit_profile, color='magenta', linestyle='--', linewidth=1.5, label=fit_label)

                if band.get('fit_method') == 'single_gaussian_full_area' and band.get('fit_params') is not None:
                    amp, mu, sigma = band.get('fit_params')
                    sigma_safe = max(float(sigma), 1e-6)
                    x_min = max(0.0, float(mu - 4.0 * sigma_safe))
                    x_max = min(float(len(profile) - 1), float(mu + 4.0 * sigma_safe))
                    ax.axvspan(x_min, x_max, alpha=0.08, color='magenta')

            ax.legend()
            
            # Span selector for band selection
            def onselect(xmin, xmax):
                if xmax - xmin < 5:
                    return
                
                start = int(min(xmin, xmax))
                end = int(max(xmin, xmax))

                # Optional two-step per-band baseline workflow
                if use_manual_baseline_var.get():
                    if selection_state['mode'] == 'band':
                        selection_state['pending_band'] = (start, end)
                        selection_state['mode'] = 'baseline'
                        status_label.config(text="Band selected. Now drag a flat baseline region for this band.", fg='purple')
                        ax.axvspan(start, end, alpha=0.2, color='orange')
                        canvas.draw()
                        return

                    pending = selection_state.get('pending_band')
                    if pending is None:
                        reset_selection_state()
                        status_label.config(text="State reset. Drag to select a band region.", fg='blue')
                        return

                    b_start, b_end = pending
                    baseline_region = (start, end)
                    finalize_band_for_lane(profile, lane_idx, b_start, b_end, baseline_region=baseline_region)
                    reset_selection_state()
                    status_label.config(text="Band saved with manual baseline region.", fg='green')
                    show_lane(lane_idx)
                    return

                finalize_band_for_lane(profile, lane_idx, start, end, baseline_region=None)
                status_label.config(text="Band saved.", fg='green')
                show_lane(lane_idx)
            
            self.interactive_span_selector = SpanSelector(
                ax,
                onselect,
                'horizontal',
                useblit=True,
                props=dict(alpha=0.5, facecolor='red')
            )
            
            canvas.draw()
        
        # Control buttons
        button_frame = tk.Frame(results_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Checkbutton(
            button_frame,
            text="Use manual baseline region (per band)",
            variable=use_manual_baseline_var
        ).pack(side=tk.LEFT, padx=5)

        tk.Checkbutton(
            button_frame,
            text="Use Gaussian fit (area only within selected region)",
            variable=use_peak_fit_var
        ).pack(side=tk.LEFT, padx=5)

        tk.Checkbutton(
            button_frame,
            text="Use Gaussian fit and integrate full fitted curve",
            variable=use_peak_fit_full_var
        ).pack(side=tk.LEFT, padx=5)

        def on_fit_checkbox_change(*_):
            # Keep fit mode explicit: region-only fit vs full-curve extrapolated fit.
            if use_peak_fit_full_var.get() and use_peak_fit_var.get():
                use_peak_fit_var.set(False)

        use_peak_fit_var.trace_add('write', on_fit_checkbox_change)
        use_peak_fit_full_var.trace_add('write', on_fit_checkbox_change)
        
        def next_lane():
            reset_selection_state()
            current_lane[0] += 1
            show_lane(current_lane[0])
        
        def prev_lane():
            if current_lane[0] > 0:
                reset_selection_state()
                current_lane[0] -= 1
                show_lane(current_lane[0])

        def clear_current_lane():
            lane_to_clear = current_lane[0] + 1
            selected_bands[:] = [b for b in selected_bands if b.get('lane') != lane_to_clear]
            reset_selection_state()
            status_label.config(text="Cleared selections for current lane.", fg='orange')
            show_lane(current_lane[0])

        def clear_all_lanes():
            selected_bands.clear()
            reset_selection_state()
            status_label.config(text="Cleared selections for all lanes.", fg='orange')
            show_lane(current_lane[0])
        
        tk.Button(button_frame, text="Previous Lane", command=prev_lane).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Next Lane", command=next_lane).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Clear Lane", command=clear_current_lane).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Clear All", command=clear_all_lanes).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Finish", command=lambda: results_window.destroy()).pack(side=tk.RIGHT, padx=5)
        
        # Show first lane
        show_lane(0)
    
    def estimate_band_width(self, profile, peak_idx, threshold=0.2):
        """Estimate band width from a clean peak"""
        baseline = self.calculate_baseline(profile, self.baseline_method.get(), lane_idx=None, bg_baselines=None)
        return qc.estimate_band_width(profile - baseline, peak_idx, threshold)
    
    def save_plot(self, fig):
        """Save the current plot"""
        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            messagebox.showinfo("Success", "Plot saved to {}".format(save_path))

    # ------------------------------------------------------------------
    # Background ROI / LOQ helpers
    # ------------------------------------------------------------------

    def clear_background_boxes(self):
        """Remove all background ROI boxes from the canvas"""
        self.background_boxes = []
        self.background_lane_map = []
        self.selected_background_idx = None
        self.selected_background_indices = set()
        self.update_display()

    def _load_raw_analysis_array(self, apply_invert=True):
        """Load raw image as a 2D float64 array for quant/LOQ computations."""
        if self.original_image is None:
            return None
        try:
            arr, _ = load_image(self.image_path, page=self.image_page, return_raw=True)
            arr = np.array(arr, dtype=np.float64)
        except Exception:
            arr = np.array(self.original_image.convert('L'), dtype=np.float64)

        if arr.ndim == 3:
            if arr.shape[2] in (3, 4):
                arr = np.mean(arr[..., :3], axis=2)
            else:
                arr = arr[0] if arr.shape[0] < 10 else np.mean(arr, axis=0)
        elif arr.ndim > 2:
            arr = arr[0]

        arr = np.array(arr, dtype=np.float64)
        if apply_invert and getattr(self, 'invert_image_var', None) and self.invert_image_var.get():
            arr = np.max(arr) - arr
        return arr

    def _compute_background_baselines(self, arr=None):
        """Compute robust (median) background baseline values from BG boxes."""
        if arr is None:
            arr = self._load_raw_analysis_array(apply_invert=True)
        if arr is None or len(self.background_boxes) == 0:
            return {'global': None, 'per_lane': {}}

        return qc.compute_background_baselines(
            arr,
            self.background_boxes,
            getattr(self, 'background_lane_map', None),
            len(getattr(self, 'lanes', []))
        )

    def _compute_loq_records(self, arr=None):
        """Return LOQ stats with global and per-lane values from background boxes."""
        if arr is None:
            arr = self._load_raw_analysis_array(apply_invert=True)
        if arr is None or len(self.background_boxes) == 0:
            return {'global': None, 'per_lane': {}}

        def calc_metrics(pixels, lane_idx=None):
            if pixels is None or len(pixels) < 4:
                return None
            mu = float(np.mean(pixels))
            med = float(np.median(pixels))
            sigma = float(np.std(pixels, ddof=1))
            # Intensity LOQ/LOD are median-centered to match median-based BG subtraction.
            lod_intensity = med + 3.3 * sigma
            loq_intensity = med + 10.0 * sigma

            loq_area_raw = None
            noise_area_raw = None
            if lane_idx is not None and 0 <= lane_idx < len(self.lanes):
                _, _, lane_w, lane_h = self.lanes[lane_idx]
                height_for_integration = self.reference_band_width if self.reference_band_width else lane_h
                sigma_profile = sigma / np.sqrt(max(1, lane_w))
                noise_area_raw = sigma_profile * np.sqrt(max(1, height_for_integration))
                loq_area_raw = 10.0 * noise_area_raw
            elif self.lane_size is not None:
                lane_w, lane_h = self.lane_size
                height_for_integration = self.reference_band_width if self.reference_band_width else lane_h
                sigma_profile = sigma / np.sqrt(max(1, lane_w))
                noise_area_raw = sigma_profile * np.sqrt(max(1, height_for_integration))
                loq_area_raw = 10.0 * noise_area_raw

            return {
                'n_pixels': int(len(pixels)),
                'mu': mu,
                'median': med,
                'sigma': sigma,
                'lod_intensity': lod_intensity,
                'loq_intensity': loq_intensity,
                'noise_area_raw': noise_area_raw,
                'loq_area_raw': loq_area_raw,
            }

        # Collect global pixels + lane-associated subsets
        all_segments = []
        lane_segments = {i: [] for i in range(len(self.lanes))}

        for idx, (x, y, w, h) in enumerate(self.background_boxes):
            y1 = max(0, int(y))
            y2 = min(arr.shape[0], int(y + h))
            x1 = max(0, int(x))
            x2 = min(arr.shape[1], int(x + w))
            if y2 <= y1 or x2 <= x1:
                continue

            pixels = arr[y1:y2, x1:x2].flatten()
            all_segments.append(pixels)

            lane_idx = self.background_lane_map[idx] if idx < len(self.background_lane_map) else None
            if lane_idx is not None and lane_idx in lane_segments:
                lane_segments[lane_idx].append(pixels)

        if len(all_segments) == 0:
            return {'global': None, 'per_lane': {}}

        global_pixels = np.concatenate(all_segments)
        global_record = calc_metrics(global_pixels, lane_idx=None)

        per_lane = {}
        for lane_idx, chunks in lane_segments.items():
            if len(chunks) == 0:
                continue
            per_lane_pixels = np.concatenate(chunks)
            lane_record = calc_metrics(per_lane_pixels, lane_idx=lane_idx)
            if lane_record is not None:
                per_lane[lane_idx] = lane_record

        return {'global': global_record, 'per_lane': per_lane}

    def _compute_empirical_loq_for_band(self, h_band, arr=None):
        """Empirical background-area LOQ for one band height.

        This mirrors the band workflow: collapse each BG box to 1D by width-mean,
        median-center, and integrate over windows of length h_band.
        
        Pools ALL background boxes to get a global empirical LOQ estimate,
        ensuring consistency across all lanes when using same band height.
        """
        if arr is None:
            arr = self._load_raw_analysis_array(apply_invert=True)
        if arr is None or len(self.background_boxes) == 0:
            return None

        h_band = max(1, int(h_band))

        all_boxes = []
        for idx, (x, y, w, h) in enumerate(self.background_boxes):
            y1 = max(0, int(y))
            y2 = min(arr.shape[0], int(y + h))
            x1 = max(0, int(x))
            x2 = min(arr.shape[1], int(x + w))
            if y2 <= y1 or x2 <= x1:
                continue

            box = (x1, y1, x2, y2)
            all_boxes.append(box)

        if len(all_boxes) == 0:
            return None

        def collect_area_samples(boxes):
            samples = []
            for x1, y1, x2, y2 in boxes:
                roi = arr[y1:y2, x1:x2]
                if roi.size == 0:
                    continue

                profile = np.mean(roi, axis=1)
                if len(profile) < h_band:
                    continue

                profile_corr = np.array(profile, dtype=np.float64) - float(np.median(profile))
                step = max(1, h_band // 4)

                if len(profile_corr) == h_band:
                    samples.append(float(np.trapz(profile_corr)))
                else:
                    for start in range(0, len(profile_corr) - h_band + 1, step):
                        segment = profile_corr[start:start + h_band]
                        samples.append(float(np.trapz(segment)))
            return samples

        # Pool all background boxes for global empirical LOQ estimate
        area_samples = collect_area_samples(all_boxes)

        if len(area_samples) == 0:
            return None

        mean_area = float(np.mean(area_samples))
        if len(area_samples) < 2:
            return {
                'n_samples': int(len(area_samples)),
                'mean_area': mean_area,
                'sd_area': None,
                'loq_area_empirical': None
            }

        sd_area = float(np.std(area_samples, ddof=1))
        loq_area_empirical = float(mean_area + 10.0 * sd_area)
        return {
            'n_samples': int(len(area_samples)),
            'mean_area': mean_area,
            'sd_area': sd_area,
            'loq_area_empirical': loq_area_empirical
        }

    def calculate_loq(self):
        """Calculate LOD / LOQ from user-drawn background ROI boxes.

        Methodology
        -----------
        All pixels from the selected background boxes are pooled.
          μ   = mean background intensity
          σ   = std dev of background intensity (ddof=1)
          LOD = μ + 3.3 σ    (minimum detectable signal, intensity units)
          LOQ = μ + 10 σ     (minimum reliably quantifiable, intensity units)

        Area-equivalent LOQ (same units as Area_raw in the exported CSV):
          Each row of a lane profile is the mean of W pixels, so
            σ_profile = σ / √W
          A band area integrates over H rows, so
            σ_area    = σ_profile × √H
          LOQ_area  = 10 × σ_area
        where W = lane width and H = band integration height (reference band
        width if set, otherwise the full lane height).
        """
        if self.original_image is None:
            messagebox.showwarning("LOQ", "Please load an image first.")
            return
        if len(self.background_boxes) == 0:
            messagebox.showwarning(
                "LOQ",
                "No background boxes defined.\n\n"
                "Switch the draw mode to 'Background' and drag one or more "
                "background regions on the image, then click Calc LOQ."
            )
            return

        arr = self._load_raw_analysis_array()
        if arr is None:
            messagebox.showwarning("LOQ", "Could not load image data for LOQ calculation.")
            return

        # Collect pixels from all background boxes
        bg_segments = []
        for x, y, w, h in self.background_boxes:
            y1 = max(0, int(y));  y2 = min(arr.shape[0], int(y + h))
            x1 = max(0, int(x));  x2 = min(arr.shape[1], int(x + w))
            if y2 > y1 and x2 > x1:
                bg_segments.append(arr[y1:y2, x1:x2].flatten())

        if not bg_segments or sum(len(s) for s in bg_segments) < 4:
            messagebox.showwarning("LOQ", "Background boxes have too few pixels for statistics.")
            return

        bg_pixels = np.concatenate(bg_segments)
        mu    = float(np.mean(bg_pixels))
        med   = float(np.median(bg_pixels))
        sigma = float(np.std(bg_pixels, ddof=1))
        n_pix = int(len(bg_pixels))

        # Median-centered to align with median-based baseline subtraction.
        lod_intensity = med + 3.3  * sigma
        loq_intensity = med + 10.0 * sigma

        # Area-equivalent LOQ
        loq_area  = None
        H_val     = None
        lane_w_val = None
        if self.lane_size is not None:
            lane_w_val, lane_h = self.lane_size
            H_val = self.reference_band_width if self.reference_band_width else lane_h
            sigma_profile = sigma / np.sqrt(max(1, lane_w_val))
            loq_area      = 10.0 * sigma_profile * np.sqrt(max(1, H_val))

        loq_area_str = "{:.4e}".format(loq_area) if loq_area is not None else "N/A  (no lane defined)"

        loq_area_display_str = "N/A"
        if loq_area is not None and len(self.band_data) > 0:
            raw_areas = [abs(b.get('area', 0.0)) for b in self.band_data
                         if b.get('area') not in (None, 0)]
            if raw_areas:
                display_scale = 1.0 / float(min(raw_areas))
                loq_area_display_str = "{:.4f} (×{:.0e})".format(
                    loq_area * display_scale, display_scale)

        # Bundle for the save-results closure
        results = dict(
            n_boxes=len(self.background_boxes),
            n_pixels=n_pix,
            mu=mu, median=med, sigma=sigma,
            lod_intensity=lod_intensity,
            loq_intensity=loq_intensity,
            loq_area_str=loq_area_str,
            loq_area_display_str=loq_area_display_str,
            lane_w=lane_w_val, H=H_val,
        )

        # ── Build results window ──────────────────────────────────────
        result_win = tk.Toplevel(self.root)
        result_win.title("LOQ Calculator Results")
        result_win.geometry("520x480")
        result_win.resizable(False, False)

        tk.Label(result_win, text="Limit of Quantification (LOQ)",
                 font=('Arial', 13, 'bold')).pack(pady=10)

        # Background statistics block
        stats_frame = tk.LabelFrame(result_win, text="Background Statistics",
                                    font=('Arial', 10, 'bold'))
        stats_frame.pack(fill=tk.X, padx=15, pady=5)
        for lbl, val in [
            ("N boxes:",              str(results['n_boxes'])),
            ("N pixels:",             str(n_pix)),
            ("Mean intensity (μ):",   "{:.4e}".format(mu)),
            ("Median intensity:",     "{:.4e}".format(med)),
            ("Std dev (σ):",          "{:.4e}".format(sigma)),
        ]:
            row_f = tk.Frame(stats_frame)
            row_f.pack(fill=tk.X, padx=10, pady=2)
            tk.Label(row_f, text=lbl,  font=('Arial', 9), width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row_f, text=val,  font=('Arial', 9, 'bold'), anchor='w').pack(side=tk.LEFT)

        # Intensity thresholds block
        thresh_frame = tk.LabelFrame(result_win, text="Thresholds — Intensity Units",
                                     font=('Arial', 10, 'bold'))
        thresh_frame.pack(fill=tk.X, padx=15, pady=5)
        for lbl, val, note in [
            ("LOD  (μ + 3.3 σ):", "{:.4e}".format(lod_intensity), "Minimum detectable signal"),
            ("LOQ  (μ + 10 σ):",  "{:.4e}".format(loq_intensity), "Minimum reliably quantifiable"),
        ]:
            row_f = tk.Frame(thresh_frame)
            row_f.pack(fill=tk.X, padx=10, pady=2)
            tk.Label(row_f, text=lbl,  font=('Arial', 9), width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row_f, text=val,  font=('Arial', 9, 'bold'), anchor='w').pack(side=tk.LEFT)
            tk.Label(row_f, text=note, font=('Arial', 7), fg='gray').pack(side=tk.LEFT, padx=6)

        # Area-equivalent block
        area_frame = tk.LabelFrame(
            result_win,
            text="Area-Equivalent LOQ  (same units as Area_raw in CSV)",
            font=('Arial', 10, 'bold'))
        area_frame.pack(fill=tk.X, padx=15, pady=5)
        for lbl, val in [
            ("LOQ_area (raw):",     loq_area_str),
            ("LOQ_area (display):", loq_area_display_str),
        ]:
            row_f = tk.Frame(area_frame)
            row_f.pack(fill=tk.X, padx=10, pady=2)
            tk.Label(row_f, text=lbl, font=('Arial', 9), width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row_f, text=val, font=('Arial', 9, 'bold'), anchor='w').pack(side=tk.LEFT)

        tk.Label(result_win,
                 text="LOQ_area = 10 × (σ / √W) × √H     "
                      "[W = lane width px,  H = band integration height px]",
                 font=('Arial', 7), fg='gray', justify=tk.CENTER).pack(pady=3)

        # Save / Close buttons
        def _save_loq_results():
            save_path = filedialog.asksaveasfilename(
                defaultextension='.txt',
                filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
                title='Save LOQ Results', parent=result_win
            )
            if not save_path:
                return
            with open(save_path, 'w') as f:
                f.write("WB_quantifier {} (git {})\n".format(__version__, get_git_commit()))
                f.write("LOQ Analysis Results\n")
                f.write("=" * 40 + "\n")
                f.write("Image:              {}\n".format(
                    os.path.basename(self.image_path) if self.image_path else ''))
                f.write("N background boxes: {}\n".format(results['n_boxes']))
                f.write("N pixels:           {}\n".format(results['n_pixels']))
                f.write("Mean intensity (μ): {:.6e}\n".format(results['mu']))
                f.write("Median intensity:   {:.6e}\n".format(results['median']))
                f.write("Std dev (σ):        {:.6e}\n".format(results['sigma']))
                f.write("\n--- Thresholds (intensity units) ---\n")
                f.write("LOD (median + 3.3σ): {:.6e}\n".format(results['lod_intensity']))
                f.write("LOQ (median + 10σ):  {:.6e}\n".format(results['loq_intensity']))
                f.write("\n--- Area-equivalent LOQ ---\n")
                if results['lane_w'] is not None:
                    f.write("Lane width W:       {} px\n".format(results['lane_w']))
                    f.write("Band height H:      {} px\n".format(results['H']))
                f.write("LOQ_area (raw):     {}\n".format(results['loq_area_str']))
                f.write("LOQ_area (display): {}\n".format(results['loq_area_display_str']))
            messagebox.showinfo("Saved", "LOQ results saved to\n{}".format(save_path),
                                parent=result_win)

        btn_frame = tk.Frame(result_win)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Save Results", command=_save_loq_results,
                  bg='dodgerblue', fg='white', font=('Arial', 9, 'bold'),
                  relief=tk.RAISED, bd=2, padx=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Close", command=result_win.destroy).pack(side=tk.LEFT, padx=5)

    def export_data(self):
        """Export quantification data to CSV"""
        if len(self.band_data) == 0:
            messagebox.showwarning("Warning", "No band data to export. Please analyze bands first.")
            return
        
        save_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if save_path:
            # Collect raw areas
            raw_areas = [b['area'] for b in self.band_data if 'area' in b]
            loq_records = self._compute_loq_records()
            raw_arr = self._load_raw_analysis_array(apply_invert=True)
            empirical_cache = {}

            # Determine display scale: normalize so minimum non-zero absolute area becomes 1
            nonzero = [abs(a) for a in raw_areas if a is not None and a != 0]
            if len(nonzero) == 0:
                scale = 1.0
            else:
                min_nonzero = float(min(nonzero))
                if min_nonzero <= 0:
                    scale = 1.0
                else:
                    scale = 1.0 / min_nonzero

            with open(save_path, 'w', newline='') as csvfile:
                # Write a header comment with scaling info
                csvfile.write('# display_scale={:.0e}\n'.format(scale))
                csvfile.write('# tool=WB_quantifier\n')
                csvfile.write('# tool_version={}\n'.format(__version__))
                csvfile.write('# git_commit={}\n'.format(get_git_commit()))
                csvfile.write('# export_utc={}\n'.format(datetime.now(timezone.utc).isoformat()))
                csvfile.write('# bands_are_bright={}\n'.format(
                    bool(getattr(self, 'bands_are_bright', None) and self.bands_are_bright.get())))
                csvfile.write('# invert_for_analysis={}\n'.format(
                    bool(getattr(self, 'invert_image_var', None) and self.invert_image_var.get())))
                csvfile.write('# peak_threshold={}\n'.format(
                    getattr(self, 'peak_threshold', None) and self.peak_threshold.get()))
                csvfile.write('# image_page={}\n'.format(getattr(self, 'image_page', '')))
                image_sha256 = ''
                try:
                    if self.image_path and os.path.isfile(self.image_path):
                        h = hashlib.sha256()
                        with open(self.image_path, 'rb') as _fh:
                            for _chunk in iter(lambda: _fh.read(1 << 20), b''):
                                h.update(_chunk)
                        image_sha256 = h.hexdigest()
                except Exception:
                    image_sha256 = ''
                csvfile.write('# image_sha256={}\n'.format(image_sha256))
                if loq_records.get('global') is not None:
                    csvfile.write('# loq_mode=lane_specific_with_global_fallback\n')
                csvfile.write('# LOQ_column=prefer_empirical_fallback_model\n')
                csvfile.write('# Area_corrected=baseline-subtracted integrated area used for quantification\n')
                csvfile.write('# Area_raw=integrated profile area over same interval without baseline subtraction\n')
                csvfile.write('# SNR_area_empirical=abs(Area_raw)/BG_Area_SD_empirical\n')
                csvfile.write('# empirical_loq_definition=mean(bg_area_samples)+10*sd(bg_area_samples)\n')
                csvfile.write('# bg_area_samples_definition=1D-collapse(mean across width), median-center, integrate windows of size Width\n')

                fieldnames = [
                    'Source_File', 'Lane', 'Band',
                    'Area_corrected', 'Area_display', 'Area_raw',
                    'LOQ', 'LOQ_model', 'LOQ_empirical',
                    'BG_Mean', 'BG_Median', 'BG_SD',
                    'BG_Area_mean_empirical', 'BG_Area_SD_empirical', 'BG_Area_N_empirical',
                    'SNR_area_empirical',
                    'Height', 'Width', 'Peak_Position', 'Start', 'End',
                    'Baseline_Method', 'Baseline_Value',
                    'Baseline_Region_Start', 'Baseline_Region_End',
                    'Integration_Method', 'Fit_Method', 'Fit_Area_Scope',
                    'Fit_Area', 'Fit_Amp', 'Fit_Mu', 'Fit_Sigma', 'Fit_Polarity',
                    'Lane_X', 'Lane_Y', 'Lane_W', 'Lane_H'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                # Group by lane
                lanes = {}
                for band in self.band_data:
                    lane_num = band['lane']
                    if lane_num not in lanes:
                        lanes[lane_num] = []
                    lanes[lane_num].append(band)

                # Write data
                for lane_num in sorted(lanes.keys()):
                    for band_idx, band in enumerate(lanes[lane_num], 1):
                        area_corrected = float(band.get('area', 0.0))
                        area_disp = area_corrected * scale
                        lane_idx = lane_num - 1
                        start_idx = max(0, int(band.get('start', 0)))
                        end_idx = max(start_idx + 1, int(band.get('end', start_idx + 1)))

                        # True uncorrected area over the same integration interval.
                        area_raw = None
                        if lane_idx < len(self.lane_profiles):
                            prof = self.lane_profiles[lane_idx]
                            end_idx = min(end_idx, len(prof))
                            if end_idx > start_idx:
                                area_raw = float(np.trapz(prof[start_idx:end_idx]))

                        if area_raw is None:
                            area_raw = area_corrected

                        loq_value = None
                        loq_model = None
                        lane_loq = loq_records.get('per_lane', {}).get(lane_idx)
                        global_loq = loq_records.get('global')
                        loq_record = None
                        if lane_loq is not None and lane_loq.get('loq_area_raw') is not None:
                            loq_record = lane_loq
                            loq_model = float(lane_loq['loq_area_raw'])
                        elif global_loq is not None and global_loq.get('loq_area_raw') is not None:
                            loq_record = global_loq
                            loq_model = float(global_loq['loq_area_raw'])

                        bg_mean = loq_record.get('mu') if loq_record is not None else None
                        bg_median = loq_record.get('median') if loq_record is not None else None
                        bg_sd = loq_record.get('sigma') if loq_record is not None else None

                        # Per-band model LOQ so H matches the actual integration window width.
                        if bg_sd not in (None, 0):
                            lane_w_for_noise = None
                            if 0 <= lane_idx < len(self.lanes):
                                lane_w_for_noise = int(self.lanes[lane_idx][2])
                            elif self.lane_size is not None:
                                lane_w_for_noise = int(self.lane_size[0])

                            if lane_w_for_noise is not None and lane_w_for_noise > 0:
                                h_band = max(1, int(band.get('width', 1)))
                                sigma_profile = float(bg_sd) / np.sqrt(max(1, lane_w_for_noise))
                                loq_model = 10.0 * sigma_profile * np.sqrt(max(1, h_band))

                        # Empirical LOQ from background area samples (same 1D-collapse + integration style as bands).
                        h_band = max(1, int(band.get('width', 1)))
                        empirical_key = h_band  # Global cache per band height, not per lane
                        if empirical_key not in empirical_cache:
                            empirical_cache[empirical_key] = self._compute_empirical_loq_for_band(
                                h_band, arr=raw_arr
                            )
                        empirical = empirical_cache.get(empirical_key)

                        emp_mean = empirical.get('mean_area') if empirical is not None else None
                        emp_sd = empirical.get('sd_area') if empirical is not None else None
                        emp_n = empirical.get('n_samples') if empirical is not None else None
                        loq_empirical = empirical.get('loq_area_empirical') if empirical is not None else None

                        # Main LOQ column prefers empirical if available, else model.
                        loq_value = loq_empirical if loq_empirical is not None else loq_model

                        snr_area_empirical = None
                        if emp_sd not in (None, 0):
                            snr_area_empirical = abs(float(area_raw)) / float(emp_sd)

                        # scale so minimum non-zero area == 1
                        area_disp = area_disp
                        writer.writerow({
                            'Source_File': os.path.basename(self.image_path) if self.image_path else '',
                            'Lane': lane_num,
                            'Band': band_idx,
                            'Area_corrected': '{:.12e}'.format(area_corrected),
                            'Area_display': '{:.6f}'.format(area_disp),
                            'Area_raw': '{:.12e}'.format(area_raw),
                            'LOQ': '{:.12e}'.format(loq_value) if loq_value is not None else '',
                            'LOQ_model': '{:.12e}'.format(loq_model) if loq_model is not None else '',
                            'LOQ_empirical': '{:.12e}'.format(loq_empirical) if loq_empirical is not None else '',
                            'BG_Mean': '{:.12e}'.format(bg_mean) if bg_mean is not None else '',
                            'BG_Median': '{:.12e}'.format(bg_median) if bg_median is not None else '',
                            'BG_SD': '{:.12e}'.format(bg_sd) if bg_sd is not None else '',
                            'BG_Area_mean_empirical': '{:.12e}'.format(emp_mean) if emp_mean is not None else '',
                            'BG_Area_SD_empirical': '{:.12e}'.format(emp_sd) if emp_sd is not None else '',
                            'BG_Area_N_empirical': emp_n if emp_n is not None else '',
                            'SNR_area_empirical': '{:.6f}'.format(snr_area_empirical) if snr_area_empirical is not None else '',
                            'Height': '{:.6g}'.format(band.get('height', 0.0)),
                            'Width': band.get('width', 0),
                            'Peak_Position': band.get('peak_position', 0),
                            'Start': band.get('start', 0),
                            'End': band.get('end', 0),
                            'Baseline_Method': band.get('baseline_source', '') or '',
                            'Baseline_Value': ('{:.12e}'.format(band['baseline_value'])
                                               if band.get('baseline_value') is not None else ''),
                            'Baseline_Region_Start': (int(band['baseline_region'][0])
                                                      if band.get('baseline_region') is not None else ''),
                            'Baseline_Region_End': (int(band['baseline_region'][1])
                                                    if band.get('baseline_region') is not None else ''),
                            'Integration_Method': band.get('integration_method', '') or '',
                            'Fit_Method': band.get('fit_method', '') or '',
                            'Fit_Area_Scope': band.get('fit_area_scope', '') or '',
                            'Fit_Area': ('{:.12e}'.format(band['fit_area'])
                                         if band.get('fit_area') is not None else ''),
                            'Fit_Amp': ('{:.12e}'.format(band['fit_params'][0])
                                        if band.get('fit_params') is not None else ''),
                            'Fit_Mu': ('{:.12e}'.format(band['fit_params'][1])
                                       if band.get('fit_params') is not None else ''),
                            'Fit_Sigma': ('{:.12e}'.format(band['fit_params'][2])
                                          if band.get('fit_params') is not None else ''),
                            'Fit_Polarity': ('{:.6g}'.format(band['fit_polarity'])
                                             if band.get('fit_polarity') is not None else ''),
                            'Lane_X': int(self.lanes[lane_idx][0]) if 0 <= lane_idx < len(getattr(self, 'lanes', [])) else '',
                            'Lane_Y': int(self.lanes[lane_idx][1]) if 0 <= lane_idx < len(getattr(self, 'lanes', [])) else '',
                            'Lane_W': int(self.lanes[lane_idx][2]) if 0 <= lane_idx < len(getattr(self, 'lanes', [])) else '',
                            'Lane_H': int(self.lanes[lane_idx][3]) if 0 <= lane_idx < len(getattr(self, 'lanes', [])) else ''
                        })

            messagebox.showinfo("Success", f"Data exported to {save_path}\n(display_scale={scale:.0e})")
    
    def show_summary(self):
        """Show summary statistics"""
        if len(self.band_data) == 0:
            messagebox.showwarning("Warning", "No band data available.")
            return
        
        # Create summary window
        summary_window = tk.Toplevel(self.root)
        summary_window.title("Quantification Summary")
        summary_window.geometry("600x400")
        
        # Create treeview
        tree_frame = tk.Frame(summary_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scrollbar
        scrollbar = tk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview
        columns = ('Lane', 'Band', 'Area', 'Height', 'Width')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=scrollbar.set)
        scrollbar.config(command=tree.yview)
        
        # Define headings
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        
        # Insert data
        lanes = {}
        for band in self.band_data:
            lane_num = band['lane']
            if lane_num not in lanes:
                lanes[lane_num] = []
            lanes[lane_num].append(band)
        
        # compute display normalization so minimum non-zero area == 1
        all_areas = [abs(b.get('area', 0.0)) for b in self.band_data if b.get('area', None) not in (None, 0)]
        if len(all_areas) == 0:
            summary_scale = 1.0
        else:
            summary_scale = 1.0 / float(min(all_areas))

        for lane_num in sorted(lanes.keys()):
            for band_idx, band in enumerate(lanes[lane_num], 1):
                area_val = band.get('area', 0.0)
                disp = area_val * summary_scale
                tree.insert('', tk.END, values=(
                    lane_num,
                    band_idx,
                    '{:.2f}'.format(disp),
                    '{:.2f}'.format(band.get('height', 0.0)),
                    band['width']
                ))
        
        tree.pack(fill=tk.BOTH, expand=True)
        
        # Add export button
        tk.Button(summary_window, text="Export to CSV", command=self.export_data).pack(pady=5)


def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = WesternBlotQuantifier(root)
    root.mainloop()


if __name__ == "__main__":
    main()
