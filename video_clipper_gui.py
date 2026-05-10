import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import subprocess
import os
import threading
import re

class VideoClipperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Clipper Pro")
        self.root.geometry("750x650")
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
        self.start_entry = ttk.Entry(self.main_frame, textvariable=self.start_time_var)
        self.start_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        # End Time
        ttk.Label(self.main_frame, text="End Time (HH:MM:SS):").grid(row=3, column=0, sticky="w", pady=5)
        self.end_time_var = tk.StringVar(value="00:00:00")
        self.end_entry = ttk.Entry(self.main_frame, textvariable=self.end_time_var)
        self.end_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        
        # FFmpeg Path (Defaults to local file in the same directory)
        ttk.Label(self.main_frame, text="FFmpeg Path:").grid(row=4, column=0, sticky="w", pady=5)
        self.ffmpeg_path_var = tk.StringVar(value=self.find_ffmpeg())
        self.ffmpeg_entry = ttk.Entry(self.main_frame, textvariable=self.ffmpeg_path_var)
        self.ffmpeg_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        self.ffmpeg_browse_btn = ttk.Button(self.main_frame, text="Find", command=self.browse_ffmpeg)
        self.ffmpeg_browse_btn.grid(row=4, column=2, padx=5, pady=5)
        
        # Output Filename
        ttk.Label(self.main_frame, text="Output Name:").grid(row=5, column=0, sticky="w", pady=5)
        self.output_name_var = tk.StringVar(value="output.mp4")
        self.output_entry = ttk.Entry(self.main_frame, textvariable=self.output_name_var)
        self.output_entry.grid(row=5, column=1, padx=5, pady=5, sticky="ew")
        
        # Run Button
        self.run_btn = ttk.Button(self.main_frame, text="START CLIPPING", style="Run.TButton", command=self.start_thread)
        self.run_btn.grid(row=6, column=0, columnspan=3, pady=20, ipady=12, sticky="ew")
        
        # Log Area
        ttk.Label(self.main_frame, text="FFmpeg Console Output:").grid(row=7, column=0, sticky="w", pady=(10, 0))
        self.log_area = scrolledtext.ScrolledText(self.main_frame, height=12, bg="#121212", fg="#00ff00", 
                                                 font=("Consolas", 9), insertbackground="white")
        self.log_area.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=5)
        
        # Status
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(self.main_frame, textvariable=self.status_var, bg="#1e1e1e", fg="#007acc", font=("Segoe UI", 10, "bold"))
        self.status_label.grid(row=9, column=0, columnspan=3, sticky="w", pady=(5, 0))

        # Layout weight
        self.main_frame.rowconfigure(8, weight=1)
        self.main_frame.columnconfigure(1, weight=1)

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
        if file_path: self.input_path_var.set(file_path)

    def browse_ffmpeg(self):
        file_path = filedialog.askopenfilename(title="Locate ffmpeg.exe", filetypes=[("Executable", "*.exe"), ("All", "*.*")])
        if file_path: self.ffmpeg_path_var.set(file_path)

    def validate_time(self, time_str):
        pattern = r"^(?:(?:(\d{1,2}):)?(\d{1,2}):)?(\d{1,2})$"
        return re.match(pattern, time_str) is not None

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

        # Check if output file is writable
        output = self.output_name_var.get()
        if os.path.exists(output):
            try:
                with open(output, 'ab'):
                    pass
            except IOError:
                messagebox.showerror("Permission Denied", 
                    f"Cannot write to '{output}'.\n\nIs the file open in a video player? Please close it and try again.")
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
        
        cmd = [ffmpeg_cmd, "-y", "-i", input_path, "-ss", start, "-to", end, 
               "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "128k", output]
        
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
