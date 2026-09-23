import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import subprocess
import os
import threading
import re
import json

class VideoClipperGUI:
    DEFAULT_OUTPUT_NAME = "output.mp4"

    def __init__(self, root):
        self.root = root
        self.previous_output_path = None
        self.previous_output_input_path = None
        self.root.title("Video Clipper Pro")
        self.root.geometry("750x800")
        self.root.configure(bg="#1e1e1e")
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Configure styles for a "premium" look
        self.style.configure("TLabel", background="#1e1e1e", foreground="#ffffff", font=("Segoe UI", 10))
        self.style.configure("TEntry", fieldbackground="#333333", foreground="#ffffff")
        self.style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=5)
        self.style.configure("Run.TButton", background="#007acc", foreground="#ffffff")
        self.style.map("Run.TButton", background=[("active", "#005a9e")])
        
        # Main Container
        self.main_frame = ttk.Frame(root, padding="20", style="TFrame")
        self.style.configure("TFrame", background="#1e1e1e")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        self.header = tk.Label(self.main_frame, text="Video Clipper Pro", font=("Segoe UI", 20, "bold"), 
                              bg="#1e1e1e", fg="#007acc")
        self.header.grid(row=0, column=0, columnspan=3, pady=(0, 20), sticky="w")
        
        # Input Path
        ttk.Label(self.main_frame, text="Input Video File:").grid(row=1, column=0, sticky="w", pady=5)
        self.input_path_var = tk.StringVar()
        self.input_entry = ttk.Entry(self.main_frame, textvariable=self.input_path_var)
        self.input_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.browse_btn = ttk.Button(self.main_frame, text="Browse", command=self.browse_file)
        self.browse_btn.grid(row=1, column=2, padx=5, pady=5)
        
        # Start Time
        ttk.Label(self.main_frame, text="Start Time (HH:MM:SS):").grid(row=2, column=0, sticky="w", pady=5)
        self.start_time_var = tk.StringVar(value="00:00:00")
        self.start_entry = ttk.Entry(self.main_frame, textvariable=self.start_time_var, width=12)
        self.start_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        self._build_time_buttons(self.main_frame, self.start_time_var, row=2)

        # End Time
        ttk.Label(self.main_frame, text="End Time (HH:MM:SS):").grid(row=3, column=0, sticky="w", pady=5)
        self.end_time_var = tk.StringVar(value="00:00:00")
        self.end_entry = ttk.Entry(self.main_frame, textvariable=self.end_time_var, width=12)
        self.end_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self._build_time_buttons(self.main_frame, self.end_time_var, row=3)
        
        # FFmpeg Path (Defaults to local file in the same directory)
        ttk.Label(self.main_frame, text="FFmpeg Path:").grid(row=4, column=0, sticky="w", pady=5)
        self.ffmpeg_path_var = tk.StringVar(value=self.find_ffmpeg())
        self.ffmpeg_entry = ttk.Entry(self.main_frame, textvariable=self.ffmpeg_path_var)
        self.ffmpeg_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        self.ffmpeg_browse_btn = ttk.Button(self.main_frame, text="Find", command=self.browse_ffmpeg)
        self.ffmpeg_browse_btn.grid(row=4, column=2, padx=5, pady=5)
        
        # Output Filename
        ttk.Label(self.main_frame, text="Output Name:").grid(row=5, column=0, sticky="w", pady=5)
        self.output_name_var = tk.StringVar(value=self.DEFAULT_OUTPUT_NAME)
        self.output_entry = ttk.Entry(self.main_frame, textvariable=self.output_name_var)
        self.output_entry.grid(row=5, column=1, padx=5, pady=5, sticky="ew")
        output_buttons = ttk.Frame(self.main_frame)
        output_buttons.grid(row=5, column=2, padx=5, pady=5, sticky="e")
        self.output_reset_btn = ttk.Button(output_buttons, text="Default", command=self.reset_output)
        self.output_reset_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.output_browse_btn = ttk.Button(output_buttons, text="Save As…", command=self.browse_output)
        self.output_browse_btn.pack(side=tk.LEFT)

        # Audio Options
        opts_frame = tk.Frame(self.main_frame, bg="#252525", bd=0, highlightthickness=1,
                              highlightbackground="#3a3a3a")
        opts_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 2), ipady=4)

        self.normalize_var = tk.BooleanVar()
        norm_chk = tk.Checkbutton(
            opts_frame, text="Normalize volume (loudnorm)",
            variable=self.normalize_var,
            bg="#252525", fg="#ffffff", selectcolor="#1e1e1e",
            activebackground="#252525", activeforeground="#ffffff",
            font=("Segoe UI", 10), cursor="hand2",
            command=self._toggle_normalize
        )
        norm_chk.pack(side=tk.LEFT, padx=(10, 6))

        tk.Label(opts_frame, text="Target:", bg="#252525", fg="#aaaaaa",
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.lufs_var = tk.StringVar(value="-14")
        self.lufs_entry = tk.Entry(opts_frame, textvariable=self.lufs_var, width=5,
                                   bg="#333333", fg="#ffffff", insertbackground="white",
                                   font=("Segoe UI", 10), relief="flat", state="disabled",
                                   disabledbackground="#2a2a2a", disabledforeground="#666666")
        self.lufs_entry.pack(side=tk.LEFT, padx=(4, 2))
        tk.Label(opts_frame, text="LUFS", bg="#252525", fg="#aaaaaa",
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(opts_frame, text="(-23 = broadcast  •  -14 = streaming  •  -10 = loud)",
                 bg="#252525", fg="#555555", font=("Segoe UI", 8)).pack(side=tk.LEFT)

        # Run Button
        self.run_btn = ttk.Button(self.main_frame, text="START CLIPPING", style="Run.TButton", command=self.start_thread)
        self.run_btn.grid(row=7, column=0, columnspan=3, pady=(8, 5), ipady=12, sticky="ew")

        # Post-clip Action Bar
        action_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        action_frame.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        self.play_btn = tk.Button(
            action_frame, text="▶  Play Output",
            bg="#1a3a4a", fg="#4dcfff", activebackground="#1e5070", activeforeground="#4dcfff",
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0, padx=14, pady=6,
            cursor="hand2", command=self.play_output
        )
        self.play_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.rename_btn = tk.Button(
            action_frame, text="✏  Rename Previous Output…",
            bg="#2e2a1a", fg="#ffd966", activebackground="#4a421a", activeforeground="#ffd966",
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0, padx=14, pady=6,
            cursor="hand2", command=self.rename_previous_output
        )
        self.rename_btn.pack(side=tk.LEFT)
        
        # Log Area
        ttk.Label(self.main_frame, text="FFmpeg Console Output:").grid(row=9, column=0, sticky="w", pady=(10, 0))
        self.log_area = scrolledtext.ScrolledText(self.main_frame, height=10, bg="#121212", fg="#00ff00", 
                                                 font=("Consolas", 9), insertbackground="white")
        self.log_area.grid(row=10, column=0, columnspan=3, sticky="nsew", pady=5)
        
        # Status
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(self.main_frame, textvariable=self.status_var, bg="#1e1e1e", fg="#007acc", font=("Segoe UI", 10, "bold"))
        self.status_label.grid(row=11, column=0, columnspan=3, sticky="w", pady=(5, 0))

        # Layout weight
        self.main_frame.rowconfigure(10, weight=1)
        self.main_frame.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Timestamp convenience helpers
    # ------------------------------------------------------------------

    def _toggle_normalize(self):
        """Enable/disable the LUFS entry based on the normalize checkbox."""
        state = "normal" if self.normalize_var.get() else "disabled"
        self.lufs_entry.config(state=state)

    def _build_time_buttons(self, parent, time_var, row):
        """Create paired positive-over-negative nudge buttons for a timestamp field."""
        btn_frame = tk.Frame(parent, bg="#1e1e1e")
        btn_frame.grid(row=row, column=2, padx=(0, 5), pady=5, sticky="w")

        step_seconds = [300, 60, 30, 5, 1]
        for column, seconds in enumerate(step_seconds):
            for button_row, delta in enumerate((seconds, -seconds)):
                is_positive = delta > 0
                bg  = "#1a4a2e" if is_positive else "#4a1a1a"
                abg = "#27723f" if is_positive else "#72271a"
                fg  = "#4dff91" if is_positive else "#ff6b6b"
                unit = "m" if seconds >= 60 else "s"
                amount = seconds // 60 if seconds >= 60 else seconds
                sign = "+" if is_positive else "−"
                btn = tk.Button(
                    btn_frame, text=f"{sign}{amount}{unit}",
                    bg=bg, fg=fg, activebackground=abg, activeforeground=fg,
                    font=("Segoe UI", 8, "bold"),
                    relief="flat", bd=0, padx=4, pady=2, cursor="hand2",
                    command=lambda v=time_var, d=delta: self._nudge_time(v, d)
                )
                btn.grid(row=button_row, column=column, padx=1, pady=1)

    @staticmethod
    def _time_to_seconds(t):
        """Convert HH:MM:SS (or MM:SS or SS) string to total seconds."""
        parts = t.strip().split(":")
        parts = [int(p) for p in parts]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        else:
            return parts[0]

    @staticmethod
    def _seconds_to_time(s):
        """Convert total seconds to HH:MM:SS string."""
        s = max(0, int(s))
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def _nudge_time(self, time_var, delta_seconds):
        """Increment or decrement a timestamp StringVar by delta_seconds."""
        try:
            current = self._time_to_seconds(time_var.get())
        except (ValueError, AttributeError):
            current = 0
        time_var.set(self._seconds_to_time(current + delta_seconds))

    # ------------------------------------------------------------------

    def find_ffmpeg(self):
        # Look in the same directory as this script first
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_ffmpeg = os.path.join(script_dir, "ffmpeg.exe")
        if os.path.exists(local_ffmpeg):
            return local_ffmpeg
        
        # Fallback to system path
        return "ffmpeg"

    def browse_file(self):
        file_path = filedialog.askopenfilename(title="Select Video", filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov"), ("All", "*.*")])
        if file_path:
            self.input_path_var.set(file_path)
            self.reset_output()

    def reset_output(self):
        """Return the output name to the standard filename."""
        self.output_name_var.set(self.DEFAULT_OUTPUT_NAME)

    def browse_output(self):
        """Let the user pick a save location and filename for the output."""
        file_path = filedialog.asksaveasfilename(
            title="Save Output As",
            initialfile=self.output_name_var.get(),
            defaultextension=".mp4",
            filetypes=[("MP4", "*.mp4"), ("MKV", "*.mkv"), ("AVI", "*.avi"), ("All", "*.*")]
        )
        if file_path:
            self.output_name_var.set(file_path)

    def play_output(self):
        """Open the output file with the system default video player."""
        output = self.output_name_var.get()
        if not output or not os.path.exists(output):
            messagebox.showwarning("Play Output", "Output file not found. Clip a video first.")
            return
        try:
            if os.name == "nt":
                os.startfile(output)
            else:
                subprocess.Popen(["xdg-open", output])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")

    def rename_previous_output(self):
        """Rename the most recently produced output file via an inline dialog."""
        old_path = self.previous_output_path
        if not old_path or not os.path.exists(old_path):
            messagebox.showwarning("Rename", "Previous output file not found. Clip a video first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Output File")
        dialog.configure(bg="#1e1e1e")
        dialog.resizable(False, False)
        dialog.grab_set()

        old_dir  = os.path.dirname(os.path.abspath(old_path))
        old_name = os.path.basename(old_path)

        tk.Label(dialog, text="New filename:", bg="#1e1e1e", fg="#ffffff",
                 font=("Segoe UI", 10)).grid(row=0, column=0, padx=14, pady=(16, 4), sticky="w")
        new_name_var = tk.StringVar(value=old_name)
        entry = ttk.Entry(dialog, textvariable=new_name_var, width=38)
        entry.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew")
        entry.select_range(0, tk.END)
        entry.focus_set()

        def do_rename():
            new_name = new_name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Rename", "Please enter a filename.", parent=dialog)
                return
            new_path = os.path.join(old_dir, new_name)
            try:
                os.rename(old_path, new_path)
                self.previous_output_path = new_path
                if self.output_name_var.get() == old_path:
                    self.output_name_var.set(new_path)
                self.log(f">>> Renamed to: {new_path}")
                dialog.destroy()
            except OSError as e:
                messagebox.showerror("Rename Failed", str(e), parent=dialog)

        btn_frame = tk.Frame(dialog, bg="#1e1e1e")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(0, 14), padx=14, sticky="e")
        tk.Button(btn_frame, text="Cancel", bg="#333333", fg="#aaaaaa",
                  font=("Segoe UI", 9), relief="flat", padx=10, pady=4,
                  command=dialog.destroy).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_frame, text="Rename", bg="#007acc", fg="#ffffff",
                  font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4,
                  command=do_rename).pack(side=tk.LEFT)
        dialog.bind("<Return>", lambda _: do_rename())
        dialog.bind("<Escape>", lambda _: dialog.destroy())

    def browse_ffmpeg(self):
        file_path = filedialog.askopenfilename(title="Locate ffmpeg.exe", filetypes=[("Executable", "*.exe"), ("All", "*.*")])
        if file_path: self.ffmpeg_path_var.set(file_path)

    def validate_time(self, time_str):
        pattern = r"^(?:(?:(\d{1,2}):)?(\d{1,2}):)?(\d{1,2})$"
        return re.match(pattern, time_str) is not None

    @staticmethod
    def paths_match(first_path, second_path):
        return os.path.normcase(os.path.abspath(first_path)) == os.path.normcase(os.path.abspath(second_path))

    def log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)

    def start_thread(self):
        if not self.input_path_var.get():
            messagebox.showerror("Error", "Please select an input file.")
            return
        
        # Validate times
        s_time = self.start_time_var.get()
        e_time = self.end_time_var.get()
        if not self.validate_time(s_time) or not self.validate_time(e_time):
            messagebox.showerror("Error", "Invalid time format. Please use HH:MM:SS.")
            return

        input_path = self.input_path_var.get()
        output = self.output_name_var.get()
        if os.path.exists(output):
            can_overwrite = (
                self.previous_output_path
                and self.previous_output_input_path
                and self.paths_match(output, self.previous_output_path)
                and self.paths_match(input_path, self.previous_output_input_path)
            )
            if not can_overwrite:
                messagebox.showwarning(
                    "Output Already Exists",
                    f"'{output}' already exists.\n\nChoose a different output name before clipping from this input video."
                )
                return

        self.run_btn.config(state=tk.DISABLED)
        self.log_area.delete(1.0, tk.END)
        self.status_var.set("PROCESSING...")
        self.log(">>> Initializing FFmpeg...")
        
        threading.Thread(target=self.run_ffmpeg, daemon=True).start()

    def run_ffmpeg(self):
        input_path = self.input_path_var.get()
        start = self.start_time_var.get()
        end = self.end_time_var.get()
        output = self.output_name_var.get()
        ffmpeg_cmd = self.ffmpeg_path_var.get()
        can_overwrite = (
            self.previous_output_path
            and self.previous_output_input_path
            and self.paths_match(output, self.previous_output_path)
            and self.paths_match(input_path, self.previous_output_input_path)
        )
        
        cmd = [ffmpeg_cmd, "-y" if can_overwrite else "-n", "-i", input_path, "-ss", start, "-to", end,
               "-c:v", "libx264", "-crf", "18", "-preset", "medium",
               "-c:a", "aac", "-b:a", "128k"]

        if self.normalize_var.get():
            try:
                lufs = float(self.lufs_var.get())
            except ValueError:
                lufs = -14.0

            # --- Pass 1: measure loudness ---
            self.root.after(0, self.log, f">>> loudnorm pass 1/2: measuring loudness...")
            p1_cmd = [
                ffmpeg_cmd, "-y", "-i", input_path, "-ss", start, "-to", end,
                "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json",
                "-vn", "-f", "null", "-"
            ]
            try:
                p1 = subprocess.Popen(
                    p1_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                    text=True, startupinfo=startupinfo
                )
                _, p1_stderr = p1.communicate()

                # The JSON block is at the end of stderr
                json_match = re.search(r'\{[^{}]+\}', p1_stderr, re.DOTALL)
                if json_match:
                    stats = json.loads(json_match.group())
                    measured_i   = stats.get("input_i",      "-70.0")
                    measured_tp  = stats.get("input_tp",      "-9.0")
                    measured_lra = stats.get("input_lra",    "0.0")
                    measured_thr = stats.get("input_thresh", "-80.0")
                    offset       = stats.get("target_offset", "0.0")
                    self.root.after(0, self.log,
                        f">>> measured {measured_i} LUFS  →  target {lufs} LUFS  (pass 2/2)")
                    af = (
                        f"loudnorm=I={lufs}:TP=-1.5:LRA=11:linear=true"
                        f":measured_I={measured_i}:measured_TP={measured_tp}"
                        f":measured_LRA={measured_lra}:measured_thresh={measured_thr}"
                        f":offset={offset}"
                    )
                else:
                    # Fallback to single-pass if JSON not found
                    self.root.after(0, self.log, ">>> loudnorm: could not parse pass-1 stats, falling back to single-pass")
                    af = f"loudnorm=I={lufs}:TP=-1.5:LRA=11"
            except Exception as e:
                self.root.after(0, self.log, f">>> loudnorm pass 1 error: {e} — falling back to single-pass")
                af = f"loudnorm=I={lufs}:TP=-1.5:LRA=11"

            cmd += ["-af", af]

        cmd.append(output)
        
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, 
                                     text=True, startupinfo=startupinfo)
            
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    self.root.after(0, self.log, line.strip())
            
            if process.returncode == 0:
                self.previous_output_path = output
                self.previous_output_input_path = input_path
                self.root.after(0, lambda: self.status_var.set("SUCCESS!"))
                self.root.after(0, lambda: messagebox.showinfo("Success", f"Video clipped successfully!\nSaved as: {output}"))
            else:
                self.root.after(0, lambda: self.status_var.set("FAILED"))
                self.root.after(0, lambda: messagebox.showerror("Error", "FFmpeg failed. See log for details."))
                
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set("ERROR"))
            self.root.after(0, lambda: self.log(f"EXCEPTION: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL))

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoClipperGUI(root)
    root.mainloop()
