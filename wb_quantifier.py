"""
Western Blot Lane Quantification Tool

This script provides an interactive interface for selecting lanes in Western blot images
and generating intensity profiles similar to ImageJ.
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk


class WesternBlotQuantifier:
    """Main class for Western blot quantification"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Western Blot Quantifier")
        
        # Image variables
        self.original_image = None
        self.display_image = None
        self.image_path = None
        self.photo = None
        
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
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas for image display
        self.canvas = tk.Canvas(left_frame, width=self.canvas_width, height=self.canvas_height, bg='gray')
        self.canvas.pack(padx=10, pady=10)
        
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
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(control_frame, text="Load Image", command=self.load_image).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="Clear Lanes", command=self.clear_lanes).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="Generate Profiles", command=self.generate_profiles).pack(side=tk.LEFT, padx=5)
        
        # Instructions
        instructions = """
Instructions:
1. Load a Western blot image
2. Draw the first lane rectangle (sets size for all lanes)
3. Click and drag to position additional lanes of the same size
4. Use arrow keys to fine-tune lane position (click on a lane first)
5. Press Delete/Backspace to remove selected lane
6. Click 'Generate Profiles' to view intensity graphs
        """
        inst_label = tk.Label(left_frame, text=instructions, justify=tk.LEFT, font=('Arial', 9))
        inst_label.pack(padx=10, pady=5)
        
        # Right panel - Lane list
        right_frame = tk.Frame(main_frame, width=200)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=10)
        
        tk.Label(right_frame, text="Lanes:", font=('Arial', 12, 'bold')).pack(pady=5)
        
        self.lane_listbox = tk.Listbox(right_frame, height=20)
        self.lane_listbox.pack(fill=tk.BOTH, expand=True)
        self.lane_listbox.bind('<<ListboxSelect>>', self.on_lane_select)
        
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
            self.original_image = cv2.imread(file_path)
            
            if self.original_image is None:
                messagebox.showerror("Error", "Failed to load image")
                return
            
            # Convert BGR to RGB for display
            self.original_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)
            
            # Clear previous lanes
            self.clear_lanes()
            
            # Display image
            self.update_display()
            
    def update_display(self):
        """Update the canvas with current image and lanes"""
        if self.original_image is None:
            return
        
        # Create a copy for display
        display_img = self.original_image.copy()
        
        # Draw existing lanes
        for idx, (x, y, w, h) in enumerate(self.lanes):
            color = (0, 255, 0) if idx == self.selected_lane_idx else (255, 255, 0)
            thickness = 3 if idx == self.selected_lane_idx else 2
            cv2.rectangle(display_img, (x, y), (x + w, y + h), color, thickness)
            cv2.putText(display_img, "L{}".format(idx+1), (x, y-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Draw current rectangle being created
        if self.current_rect is not None:
            x, y, w, h = self.current_rect
            cv2.rectangle(display_img, (x, y), (x + w, y + h), (0, 255, 255), 2)
        
        # Resize image to fit canvas while maintaining aspect ratio
        h, w = display_img.shape[:2]
        scale = min(self.canvas_width / w, self.canvas_height / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        self.display_scale = scale
        resized = cv2.resize(display_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Convert to PhotoImage
        img_pil = Image.fromarray(resized)
        self.photo = ImageTk.PhotoImage(img_pil)
        
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
    
    def on_mouse_down(self, event):
        """Handle mouse button press"""
        if self.original_image is None:
            return
        
        img_x, img_y = self.canvas_to_image_coords(event.x, event.y)
        
        # Check if clicking on existing lane
        for idx, (x, y, w, h) in enumerate(self.lanes):
            if x <= img_x <= x + w and y <= img_y <= y + h:
                self.selected_lane_idx = idx
                self.lane_listbox.selection_clear(0, tk.END)
                self.lane_listbox.selection_set(idx)
                self.update_display()
                return
        
        # Start drawing new rectangle
        self.drawing = True
        self.rect_start = (img_x, img_y)
        self.selected_lane_idx = None
        
    def on_mouse_drag(self, event):
        """Handle mouse drag"""
        if not self.drawing or self.rect_start is None:
            return
        
        img_x, img_y = self.canvas_to_image_coords(event.x, event.y)
        start_x, start_y = self.rect_start
        
        if self.lane_size is None:
            # First lane - user defines size
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
        
        # Add lane
        if self.lane_size is None:
            # First lane sets the size
            self.lane_size = (w, h)
        
        self.lanes.append((x, y, w, h))
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
        if self.selected_lane_idx is None or self.selected_lane_idx >= len(self.lanes):
            return
        
        x, y, w, h = self.lanes[self.selected_lane_idx]
        
        # Ensure lane stays within image bounds
        img_h, img_w = self.original_image.shape[:2]
        new_x = max(0, min(img_w - w, x + dx))
        new_y = max(0, min(img_h - h, y + dy))
        
        self.lanes[self.selected_lane_idx] = (new_x, new_y, w, h)
        self.update_display()
    
    def delete_selected_lane(self, event):
        """Delete the selected lane"""
        if self.selected_lane_idx is None or self.selected_lane_idx >= len(self.lanes):
            return
        
        del self.lanes[self.selected_lane_idx]
        
        # If all lanes deleted, reset lane size
        if len(self.lanes) == 0:
            self.lane_size = None
        
        self.selected_lane_idx = None
        self.update_lane_list()
        self.update_display()
    
    def clear_lanes(self):
        """Clear all lanes"""
        self.lanes = []
        self.lane_size = None
        self.selected_lane_idx = None
        self.update_lane_list()
        self.update_display()
    
    def generate_profiles(self):
        """Generate intensity profiles for all lanes"""
        if len(self.lanes) == 0:
            messagebox.showwarning("Warning", "No lanes defined. Please select lanes first.")
            return
        
        # Create a new window for profiles
        profile_window = tk.Toplevel(self.root)
        profile_window.title("Lane Intensity Profiles")
        
        # Create matplotlib figure
        n_lanes = len(self.lanes)
        fig, axes = plt.subplots(n_lanes, 1, figsize=(10, 2*n_lanes))
        
        if n_lanes == 1:
            axes = [axes]
        
        # Convert to grayscale if needed
        if len(self.original_image.shape) == 3:
            gray_image = cv2.cvtColor(self.original_image, cv2.COLOR_RGB2GRAY)
        else:
            gray_image = self.original_image
        
        # Generate profile for each lane
        for idx, (x, y, w, h) in enumerate(self.lanes):
            # Extract lane region
            lane_roi = gray_image[y:y+h, x:x+w]
            
            # Calculate intensity profile (average across width)
            profile = np.mean(lane_roi, axis=1)
            
            # Plot
            axes[idx].plot(profile, linewidth=2)
            axes[idx].set_title('Lane {}'.format(idx+1), fontweight='bold')
            axes[idx].set_xlabel('Position (pixels)')
            axes[idx].set_ylabel('Intensity')
            axes[idx].grid(True, alpha=0.3)
            axes[idx].set_xlim(0, len(profile))
            
            # Invert y-axis to match ImageJ convention (higher peaks for darker bands)
            axes[idx].invert_yaxis()
        
        plt.tight_layout()
        
        # Embed in tkinter window
        canvas = FigureCanvasTkAgg(fig, master=profile_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Add save button
        def save_profiles():
            save_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            if save_path:
                fig.savefig(save_path, dpi=300, bbox_inches='tight')
                messagebox.showinfo("Success", "Profiles saved to {}".format(save_path))
        
        button_frame = tk.Frame(profile_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(button_frame, text="Save Profiles", command=save_profiles).pack(side=tk.LEFT, padx=5)


def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = WesternBlotQuantifier(root)
    root.mainloop()


if __name__ == "__main__":
    main()
