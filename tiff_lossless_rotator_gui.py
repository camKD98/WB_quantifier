"""
Standalone Lossless TIFF Rotator/Flipper GUI.

This tool performs pixel-exact, non-interpolating transforms:
- Rotate 90 CW
- Rotate 90 CCW
- Rotate 180
- Flip Horizontal
- Flip Vertical

Notes:
- These operations are lossless with respect to pixel values.
- Arbitrary-angle rotations are intentionally not supported.
- Multi-page TIFFs are supported.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np

try:
    import tifffile
except ImportError as exc:
    raise SystemExit(
        "tifffile is required for this tool. Install with: pip install tifffile"
    ) from exc


OPERATIONS = [
    "Rotate 90 CW",
    "Rotate 90 CCW",
    "Rotate 180",
    "Flip Horizontal",
    "Flip Vertical",
]


class LosslessTiffTransformGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Lossless TIFF Rotator/Flipper")
        self.root.geometry("700x360")
        self.root.minsize(680, 330)

        self.input_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        self.operation_var = tk.StringVar(value=OPERATIONS[0])
        self.all_pages_var = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        container = tk.Frame(self.root, padx=12, pady=12)
        container.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(
            container,
            text="Lossless TIFF Rotator/Flipper",
            font=("Arial", 14, "bold"),
        )
        title.pack(anchor=tk.W, pady=(0, 10))

        input_frame = tk.LabelFrame(container, text="Input", padx=8, pady=8)
        input_frame.pack(fill=tk.X, pady=6)

        tk.Entry(input_frame, textvariable=self.input_path_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
        )
        tk.Button(input_frame, text="Browse", command=self.browse_input, width=10).pack(
            side=tk.RIGHT
        )

        op_frame = tk.LabelFrame(container, text="Transform", padx=8, pady=8)
        op_frame.pack(fill=tk.X, pady=6)

        tk.Label(op_frame, text="Operation:").pack(side=tk.LEFT)
        op_menu = ttk.Combobox(
            op_frame,
            textvariable=self.operation_var,
            values=OPERATIONS,
            state="readonly",
            width=22,
        )
        op_menu.pack(side=tk.LEFT, padx=(8, 16))

        tk.Checkbutton(
            op_frame,
            text="Apply to all pages",
            variable=self.all_pages_var,
        ).pack(side=tk.LEFT)

        output_frame = tk.LabelFrame(container, text="Output", padx=8, pady=8)
        output_frame.pack(fill=tk.X, pady=6)

        tk.Entry(output_frame, textvariable=self.output_path_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
        )
        tk.Button(output_frame, text="Save As", command=self.browse_output, width=10).pack(
            side=tk.RIGHT
        )

        btn_frame = tk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=(8, 6))

        tk.Button(
            btn_frame,
            text="Run Transform",
            command=self.run_transform,
            bg="dodgerblue",
            fg="white",
            activebackground="darkblue",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            highlightthickness=0,
            width=16,
        ).pack(side=tk.LEFT)

        tk.Button(btn_frame, text="Quit", command=self.root.destroy, width=10).pack(
            side=tk.RIGHT
        )

        notes = (
            "Lossless means pixel values are preserved exactly (no interpolation).\n"
            "Supported operations are limited to 90/180-degree rotations and flips."
        )
        tk.Label(container, text=notes, justify=tk.LEFT, fg="gray30").pack(
            anchor=tk.W, pady=(8, 0)
        )

    def browse_input(self):
        path = filedialog.askopenfilename(
            title="Select TIFF file",
            filetypes=[("TIFF files", "*.tif *.tiff"), ("All files", "*.*")],
        )
        if not path:
            return

        self.input_path_var.set(path)
        if not self.output_path_var.get():
            self.output_path_var.set(self._default_output_path(path, self.operation_var.get()))

    def browse_output(self):
        default_name = ""
        input_path = self.input_path_var.get().strip()
        if input_path:
            default_name = os.path.basename(
                self._default_output_path(input_path, self.operation_var.get())
            )

        path = filedialog.asksaveasfilename(
            title="Save transformed TIFF as",
            defaultextension=".tif",
            initialfile=default_name,
            filetypes=[("TIFF files", "*.tif *.tiff"), ("All files", "*.*")],
        )
        if path:
            self.output_path_var.set(path)

    def _default_output_path(self, input_path, operation):
        base, ext = os.path.splitext(input_path)
        safe = operation.lower().replace(" ", "_")
        return f"{base}_{safe}{ext or '.tif'}"

    def _spatial_axes(self, arr):
        """Infer spatial axes for pixel-preserving rotate/flip."""
        if arr.ndim < 2:
            raise ValueError("Array must be at least 2D")

        # HxW or HxWxC
        if arr.ndim == 2 or (arr.ndim >= 3 and arr.shape[-1] in (3, 4)):
            return (0, 1)

        # CxHxW heuristic
        if arr.ndim >= 3 and arr.shape[0] in (3, 4) and arr.shape[1] > 16 and arr.shape[2] > 16:
            return (1, 2)

        # Fallback to first two axes
        return (0, 1)

    def _apply_operation(self, arr, operation):
        axes = self._spatial_axes(arr)

        if operation == "Rotate 90 CW":
            return np.rot90(arr, k=-1, axes=axes)
        if operation == "Rotate 90 CCW":
            return np.rot90(arr, k=1, axes=axes)
        if operation == "Rotate 180":
            return np.rot90(arr, k=2, axes=axes)
        if operation == "Flip Horizontal":
            return np.flip(arr, axis=axes[1])
        if operation == "Flip Vertical":
            return np.flip(arr, axis=axes[0])

        raise ValueError(f"Unsupported operation: {operation}")

    def run_transform(self):
        input_path = self.input_path_var.get().strip()
        output_path = self.output_path_var.get().strip()
        operation = self.operation_var.get()
        use_all_pages = self.all_pages_var.get()

        if not input_path:
            messagebox.showwarning("Missing input", "Please choose an input TIFF file.")
            return
        if not os.path.isfile(input_path):
            messagebox.showerror("Invalid input", "Input file does not exist.")
            return
        if not output_path:
            output_path = self._default_output_path(input_path, operation)
            self.output_path_var.set(output_path)

        try:
            with tifffile.TiffFile(input_path) as tf:
                n_pages = len(tf.pages)
                page_indices = list(range(n_pages)) if use_all_pages else [0]

                transformed_pages = []
                for idx in page_indices:
                    page_arr = tf.pages[idx].asarray()
                    transformed = self._apply_operation(page_arr, operation)
                    transformed_pages.append(transformed)

                # Write as TIFF pages. Compression is lossless (zlib) for compact output.
                with tifffile.TiffWriter(output_path, bigtiff=(len(transformed_pages) > 1)) as tw:
                    for arr in transformed_pages:
                        tw.write(arr, compression="zlib")

            page_msg = "all pages" if use_all_pages else "first page only"
            messagebox.showinfo(
                "Success",
                f"Transform complete ({page_msg}).\nSaved to:\n{output_path}",
            )
        except Exception as exc:
            messagebox.showerror("Transform failed", str(exc))


def main():
    root = tk.Tk()
    LosslessTiffTransformGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
