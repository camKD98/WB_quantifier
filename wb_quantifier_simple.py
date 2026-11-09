"""
Western Blot Lane Quantification Tool (Simplified - No OpenCV)

This script provides an interactive interface for selecting lanes in Western blot images
and generating intensity profiles similar to ImageJ.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
from image_utils import load_image, export_png


class WesternBlotQuantifier:
    """Main class for Western blot quantification"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Western Blot Quantifier")
        
        # Image variables
        self.original_image = None
        self.display_image = None
        self.image_path = None
        self.image_page = 0
        self.photo = None

        # Display parameters (non-destructive)
        self.p_low = 0.5
        self.p_high = 99.5
        self.gamma = 1.0
        self.apply_display_to_quant = False  # default: quant uses raw data
            
        # Lane selection variables
        self.lanes = []  # List of lane rectangles (x, y, width, height)
        self.lane_size = None  # (width, height) set by first lane
        self.current_rect = None  # Current rectangle being drawn
        self.rect_start = None
        self.drawing = False
        self.selected_lane_idx = None  # Currently selected lane for moving
        
        # Canvas variables
        self.canvas = None
        self.canvas_width = 800
        self.canvas_height = 600
        
        # Setup GUI
        self.setup_gui()
        
    def setup_gui(self):
        """Initialize GUI components"""
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load Image", command=self.load_image)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Main frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Image canvas
        left_frame = tk.Frame(main_frame)
        """
        Simplified and working Western blot quantifier GUI used for testing.

        This is a compact, corrected implementation that uses the tifffile-first
        loader in image_utils. It keeps display scaling separate from raw data used
        for quantification and includes an Export PNG dialog.
        """

        import numpy as np
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import tkinter as tk
        from tkinter import filedialog, messagebox
        from PIL import Image, ImageTk, ImageDraw
        from image_utils import load_image, export_png


        class WesternBlotQuantifier:
            def __init__(self, root):
                self.root = root
                self.root.title("Western Blot Quantifier")

                # Image state
                self.original_image = None
                self.image_path = None
                self.image_page = 0

                # Display params (non-destructive)
                self.p_low = 0.5
                self.p_high = 99.5
                self.gamma = 1.0

                # Lanes
                self.lanes = []
                self.lane_size = None
                self.current_rect = None
                self.rect_start = None
                self.drawing = False
                self.selected_lane_idx = None

                # Canvas
                self.canvas = None
                self.canvas_width = 800
                self.canvas_height = 600

                self.setup_gui()

            def setup_gui(self):
                menubar = tk.Menu(self.root)
                self.root.config(menu=menubar)
                file_menu = tk.Menu(menubar, tearoff=0)
                menubar.add_cascade(label='File', menu=file_menu)
                file_menu.add_command(label='Load Image', command=self.load_image)
                file_menu.add_command(label='Export PNG', command=self.export_png_dialog)
                file_menu.add_separator()
                file_menu.add_command(label='Exit', command=self.root.quit)

                main_frame = tk.Frame(self.root)
                main_frame.pack(fill=tk.BOTH, expand=True)

                left_frame = tk.Frame(main_frame)
                left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                self.canvas = tk.Canvas(left_frame, width=self.canvas_width, height=self.canvas_height, bg='gray')
                self.canvas.pack(padx=10, pady=10)
                self.canvas.bind('<ButtonPress-1>', self.on_mouse_down)
                self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
                self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)

                control_frame = tk.Frame(left_frame)
                control_frame.pack(fill=tk.X, padx=10, pady=5)
                tk.Button(control_frame, text='Load Image', command=self.load_image).pack(side=tk.LEFT, padx=5)
                tk.Button(control_frame, text='Export PNG...', command=self.export_png_dialog).pack(side=tk.LEFT, padx=5)
                tk.Button(control_frame, text='Clear Lanes', command=self.clear_lanes).pack(side=tk.LEFT, padx=5)
                tk.Button(control_frame, text='Generate Profiles', command=self.generate_profiles).pack(side=tk.LEFT, padx=5)

                right_frame = tk.Frame(main_frame, width=200)
                right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=10)
                tk.Label(right_frame, text='Lanes:', font=('Arial', 12, 'bold')).pack(pady=5)
                self.lane_listbox = tk.Listbox(right_frame, height=20)
                self.lane_listbox.pack(fill=tk.BOTH, expand=True)
                self.lane_listbox.bind('<<ListboxSelect>>', self.on_lane_select)

            def load_image(self):
                path = filedialog.askopenfilename(title='Select image', filetypes=[('TIFF', '*.tif *.tiff'), ('Images', '*.png;*.jpg;*.jpeg'), ('All', '*.*')])
                if not path:
                    return
                self.image_path = path
                try:
                    img, meta = load_image(path, page=None, p_low=self.p_low, p_high=self.p_high, gamma=self.gamma)
                    if meta.get('n_pages', 1) > 1:
                        page = tk.simpledialog.askinteger('Multi-page TIFF', 'Select page (0-{}):'.format(meta['n_pages']-1), minvalue=0, maxvalue=meta['n_pages']-1, initialvalue=0)
                        if page is None:
                            return
                        self.image_page = page
                        img, meta = load_image(path, page=page, p_low=self.p_low, p_high=self.p_high, gamma=self.gamma)
                    else:
                        self.image_page = 0
                    self.original_image = img
                    self.clear_lanes()
                    self.update_display()
                except Exception as e:
                    messagebox.showerror('Error', f'Failed to load image: {e}')

            def update_display(self):
                if self.original_image is None:
                    self.canvas.delete('all')
                    return
                display_img = self.original_image.copy()
                draw = ImageDraw.Draw(display_img)
                for idx, (x, y, w, h) in enumerate(self.lanes):
                    color = (0, 255, 0) if idx == self.selected_lane_idx else (255, 255, 0)
                    for i in range(2):
                        draw.rectangle([x-i, y-i, x+w+i, y+h+i], outline=color)
                    draw.text((x, max(0, y-12)), f'L{idx+1}', fill=color)

                if self.current_rect is not None:
                    x, y, w, h = self.current_rect
                    draw.rectangle([x, y, x+w, y+h], outline=(0, 255, 255))

                img_w, img_h = display_img.size
                scale = min(self.canvas_width / img_w, self.canvas_height / img_h)
                self.display_scale = scale
                new_w, new_h = int(img_w*scale), int(img_h*scale)
                resized = display_img.resize((new_w, new_h), Image.LANCZOS)
                self.photo = ImageTk.PhotoImage(resized)
                self.canvas.config(width=new_w, height=new_h)
                self.canvas.delete('all')
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

            def canvas_to_image_coords(self, cx, cy):
                if not hasattr(self, 'display_scale'):
                    return cx, cy
                return int(cx/self.display_scale), int(cy/self.display_scale)

            def on_mouse_down(self, event):
                if self.original_image is None:
                    return
                ix, iy = self.canvas_to_image_coords(event.x, event.y)
                for idx, (x, y, w, h) in enumerate(self.lanes):
                    if x <= ix <= x+w and y <= iy <= y+h:
                        self.selected_lane_idx = idx
                        self.lane_listbox.selection_clear(0, tk.END)
                        self.lane_listbox.selection_set(idx)
                        self.update_display()
                        return
                self.drawing = True
                self.rect_start = (ix, iy)
                self.current_rect = None

            def on_mouse_drag(self, event):
                if not self.drawing or self.rect_start is None:
                    return
                ix, iy = self.canvas_to_image_coords(event.x, event.y)
                sx, sy = self.rect_start
                if self.lane_size is None:
                    x, y = min(sx, ix), min(sy, iy)
                    w, h = abs(ix-sx), abs(iy-sy)
                else:
                    w, h = self.lane_size
                    x, y = ix - w//2, iy - h//2
                self.current_rect = (x, y, w, h)
                self.update_display()

            def on_mouse_up(self, event):
                if not self.drawing:
                    return
                self.drawing = False
                if not self.current_rect:
                    return
                x, y, w, h = self.current_rect
                if w < 5 or h < 5:
                    self.current_rect = None
                    self.update_display()
                    return
                if self.lane_size is None:
                    self.lane_size = (w, h)
                self.lanes.append((x, y, w, h))
                self.current_rect = None
                self.update_lane_list()
                self.update_display()

            def update_lane_list(self):
                self.lane_listbox.delete(0, tk.END)
                for i in range(len(self.lanes)):
                    self.lane_listbox.insert(tk.END, f'Lane {i+1}')

            def on_lane_select(self, event):
                sel = self.lane_listbox.curselection()
                if sel:
                    self.selected_lane_idx = sel[0]
                    self.update_display()

            def clear_lanes(self):
                self.lanes = []
                self.lane_size = None
                self.selected_lane_idx = None
                self.update_lane_list()
                self.update_display()

            def generate_profiles(self):
                if not self.lanes:
                    messagebox.showwarning('Warning', 'No lanes defined')
                    return
                # Load raw array for quantification
                try:
                    arr, meta = load_image(self.image_path, page=self.image_page, return_raw=True)
                except Exception:
                    gray = np.array(self.original_image.convert('L'))
                else:
                    if arr.ndim == 3 and arr.shape[2] in (3,4):
                        gray = np.mean(arr[..., :3], axis=2).astype(arr.dtype)
                    elif arr.ndim == 2:
                        gray = arr
                    else:
                        gray = np.mean(arr, axis=0)

                n = len(self.lanes)
                fig, axes = plt.subplots(n, 1, figsize=(8, 2*n))
                if n == 1:
                    axes = [axes]
                for i, (x, y, w, h) in enumerate(self.lanes):
                    roi = gray[y:y+h, x:x+w]
                    profile = np.mean(roi, axis=1)
                    axes[i].plot(profile)
                    axes[i].invert_yaxis()
                    axes[i].set_title(f'Lane {i+1}')
                plt.tight_layout()
                win = tk.Toplevel(self.root)
                canvas = FigureCanvasTkAgg(fig, master=win)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            def export_png_dialog(self):
                if not self.image_path:
                    messagebox.showwarning('Warning', 'Load an image first')
                    return
                out = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG','*.png')])
                if not out:
                    return
                try:
                    export_png(self.image_path, out, page=self.image_page, bitdepth=8, p_low=self.p_low, p_high=self.p_high, gamma=self.gamma)
                    messagebox.showinfo('Exported', f'Wrote {out}')
                except Exception as e:
                    messagebox.showerror('Error', f'Export failed: {e}')


        def main():
            root = tk.Tk()
            app = WesternBlotQuantifier(root)
            root.mainloop()


        if __name__ == '__main__':
            main()
