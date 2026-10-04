import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import subprocess
import os
import threading
import re
import json
import math
import shutil
import time

class VideoClipperGUI:
    DEFAULT_OUTPUT_NAME = "output.mp4"

    def __init__(self, root):
        self.root = root
        self.previous_output_path = None
        self.previous_output_input_path = None
        self.preview_process = None
        self.preview_stop_event = threading.Event()
        self.preview_image = None
        self.preview_position = 0.0
        self.preview_source = None
        self.preview_duration = 0.0
        self.preview_end_position = 0.0
        self.preview_started_at = 0.0
        self.preview_window_title = ""
        self.preview_window_handle = None
        self.preview_paused = False
        self.preview_slider_dragging = False
        self.preview_space_down = False
        self.preview_wndproc_callback = None
        self.preview_original_wndproc = None
        self.current_process = None
        self.cancel_requested = False
        self.output_customized = False
        self.video_duration = 0.0
        self.queue = []
        self.next_queue_id = 1
        self.is_processing = False

        self.root.title("Video Clipper Pro")
        available_height = max(600, root.winfo_screenheight() - 80)
        self.root.geometry(f"820x{min(available_height, 820)}")
        self.root.minsize(780, 600)
        self.root.configure(bg="#1e1e1e")

        # Discover ffmpeg, ffplay, and ffprobe
        self.ffmpeg_path = self.find_binary("ffmpeg")
        self.ffplay_path = self.find_binary("ffplay")
        self.ffprobe_path = self.find_binary("ffprobe")

        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Style configurations for dark "premium" look
        self.style.configure("TLabel", background="#1e1e1e", foreground="#ffffff", font=("Segoe UI", 10))
        self.style.configure("Sub.TLabel", background="#1e1e1e", foreground="#888888", font=("Segoe UI", 9))
        self.style.configure("TEntry", fieldbackground="#333333", foreground="#ffffff")
        self.style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=5)
        self.style.configure("Run.TButton", background="#007acc", foreground="#ffffff", font=("Segoe UI", 11, "bold"))
        self.style.map("Run.TButton", background=[("active", "#005a9e"), ("disabled", "#333333")])
        self.style.configure("Queue.TButton", background="#1e3a5f", foreground="#60a5fa", font=("Segoe UI", 10, "bold"))
        self.style.map("Queue.TButton", background=[("active", "#254a78"), ("disabled", "#333333")])
        self.style.configure("TFrame", background="#1e1e1e")
        self.style.configure("TProgressbar", thickness=14, troughcolor="#252525", background="#007acc")

        # Treeview styling
        self.style.configure("Treeview", background="#252525", foreground="#ffffff",
                             fieldbackground="#252525", rowheight=24, font=("Segoe UI", 9))
        self.style.configure("Treeview.Heading", background="#333333", foreground="#ffffff",
                             font=("Segoe UI", 9, "bold"), relief="flat")
        self.style.map("Treeview", background=[("selected", "#007acc")])

        # Main Container
        self.main_frame = ttk.Frame(root, padding="15", style="TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self._build_ui()
        self.root.bind_all("<KeyPress-space>", self._on_spacebar)
        self.root.bind_class("Button", "<KeyPress-space>", self._on_spacebar)
        self.root.bind_class("TButton", "<KeyPress-space>", self._on_spacebar)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def find_binary(self, name):
        """Look in script dir, current dir, known bin dir, or fallback to PATH."""
        ext = ".exe" if os.name == "nt" else ""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_bin = os.path.join(script_dir, f"{name}{ext}")
        if os.path.exists(local_bin):
            return local_bin
        cwd_bin = os.path.join(os.getcwd(), f"{name}{ext}")
        if os.path.exists(cwd_bin):
            return cwd_bin
        return shutil.which(f"{name}{ext}") or name

    def _build_ui(self):
        grid_row = 0

        # --- Header ---
        header_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        header_frame.grid(row=grid_row, column=0, columnspan=3, pady=(0, 8), sticky="w")
        tk.Label(header_frame, text="Video Clipper Pro", font=("Segoe UI", 18, "bold"),
                 bg="#1e1e1e", fg="#007acc").pack(side=tk.LEFT)
        tk.Label(header_frame, text="  Fast Seek • Precision Clips • Preview",
                 font=("Segoe UI", 9), bg="#1e1e1e", fg="#666666").pack(side=tk.LEFT, padx=(5, 0), pady=(6, 0))
        grid_row += 1

        # --- Input Video File ---
        ttk.Label(self.main_frame, text="Input Video:").grid(row=grid_row, column=0, sticky="w", pady=3)
        self.input_path_var = tk.StringVar()
        self.input_entry = ttk.Entry(self.main_frame, textvariable=self.input_path_var)
        self.input_entry.grid(row=grid_row, column=1, padx=5, pady=3, sticky="ew")
        self.browse_btn = ttk.Button(self.main_frame, text="Browse", command=self.browse_file)
        self.browse_btn.grid(row=grid_row, column=2, padx=5, pady=3)
        grid_row += 1

        # Video metadata info banner
        self.video_info_var = tk.StringVar(value="No video selected.")
        self.video_info_label = tk.Label(self.main_frame, textvariable=self.video_info_var,
                                         bg="#1e1e1e", fg="#888888", font=("Segoe UI", 9))
        self.video_info_label.grid(row=grid_row, column=1, sticky="w", padx=5, pady=(0, 5))
        grid_row += 1

        # --- Start Time ---
        ttk.Label(self.main_frame, text="Start Time:").grid(row=grid_row, column=0, sticky="w", pady=3)
        self.start_time_var = tk.StringVar(value="00:00:00")
        self.start_time_var.trace_add("write", self._on_timestamp_change)
        start_box = tk.Frame(self.main_frame, bg="#1e1e1e")
        start_box.grid(row=grid_row, column=1, sticky="w", padx=5, pady=3)
        self.start_entry = ttk.Entry(start_box, textvariable=self.start_time_var, width=14)
        self.start_entry.pack(side=tk.LEFT)
        tk.Button(start_box, text="⏮ 0s", bg="#2a2a2a", fg="#aaaaaa", activebackground="#3a3a3a",
                  font=("Segoe UI", 8), relief="flat", bd=0, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.start_time_var.set("00:00:00")).pack(side=tk.LEFT, padx=(5, 0))
        self._build_time_buttons(self.main_frame, self.start_time_var, row=grid_row)
        grid_row += 1

        # --- End Time ---
        ttk.Label(self.main_frame, text="End Time:").grid(row=grid_row, column=0, sticky="w", pady=3)
        self.end_time_var = tk.StringVar(value="00:00:00")
        self.end_time_var.trace_add("write", self._on_timestamp_change)
        end_box = tk.Frame(self.main_frame, bg="#1e1e1e")
        end_box.grid(row=grid_row, column=1, sticky="w", padx=5, pady=3)
        self.end_entry = ttk.Entry(end_box, textvariable=self.end_time_var, width=14)
        self.end_entry.pack(side=tk.LEFT)
        self.to_end_btn = tk.Button(end_box, text="⏭ End of Video", bg="#2a2a2a", fg="#aaaaaa",
                                    activebackground="#3a3a3a", font=("Segoe UI", 8), relief="flat", bd=0,
                                    padx=6, pady=2, cursor="hand2", command=self._set_end_to_video_duration)
        self.to_end_btn.pack(side=tk.LEFT, padx=(5, 0))
        self._build_time_buttons(self.main_frame, self.end_time_var, row=grid_row)
        grid_row += 1

        # --- Clip Duration Bar & Preview Controls ---
        duration_bar = tk.Frame(self.main_frame, bg="#252525", bd=0, highlightthickness=1,
                                highlightbackground="#333333")
        duration_bar.grid(row=grid_row, column=0, columnspan=3, sticky="ew", pady=(4, 6), ipady=4, padx=1)

        self.clip_dur_label = tk.Label(duration_bar, text="Clip Duration: 00:00:00 (0.0s)",
                                       bg="#252525", fg="#4dcfff", font=("Segoe UI", 9, "bold"))
        self.clip_dur_label.pack(side=tk.LEFT, padx=(10, 15))

        tk.Label(duration_bar, text="Extend:", bg="#252525", fg="#888888", font=("Segoe UI", 8)).pack(side=tk.LEFT)
        for s in (15, 30, 60):
            tk.Button(duration_bar, text=f"+{s}s", bg="#1a3a4a", fg="#4dcfff", activebackground="#254a60",
                      font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=6, pady=1, cursor="hand2",
                      command=lambda sec=s: self._extend_end_time(sec)).pack(side=tk.LEFT, padx=2)

        # Preview buttons using embedded ffplay
        self.stop_prev_btn = tk.Button(duration_bar, text="⏹ Stop", bg="#4a1a1a", fg="#ff6b6b",
                                       activebackground="#602525", font=("Segoe UI", 8, "bold"),
                                       relief="flat", bd=0, padx=8, pady=2, cursor="hand2",
                                       command=self.stop_preview)
        self.stop_prev_btn.pack(side=tk.RIGHT, padx=(2, 10))

        self.preview_clip_btn = tk.Button(duration_bar, text="▶ Preview Clip", bg="#2e1a47", fg="#c084fc",
                                     activebackground="#45276d", font=("Segoe UI", 8, "bold"),
                                     relief="flat", bd=0, padx=10, pady=2, cursor="hand2",
                                     command=self.preview_clip)
        self.preview_clip_btn.pack(side=tk.RIGHT, padx=2)

        self.preview_video_btn = tk.Button(duration_bar, text="▶ Preview Video", bg="#1a3a4a", fg="#4dcfff",
                                           activebackground="#254a60", font=("Segoe UI", 8, "bold"),
                                           relief="flat", bd=0, padx=10, pady=2, cursor="hand2",
                                           command=self.preview_video)
        self.preview_video_btn.pack(side=tk.RIGHT, padx=2)
        grid_row += 1

        # Embedded playback surface for the full input video.
        self.preview_surface = tk.Frame(self.main_frame, bg="#000000", width=760, height=260,
                                        highlightthickness=1, highlightbackground="#333333")
        self.preview_surface.grid(row=grid_row, column=0, columnspan=3, sticky="ew", pady=(0, 6), padx=1)
        self.preview_surface.grid_propagate(False)
        self.preview_image_label = tk.Label(self.preview_surface, bg="#000000")
        self.preview_image_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.preview_placeholder = tk.Label(
            self.preview_surface, text="Select a video, then click Preview Video",
            bg="#000000", fg="#777777", font=("Segoe UI", 11)
        )
        self.preview_placeholder.place(relx=0.5, rely=0.5, anchor="center")
        grid_row += 1

        self.preview_time_var = tk.StringVar(value="00:00:00 / 00:00:00")
        tk.Label(self.main_frame, textvariable=self.preview_time_var, bg="#1e1e1e",
                 fg="#888888", font=("Segoe UI", 8)).grid(
                     row=grid_row, column=0, columnspan=3, sticky="e", padx=6, pady=(0, 2)
                 )
        grid_row += 1

        self.preview_controls = tk.Frame(self.main_frame, bg="#1e1e1e")
        self.preview_controls.grid(row=grid_row, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.preview_seek_scale = tk.Scale(
            self.preview_controls, from_=0, to=100, orient=tk.HORIZONTAL,
            showvalue=False, resolution=0.1, length=260, highlightthickness=0,
            bg="#1e1e1e", fg="#4dcfff", troughcolor="#333333",
            activebackground="#4dcfff", sliderrelief="flat", bd=0,
            command=self._preview_slider_changed
        )
        self.preview_seek_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 8))
        self.preview_seek_scale.bind("<ButtonPress-1>", self._start_preview_slider_drag, add="+")
        self.preview_seek_scale.bind("<ButtonRelease-1>", self._seek_preview_slider, add="+")
        for text, delta in (("⏮ -10s", -10), ("◀ -1s", -1), ("+1s ▶", 1), ("+10s ⏭", 10)):
            tk.Button(self.preview_controls, text=text, bg="#252525", fg="#aaaaaa",
                      activebackground="#3a3a3a", activeforeground="#ffffff",
                      font=("Segoe UI", 8, "bold"), relief="flat", bd=0,
                      padx=8, pady=3, cursor="hand2",
                      command=lambda amount=delta: self._seek_preview(amount)).pack(side=tk.LEFT, padx=2)
        self.preview_play_btn = tk.Button(self.preview_controls, text="▶ Play",
                                          bg="#1a3a4a", fg="#4dcfff", activebackground="#254a60",
                                          font=("Segoe UI", 8, "bold"), relief="flat", bd=0,
                                          padx=8, pady=3, cursor="hand2", command=self._toggle_preview_pause)
        self.preview_play_btn.pack(side=tk.LEFT, padx=(8, 2))
        tk.Button(self.preview_controls, text="Set Start Here", bg="#1a4a2e", fg="#4dff91",
              activebackground="#27723f", activeforeground="#ffffff",
              font=("Segoe UI", 8, "bold"), relief="flat", bd=0,
              padx=7, pady=3, cursor="hand2",
              command=self._set_start_to_preview).pack(side=tk.LEFT, padx=(8, 2))
        tk.Button(self.preview_controls, text="Set End Here", bg="#4a2e1a", fg="#ffd966",
              activebackground="#724a27", activeforeground="#ffffff",
              font=("Segoe UI", 8, "bold"), relief="flat", bd=0,
              padx=7, pady=3, cursor="hand2",
              command=self._set_end_to_preview).pack(side=tk.LEFT, padx=2)
        grid_row += 1

        # --- Output Filename & Directory ---
        ttk.Label(self.main_frame, text="Output Path:").grid(row=grid_row, column=0, sticky="w", pady=3)
        self.output_name_var = tk.StringVar(value=self.DEFAULT_OUTPUT_NAME)
        self.output_entry = ttk.Entry(self.main_frame, textvariable=self.output_name_var)
        self.output_entry.grid(row=grid_row, column=1, padx=5, pady=3, sticky="ew")
        self.output_entry.bind("<Key>", lambda e: setattr(self, "output_customized", True))

        out_btn_box = tk.Frame(self.main_frame, bg="#1e1e1e")
        out_btn_box.grid(row=grid_row, column=2, padx=5, pady=3, sticky="e")
        tk.Button(out_btn_box, text="⚡ Auto-Name", bg="#252525", fg="#4dcfff", activebackground="#333333",
                  font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=6, pady=4, cursor="hand2",
                  command=self.auto_generate_output_path).pack(side=tk.LEFT, padx=(0, 4))
        self.output_browse_btn = ttk.Button(out_btn_box, text="Save As…", command=self.browse_output)
        self.output_browse_btn.pack(side=tk.LEFT)
        grid_row += 1

        # --- FFmpeg Path ---
        ttk.Label(self.main_frame, text="FFmpeg Path:").grid(row=grid_row, column=0, sticky="w", pady=3)
        self.ffmpeg_path_var = tk.StringVar(value=self.ffmpeg_path)
        self.ffmpeg_entry = ttk.Entry(self.main_frame, textvariable=self.ffmpeg_path_var)
        self.ffmpeg_entry.grid(row=grid_row, column=1, padx=5, pady=3, sticky="ew")
        self.ffmpeg_browse_btn = ttk.Button(self.main_frame, text="Locate", command=self.browse_ffmpeg)
        self.ffmpeg_browse_btn.grid(row=grid_row, column=2, padx=5, pady=3)
        grid_row += 1

        # --- Options (Audio, Format, GPU) ---
        opts_frame = tk.Frame(self.main_frame, bg="#252525", bd=0, highlightthickness=1,
                              highlightbackground="#3a3a3a")
        opts_frame.grid(row=grid_row, column=0, columnspan=3, sticky="ew", pady=(4, 6), ipady=4)

        # Normalization (disabled by default)
        self.normalize_var = tk.BooleanVar(value=False)
        norm_chk = tk.Checkbutton(
            opts_frame, text="Normalize volume (loudnorm)",
            variable=self.normalize_var, bg="#252525", fg="#ffffff", selectcolor="#1e1e1e",
            activebackground="#252525", activeforeground="#ffffff", font=("Segoe UI", 9),
            cursor="hand2", command=self._toggle_normalize
        )
        norm_chk.pack(side=tk.LEFT, padx=(10, 4))

        tk.Label(opts_frame, text="Target:", bg="#252525", fg="#aaaaaa", font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.lufs_var = tk.StringVar(value="-14")
        self.lufs_entry = tk.Entry(opts_frame, textvariable=self.lufs_var, width=5, bg="#333333",
                                   fg="#ffffff", insertbackground="white", font=("Segoe UI", 9),
                                   relief="flat", state="normal", disabledbackground="#2a2a2a",
                                   disabledforeground="#666666")
        self.lufs_entry.pack(side=tk.LEFT, padx=(3, 2))
        tk.Label(opts_frame, text="LUFS", bg="#252525", fg="#aaaaaa", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(0, 10))

        # Mute audio checkbox
        self.mute_var = tk.BooleanVar(value=False)
        mute_chk = tk.Checkbutton(
            opts_frame, text="Mute audio (-an)", variable=self.mute_var,
            bg="#252525", fg="#ffffff", selectcolor="#1e1e1e",
            activebackground="#252525", activeforeground="#ffffff", font=("Segoe UI", 9),
            cursor="hand2", command=self._toggle_mute
        )
        mute_chk.pack(side=tk.LEFT, padx=(0, 12))

        # Format selector: MP4 vs GIF
        tk.Label(opts_frame, text="Format:", bg="#252525", fg="#aaaaaa", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value="MP4")
        for fmt in ("MP4", "GIF"):
            tk.Radiobutton(opts_frame, text=fmt, variable=self.format_var, value=fmt,
                           bg="#252525", fg="#ffffff", selectcolor="#1e1e1e",
                           activebackground="#252525", activeforeground="#ffffff",
                           font=("Segoe UI", 9, "bold" if fmt == "MP4" else "normal"),
                           command=self._on_format_change).pack(side=tk.LEFT, padx=3)

        # Hardware Acceleration checkbox
        self.hw_accel_var = tk.BooleanVar(value=False)
        hw_chk = tk.Checkbutton(
            opts_frame, text="GPU / HW Accel", variable=self.hw_accel_var,
            bg="#252525", fg="#ffd966", selectcolor="#1e1e1e",
            activebackground="#252525", activeforeground="#ffd966", font=("Segoe UI", 9),
            cursor="hand2"
        )
        hw_chk.pack(side=tk.RIGHT, padx=(0, 10))
        grid_row += 1

        # --- Primary Action Bar: Start Clipping + Cancel ---
        actions_bar = tk.Frame(self.main_frame, bg="#1e1e1e")
        actions_bar.grid(row=grid_row, column=0, columnspan=3, sticky="ew", pady=(6, 6))

        self.run_btn = ttk.Button(actions_bar, text="START CLIPPING", style="Run.TButton",
                                  command=self.start_single_clip)
        self.run_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, ipady=8, padx=(0, 6))

        self.cancel_btn = tk.Button(actions_bar, text="⏹ Cancel", bg="#4a1a1a", fg="#ff6b6b",
                                    activebackground="#6b2323", activeforeground="#ffffff",
                                    font=("Segoe UI", 10, "bold"), relief="flat", bd=0, padx=14, pady=6,
                                    cursor="hand2", state="disabled", command=self.cancel_processing)
        self.cancel_btn.pack(side=tk.RIGHT, fill=tk.BOTH, ipady=4)
        grid_row += 1

        # --- Progress Bar & Progress Label ---
        prog_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        prog_frame.grid(row=grid_row, column=0, columnspan=3, sticky="ew", pady=(2, 4))
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_text_var = tk.StringVar(value="0%")
        self.progress_label = tk.Label(prog_frame, textvariable=self.progress_text_var,
                                       bg="#1e1e1e", fg="#4dcfff", font=("Segoe UI", 9, "bold"), width=22)
        self.progress_label.pack(side=tk.RIGHT, padx=(6, 0))
        grid_row += 1

        # --- Post-clip Action Bar ---
        action_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        action_frame.grid(row=grid_row, column=0, columnspan=3, sticky="ew", pady=(2, 6))

        self.play_btn = tk.Button(
            action_frame, text="▶  Play Output",
            bg="#1a3a4a", fg="#4dcfff", activebackground="#1e5070", activeforeground="#4dcfff",
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=12, pady=5,
            cursor="hand2", command=self.play_output
        )
        self.play_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.folder_btn = tk.Button(
            action_frame, text="📁  Open Folder",
            bg="#1f3d32", fg="#5cdbb5", activebackground="#275444", activeforeground="#5cdbb5",
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=12, pady=5,
            cursor="hand2", command=self.open_output_folder
        )
        self.folder_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.rename_btn = tk.Button(
            action_frame, text="✏  Rename Previous Output…",
            bg="#2e2a1a", fg="#ffd966", activebackground="#4a421a", activeforeground="#ffd966",
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=12, pady=5,
            cursor="hand2", command=self.rename_previous_output
        )
        self.rename_btn.pack(side=tk.LEFT)
        grid_row += 1

        # --- Log Area ---
        ttk.Label(self.main_frame, text="FFmpeg Console Output:").grid(row=grid_row, column=0, sticky="w", pady=(2, 0))
        grid_row += 1

        self.log_area = scrolledtext.ScrolledText(self.main_frame, height=5, bg="#121212", fg="#00ff00",
                                                  font=("Consolas", 9), insertbackground="white")
        self.log_area.grid(row=grid_row, column=0, columnspan=3, sticky="nsew", pady=4)
        grid_row += 1

        # --- Status Label ---
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(self.main_frame, textvariable=self.status_var, bg="#1e1e1e",
                                     fg="#007acc", font=("Segoe UI", 10, "bold"))
        self.status_label.grid(row=grid_row, column=0, columnspan=3, sticky="w", pady=(2, 0))

        # Layout weight
        self.main_frame.rowconfigure(grid_row - 1, weight=1)
        self.main_frame.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Timestamp & Math Helpers (Sub-second support)
    # ------------------------------------------------------------------

    def _toggle_normalize(self):
        state = "normal" if self.normalize_var.get() and not self.mute_var.get() else "disabled"
        self.lufs_entry.config(state=state)

    def _toggle_mute(self):
        if self.mute_var.get():
            self.lufs_entry.config(state="disabled")
        else:
            self._toggle_normalize()

    def _on_format_change(self):
        fmt = self.format_var.get()
        if fmt == "GIF":
            self.normalize_var.set(False)
            self.mute_var.set(True)
            self._toggle_normalize()
        else:
            self.normalize_var.set(False)
            self.mute_var.set(False)
            self._toggle_normalize()
        self.auto_generate_output_path()

    def _build_time_buttons(self, parent, time_var, row):
        """Create paired nudge buttons including precision sub-second nudges."""
        btn_frame = tk.Frame(parent, bg="#1e1e1e")
        btn_frame.grid(row=row, column=2, padx=(0, 5), pady=3, sticky="w")

        step_seconds = [300, 60, 10, 1, 0.1]
        for column, seconds in enumerate(step_seconds):
            for button_row, delta in enumerate((seconds, -seconds)):
                is_positive = delta > 0
                bg  = "#1a4a2e" if is_positive else "#4a1a1a"
                abg = "#27723f" if is_positive else "#72271a"
                fg  = "#4dff91" if is_positive else "#ff6b6b"
                if seconds >= 60:
                    label = f"{int(seconds // 60)}m"
                elif seconds >= 1:
                    label = f"{int(seconds)}s"
                else:
                    label = f"{seconds}s"
                sign = "+" if is_positive else "−"
                btn = tk.Button(
                    btn_frame, text=f"{sign}{label}",
                    bg=bg, fg=fg, activebackground=abg, activeforeground=fg,
                    font=("Segoe UI", 8, "bold"),
                    relief="flat", bd=0, padx=4, pady=1, cursor="hand2",
                    command=lambda v=time_var, d=delta: self._nudge_time(v, d)
                )
                btn.grid(row=button_row, column=column, padx=1, pady=1)

    @staticmethod
    def _time_to_seconds(t):
        """Convert HH:MM:SS[.mmm] or MM:SS[.mmm] or SS[.mmm] to total seconds (float)."""
        if not t:
            return 0.0
        parts = str(t).strip().split(":")
        try:
            parts = [float(p) for p in parts]
        except (ValueError, AttributeError):
            return 0.0
        if len(parts) == 3:
            return parts[0] * 3600.0 + parts[1] * 60.0 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60.0 + parts[1]
        elif len(parts) == 1:
            return parts[0]
        return 0.0

    @staticmethod
    def _seconds_to_time(s, force_subseconds=False):
        """Convert total seconds to HH:MM:SS[.mmm] string."""
        s = max(0.0, float(s))
        total_int = int(s)
        frac = round(s - total_int, 3)
        if frac >= 1.0:
            total_int += 1
            frac = 0.0
        h, rem = divmod(total_int, 3600)
        m, sec = divmod(rem, 60)
        if force_subseconds or frac > 0.0001:
            ms = int(round(frac * 1000))
            return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def _nudge_time(self, time_var, delta_seconds):
        current = self._time_to_seconds(time_var.get())
        new_val = max(0.0, round(current + delta_seconds, 3))
        time_var.set(self._seconds_to_time(new_val))

    def _on_timestamp_change(self, *args):
        self._update_clip_duration_display()
        if not self.output_customized:
            self.auto_generate_output_path()

    def _update_clip_duration_display(self):
        s = self._time_to_seconds(self.start_time_var.get())
        e = self._time_to_seconds(self.end_time_var.get())
        diff = max(0.0, e - s)
        dur_str = self._seconds_to_time(diff)
        if e < s:
            self.clip_dur_label.config(text="Clip Duration: Invalid (End < Start)", fg="#ff6b6b")
        else:
            self.clip_dur_label.config(text=f"Clip Duration: {dur_str} ({diff:.2f}s)", fg="#4dcfff")

    def _extend_end_time(self, seconds):
        s = self._time_to_seconds(self.start_time_var.get())
        self.end_time_var.set(self._seconds_to_time(s + seconds))

    def _set_end_to_video_duration(self):
        if self.video_duration > 0:
            self.end_time_var.set(self._seconds_to_time(self.video_duration))
        else:
            messagebox.showinfo("Video Duration", "Video length not available or video not probed yet.")

    def validate_time(self, time_str):
        """Validate HH:MM:SS, HH:MM:SS.mmm, MM:SS, or SS."""
        text = str(time_str).strip()
        pattern = r"^(?:(?:(\d{1,2}):)?(\d{1,2}):)?(\d{1,2}(?:\.\d+)?)$"
        if not re.match(pattern, text):
            return False

        parts = text.split(":")
        try:
            values = [float(part) for part in parts]
        except ValueError:
            return False
        if not all(math.isfinite(value) for value in values):
            return False
        if len(parts) == 3 and values[1] >= 60:
            return False
        if len(parts) >= 2 and values[-1] >= 60:
            return False
        return True

    @staticmethod
    def paths_match(first_path, second_path):
        if not first_path or not second_path:
            return False
        return os.path.normcase(os.path.abspath(first_path)) == os.path.normcase(os.path.abspath(second_path))

    @staticmethod
    def output_matches_format(output, output_format):
        extension = os.path.splitext(output)[1].lower()
        if output_format == "GIF":
            return extension == ".gif"
        return extension != ".gif"

    # ------------------------------------------------------------------
    # Video Probing (ffprobe)
    # ------------------------------------------------------------------

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Video",
            filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v"), ("All", "*.*")]
        )
        if file_path:
            self.input_path_var.set(file_path)
            self.output_customized = False
            self.video_info_var.set("Probing video information...")
            threading.Thread(target=self._probe_video, args=(file_path,), daemon=True).start()

    def _probe_video(self, file_path):
        if not os.path.exists(file_path):
            return
        cmd = [
            self.ffprobe_path, "-v", "error",
            "-show_entries", "format=duration:stream=width,height,r_frame_rate",
            "-of", "json", file_path
        ]
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo, timeout=10)
            data = json.loads(res.stdout)
            dur = float(data.get("format", {}).get("duration", 0))
            self.video_duration = dur

            streams = data.get("streams", [])
            v_stream = next((s for s in streams if "width" in s and s.get("width")), None)
            info_parts = [f"Duration: {self._seconds_to_time(dur)}"]
            if v_stream:
                info_parts.append(f"{v_stream.get('width')}x{v_stream.get('height')}")
                r_fps = v_stream.get("r_frame_rate", "")
                if "/" in r_fps:
                    num, den = r_fps.split("/")
                    if float(den) > 0:
                        info_parts.append(f"{float(num)/float(den):.1f} fps")
            info_str = " | ".join(info_parts)
            self.root.after(0, lambda: self._apply_probe_results(dur, info_str))
        except Exception:
            self.root.after(0, lambda: self.video_info_var.set(os.path.basename(file_path)))

    def _apply_probe_results(self, dur, info_str):
        self.video_info_var.set(info_str)
        cur_end = self._time_to_seconds(self.end_time_var.get())
        cur_start = self._time_to_seconds(self.start_time_var.get())
        if cur_end <= cur_start or cur_end == 0:
            default_dur = min(30.0, dur) if dur > 0 else 30.0
            self.end_time_var.set(self._seconds_to_time(cur_start + default_dur))
        self.auto_generate_output_path()

    # ------------------------------------------------------------------
    # In-App Preview (ffplay re-parented into Tk)
    # ------------------------------------------------------------------

    def preview_video(self):
        input_path = self.input_path_var.get().strip()
        if not input_path or not os.path.exists(input_path):
            messagebox.showwarning("Preview", "Please select a valid input video.")
            return

        self.preview_end_position = 0.0
        self._start_preview(input_path, 0.0, None, "full video")

    def preview_clip(self):
        input_path = self.input_path_var.get().strip()
        if not input_path or not os.path.exists(input_path):
            messagebox.showwarning("Preview", "Please select a valid input video.")
            return

        s = self._time_to_seconds(self.start_time_var.get())
        e = self._time_to_seconds(self.end_time_var.get())
        if e <= s:
            messagebox.showwarning("Preview", "End time must be greater than Start time.")
            return
        self._start_preview(input_path, s, e - s, "clip")

    def _start_preview(self, input_path, start_seconds, duration, description, start_paused=False):
        self._stop_preview_process(show_placeholder=False)
        self.preview_surface.update_idletasks()

        start_seconds = max(0.0, float(start_seconds))
        if self.video_duration > 0:
            start_seconds = min(start_seconds, max(0.0, self.video_duration - 0.01))
        if duration is None and self.preview_end_position > start_seconds:
            duration = self.preview_end_position - start_seconds
        elif duration is not None:
            self.preview_end_position = start_seconds + duration
        self.preview_stop_event.clear()
        self.preview_position = start_seconds
        self.preview_paused = start_paused
        self.preview_space_down = False
        self.preview_window_handle = None
        self.preview_source = input_path
        self.preview_duration = duration or self.video_duration or self._time_to_seconds(self.end_time_var.get())
        self.preview_time_var.set(
            f"{self._seconds_to_time(start_seconds)} / {self._seconds_to_time(self.preview_duration)}"
        )
        self.preview_play_btn.config(text="▶ Resume" if start_paused else "⏸ Pause")

        self.preview_window_title = f"Video Clipper Preview {os.getpid()}"
        cmd = [self.ffplay_path, "-ss",
               self._seconds_to_time(start_seconds, force_subseconds=True),
             "-window_title", self.preview_window_title, "-noborder",
             "-left", "-10000", "-top", "-10000"]
        if duration is not None:
            cmd += ["-t", str(duration), "-autoexit"]
        cmd.append(input_path)
        try:
            self.preview_placeholder.place_forget()
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.preview_process = subprocess.Popen(
                cmd, startupinfo=startupinfo
            )
            self.preview_started_at = time.monotonic()
            threading.Thread(target=self._embed_ffplay_window,
                             args=(self.preview_process,), daemon=True).start()
            self.root.after(100, self._update_preview_clock)
            self.status_var.set(f"Previewing {description} with audio in the clipper window...")
        except Exception as ex:
            self.preview_placeholder.place(relx=0.5, rely=0.5, anchor="center")
            messagebox.showerror("Preview Error", f"Could not start FFmpeg preview:\n{ex}")

    def _embed_ffplay_window(self, process):
        if os.name != "nt":
            self.root.after(0, self._preview_embed_failed)
            return
        import ctypes

        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = ctypes.c_size_t
        window_handle = None
        for _ in range(60):
            if self.preview_stop_event.is_set() or process.poll() is not None:
                return
            window_handle = user32.FindWindowW(None, self.preview_window_title)
            if window_handle:
                break
            time.sleep(0.05)
        if not window_handle or self.preview_stop_event.is_set():
            if not self.preview_stop_event.is_set():
                self.root.after(0, self._preview_embed_failed)
            return
        self.root.after(0, self._attach_ffplay_window, window_handle)

    def _preview_embed_failed(self):
        if self.preview_process and self.preview_process.poll() is None:
            self.preview_process.terminate()
        self.preview_process = None
        self.preview_placeholder.place(relx=0.5, rely=0.5, anchor="center")
        messagebox.showerror("Preview Error", "Could not embed the audio/video player in the clipper window.")

    def _attach_ffplay_window(self, window_handle):
        if not self.preview_process or self.preview_stop_event.is_set():
            return
        import ctypes

        user32 = ctypes.windll.user32
        user32.SetParent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        user32.SetParent.restype = ctypes.c_void_p
        user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.InvalidateRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
        user32.UpdateWindow.argtypes = [ctypes.c_void_p]
        self.preview_window_handle = window_handle
        parent_handle = self.preview_surface.winfo_id()
        user32.SetParent(ctypes.c_void_p(window_handle), ctypes.c_void_p(parent_handle))
        get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        set_style.restype = ctypes.c_ssize_t
        style = get_style(window_handle, -16)
        style = (style & ~0x00CF0000) | 0x40000000
        set_style(ctypes.c_void_p(window_handle), -16, style)
        self._install_preview_key_handler(window_handle)
        self._resize_embedded_preview(window_handle)
        user32.ShowWindow(ctypes.c_void_p(window_handle), 5)
        user32.InvalidateRect(ctypes.c_void_p(window_handle), None, True)
        user32.UpdateWindow(ctypes.c_void_p(window_handle))
        if self.preview_paused:
            self.root.after(100, self._pause_embedded_preview)

    def _pause_embedded_preview(self):
        if self.preview_process and self.preview_window_handle and self.preview_paused:
            import ctypes

            user32 = ctypes.windll.user32
            user32.PostMessageW(self.preview_window_handle, 0x0100, ord("P"), 0)
            user32.PostMessageW(self.preview_window_handle, 0x0101, ord("P"), 0)

    def _install_preview_key_handler(self, window_handle):
        import ctypes

        user32 = ctypes.windll.user32
        result_type = ctypes.c_ssize_t
        callback_type = ctypes.WINFUNCTYPE(
            result_type, ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_size_t, ctypes.c_ssize_t
        )
        self.preview_wndproc_callback = callback_type(self._preview_window_proc)
        set_proc = user32.SetWindowLongPtrW
        set_proc.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        set_proc.restype = ctypes.c_void_p
        self.preview_original_wndproc = set_proc(
            ctypes.c_void_p(window_handle), -4,
            ctypes.cast(self.preview_wndproc_callback, ctypes.c_void_p)
        )

    def _preview_window_proc(self, window_handle, message, wparam, lparam):
        import ctypes

        user32 = ctypes.windll.user32
        call_proc = user32.CallWindowProcW
        call_proc.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                              ctypes.c_size_t, ctypes.c_ssize_t]
        call_proc.restype = ctypes.c_ssize_t
        return call_proc(
            self.preview_original_wndproc, ctypes.c_void_p(window_handle),
            message, wparam, lparam
        )

    def _restore_preview_key_handler(self):
        if self.preview_window_handle and self.preview_original_wndproc:
            import ctypes

            user32 = ctypes.windll.user32
            set_proc = user32.SetWindowLongPtrW
            set_proc.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            set_proc.restype = ctypes.c_void_p
            set_proc(ctypes.c_void_p(self.preview_window_handle), -4,
                     self.preview_original_wndproc)
        self.preview_wndproc_callback = None
        self.preview_original_wndproc = None

    def _resize_embedded_preview(self, window_handle=None):
        if os.name != "nt":
            return
        import ctypes

        if window_handle is None:
            user32 = ctypes.windll.user32
            user32.FindWindowW.restype = ctypes.c_size_t
            window_handle = user32.FindWindowW(None, self.preview_window_title)
        if window_handle:
            self.preview_surface.update_idletasks()
            user32 = ctypes.windll.user32
            user32.MoveWindow.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_int, ctypes.c_int, ctypes.c_bool]
            user32.MoveWindow(
                ctypes.c_void_p(window_handle), 0, 0, self.preview_surface.winfo_width(),
                self.preview_surface.winfo_height(), True
            )

    def _update_preview_clock(self):
        if not self.preview_process or self.preview_process.poll() is not None:
            if self.preview_process:
                self.preview_process = None
            self.preview_play_btn.config(text="▶ Play")
            return
        if os.name == "nt":
            import ctypes

            space_down = bool(ctypes.windll.user32.GetAsyncKeyState(0x20) & 0x8000)
            if space_down and not self.preview_space_down:
                self.preview_space_down = True
                self.preview_paused = not self.preview_paused
                self.preview_started_at = time.monotonic()
                self.preview_play_btn.config(
                    text="▶ Resume" if self.preview_paused else "⏸ Pause"
                )
            elif not space_down:
                self.preview_space_down = False
        if self.preview_paused:
            self.root.after(100, self._update_preview_clock)
            return
        self.preview_position = self.preview_position + (time.monotonic() - self.preview_started_at)
        self.preview_started_at = time.monotonic()
        if self.preview_duration > 0:
            self.preview_position = min(self.preview_position, self.preview_duration)
        self.preview_time_var.set(
            f"{self._seconds_to_time(self.preview_position)} / {self._seconds_to_time(self.preview_duration)}"
        )
        if self.preview_duration > 0 and not self.preview_slider_dragging:
            self.preview_seek_scale.set(self.preview_position / self.preview_duration * 100)
        self.root.after(100, self._update_preview_clock)

    def _preview_slider_changed(self, value):
        if not self.preview_slider_dragging or self.preview_duration <= 0:
            return
        position = self.preview_duration * float(value) / 100.0
        self.preview_time_var.set(
            f"{self._seconds_to_time(position)} / {self._seconds_to_time(self.preview_duration)}"
        )

    def _start_preview_slider_drag(self, _event=None):
        self.preview_slider_dragging = True
        if self.preview_process and self.preview_process.poll() is None and not self.preview_paused:
            self._toggle_preview_pause()

    def _seek_preview_slider(self, _event=None):
        self.preview_slider_dragging = False
        if self.preview_duration <= 0:
            return
        position = self.preview_duration * self.preview_seek_scale.get() / 100.0
        input_path = self.preview_source or self.input_path_var.get().strip()
        if input_path and os.path.exists(input_path):
            self._start_preview(input_path, position, None, "video")

    def _on_spacebar(self, _event=None):
        self.preview_space_down = True
        if self.preview_process and self.preview_process.poll() is None:
            self._toggle_preview_pause()
        return "break"

    def _set_start_to_preview(self):
        if not self.preview_source or not self.preview_process:
            messagebox.showinfo("Set Start", "Preview the video first, then set the start time.")
            return
        self.start_time_var.set(self._seconds_to_time(self.preview_position, force_subseconds=True))

    def _set_end_to_preview(self):
        if not self.preview_source or not self.preview_process:
            messagebox.showinfo("Set End", "Preview the video first, then set the end time.")
            return
        self.end_time_var.set(self._seconds_to_time(self.preview_position, force_subseconds=True))

    def _seek_preview(self, delta_seconds):
        input_path = self.preview_source or self.input_path_var.get().strip()
        if not input_path or not os.path.exists(input_path):
            messagebox.showwarning("Preview", "Please select a valid input video.")
            return
        duration = self.preview_end_position or self.video_duration
        position = max(0.0, self.preview_position + delta_seconds)
        if duration > 0:
            position = min(position, max(0.0, duration - 0.01))
        self._start_preview(input_path, position, None, "video")

    def _toggle_preview_pause(self):
        if self.preview_process and self.preview_process.poll() is None and self.preview_window_handle:
            if self.preview_paused:
                input_path = self.preview_source or self.input_path_var.get().strip()
                if input_path and os.path.exists(input_path):
                    self._start_preview(input_path, self.preview_position, None, "video")
                    self.preview_space_down = True
                return
            if os.name == "nt":
                import ctypes

                user32 = ctypes.windll.user32
                user32.PostMessageW(self.preview_window_handle, 0x0100, ord("P"), 0)
                user32.PostMessageW(self.preview_window_handle, 0x0101, ord("P"), 0)
            self.preview_paused = not self.preview_paused
            self.preview_started_at = time.monotonic()
            self.preview_play_btn.config(text="▶ Resume" if self.preview_paused else "⏸ Pause")
            return
        input_path = self.preview_source or self.input_path_var.get().strip()
        if input_path and os.path.exists(input_path):
            self._start_preview(input_path, self.preview_position, None, "video")

    def _stop_preview_process(self, show_placeholder=True):
        self.preview_stop_event.set()
        self._restore_preview_key_handler()
        if self.preview_process and self.preview_process.poll() is None:
            try:
                self.preview_process.terminate()
            except Exception:
                pass
        self.preview_process = None
        self.preview_window_handle = None
        self.preview_paused = False
        if show_placeholder and hasattr(self, "preview_placeholder"):
            self.preview_placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def stop_preview(self):
        self._stop_preview_process(show_placeholder=True)
        if hasattr(self, "preview_play_btn"):
            self.preview_play_btn.config(text="▶ Play")

    # ------------------------------------------------------------------
    # Output Naming & Directory Placement
    # ------------------------------------------------------------------

    def auto_generate_output_path(self):
        input_path = self.input_path_var.get().strip()
        if not input_path:
            return
        dirname = os.path.dirname(os.path.abspath(input_path))
        base_name, _ = os.path.splitext(os.path.basename(input_path))

        s_clean = self.start_time_var.get().replace(":", "-").replace(".", "_")
        e_clean = self.end_time_var.get().replace(":", "-").replace(".", "_")
        ext = ".gif" if self.format_var.get() == "GIF" else ".mp4"
        out_name = f"{base_name}_clip_{s_clean}_to_{e_clean}{ext}"
        output_path = os.path.join(dirname, out_name)

        self.output_name_var.set(output_path)
        self.output_customized = False

    def browse_output(self):
        initial_file = os.path.basename(self.output_name_var.get())
        initial_dir = os.path.dirname(self.output_name_var.get())
        ext = ".gif" if self.format_var.get() == "GIF" else ".mp4"

        file_path = filedialog.asksaveasfilename(
            title="Save Output As",
            initialdir=initial_dir if initial_dir else None,
            initialfile=initial_file,
            defaultextension=ext,
            filetypes=[("MP4 Video", "*.mp4"), ("GIF Animation", "*.gif"), ("MKV Video", "*.mkv"), ("All", "*.*")]
        )
        if file_path:
            self.output_name_var.set(file_path)
            self.output_customized = True

    def browse_ffmpeg(self):
        file_path = filedialog.askopenfilename(
            title="Locate ffmpeg.exe",
            filetypes=[("Executable", "*.exe"), ("All", "*.*")]
        )
        if file_path:
            self.ffmpeg_path_var.set(file_path)

    # ------------------------------------------------------------------
    # Post-Clip Action Handlers
    # ------------------------------------------------------------------

    def _get_active_output_target(self):
        """Return selected queue item output path, or the current output_name_var."""
        sel = self.queue_tree.selection()
        if sel:
            item_id = sel[0]
            matched = next((q for q in self.queue if str(q["id"]) == str(item_id)), None)
            if matched and os.path.exists(matched["output"]):
                return matched["output"]
        cur = self.output_name_var.get().strip()
        if cur and os.path.exists(cur):
            return cur
        return self.previous_output_path

    def play_output(self):
        target = self._get_active_output_target()
        if not target or not os.path.exists(target):
            messagebox.showwarning("Play Output", "Output file not found. Clip a video first.")
            return
        try:
            if os.name == "nt":
                os.startfile(target)
            else:
                subprocess.Popen(["xdg-open", target])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")
    def open_output_folder(self):
        target = self._get_active_output_target()
        if not target or not os.path.exists(target):
            messagebox.showwarning("Open Folder", "Output file not found. Clip a video first.")
            return
        norm_path = os.path.normpath(target)
        try:
            if os.name == "nt":
                subprocess.Popen(f'explorer /select,"{norm_path}"')
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(norm_path)])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def rename_previous_output(self):
        old_path = self._get_active_output_target()
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
            if os.path.basename(new_name) != new_name:
                messagebox.showwarning("Rename", "Please enter a filename, not a path.", parent=dialog)
                return
            new_path = os.path.join(old_dir, new_name)
            try:
                if not self.paths_match(old_path, new_path) and os.path.exists(new_path):
                    if not messagebox.askyesno("Overwrite?", f"'{new_path}' already exists.\n\nOverwrite it?", parent=dialog):
                        return
                os.rename(old_path, new_path)
                self.previous_output_path = new_path
                if self.output_name_var.get() == old_path:
                    self.output_name_var.set(new_path)
                # Update in queue if present
                for q in self.queue:
                    if q["output"] == old_path:
                        q["output"] = new_path
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

    # ------------------------------------------------------------------
    # Batch Queue Management
    # ------------------------------------------------------------------

    def add_to_queue(self):
        input_path = self.input_path_var.get().strip()
        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Queue Error", "Please select a valid input video.")
            return

        s_str = self.start_time_var.get()
        e_str = self.end_time_var.get()
        if not self.validate_time(s_str) or not self.validate_time(e_str):
            messagebox.showerror("Queue Error", "Invalid time format.")
            return

        s = self._time_to_seconds(s_str)
        e = self._time_to_seconds(e_str)
        if e <= s:
            messagebox.showerror("Queue Error", "End time must be greater than Start time.")
            return

        out_path = self.output_name_var.get().strip()
        if not out_path:
            messagebox.showerror("Queue Error", "Please specify an output filename.")
            return
        if not self.output_matches_format(out_path, self.format_var.get()):
            messagebox.showerror("Queue Error", "GIF clips must use a .gif output; video clips cannot use .gif.")
            return
        if any(self.paths_match(out_path, queued["output"]) for queued in self.queue):
            messagebox.showerror("Queue Error", "Each queued clip must have a unique output path.")
            return

        item = {
            "id": self.next_queue_id,
            "input_path": input_path,
            "start": s_str,
            "end": e_str,
            "duration": e - s,
            "output": out_path,
            "format": self.format_var.get(),
            "normalize": self.normalize_var.get(),
            "lufs": self.lufs_var.get(),
            "mute": self.mute_var.get(),
            "hw_accel": self.hw_accel_var.get(),
            "status": "Pending"
        }
        self.next_queue_id += 1
        self.queue.append(item)
        self.queue_tree.insert("", tk.END, iid=str(item["id"]), values=(
            item["id"],
            os.path.basename(input_path),
            f"{s_str} -> {e_str}",
            f"{item['duration']:.1f}s",
            item["format"],
            item["status"]
        ))
        self.process_queue_btn.config(text=f"⚡ Process Queue ({len(self.queue)})")
        self.status_var.set(f"Added clip to queue ({len(self.queue)} total)")

    def remove_from_queue(self):
        sel = self.queue_tree.selection()
        if not sel:
            return
        for item_id in sel:
            self.queue = [q for q in self.queue if str(q["id"]) != str(item_id)]
            self.queue_tree.delete(item_id)
        self.process_queue_btn.config(text=f"⚡ Process Queue ({len(self.queue)})" if self.queue else "⚡ Process Queue")

    def clear_queue(self):
        self.queue.clear()
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        self.process_queue_btn.config(text="⚡ Process Queue")

    def _on_queue_double_click(self, event):
        sel = self.queue_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        matched = next((q for q in self.queue if str(q["id"]) == str(item_id)), None)
        if not matched:
            return
        if os.path.exists(matched["output"]):
            self.play_output()
        else:
            self.input_path_var.set(matched["input_path"])
            self.start_time_var.set(matched["start"])
            self.end_time_var.set(matched["end"])
            self.output_name_var.set(matched["output"])
            self.format_var.set(matched["format"])
            self.normalize_var.set(matched["normalize"])
            self.mute_var.set(matched["mute"])
            self.hw_accel_var.set(matched["hw_accel"])
            self.status_var.set(f"Loaded clip #{matched['id']} into editor")

    def start_batch_queue(self):
        if not self.queue:
            messagebox.showinfo("Queue", "Queue is empty. Add clips first.")
            return
        if self.is_processing:
            return

        existing_outputs = [item["output"] for item in self.queue if os.path.exists(item["output"])]
        if existing_outputs and not messagebox.askyesno(
                "Overwrite?",
                f"{len(existing_outputs)} queued output(s) already exist.\n\nOverwrite them?"):
            return

        self.cancel_requested = False
        self._set_ui_state(processing=True)
        threading.Thread(target=self._run_batch_worker, daemon=True).start()

    def _run_batch_worker(self):
        total = len(self.queue)
        success_count = 0

        for idx, item in enumerate(self.queue):
            if self.cancel_requested:
                break
            if item["status"] == "Done":
                success_count += 1
                continue

            self.root.after(0, lambda i=item["id"]: self.queue_tree.set(str(i), "status", "Processing..."))
            self.root.after(0, lambda i=idx, t=total: self.status_var.set(f"Batch: Processing {i+1} of {t}..."))

            ok = self._execute_clip_process(item)
            if ok:
                success_count += 1
                item["status"] = "Done"
                self.previous_output_path = item["output"]
                self.previous_output_input_path = item["input_path"]
                self.root.after(0, lambda i=item["id"]: self.queue_tree.set(str(i), "status", "Done"))
            else:
                item["status"] = "Failed"
                self.root.after(0, lambda i=item["id"]: self.queue_tree.set(str(i), "status", "Failed"))

        self.root.after(0, lambda: self._on_batch_complete(success_count, total))

    def _on_batch_complete(self, success_count, total):
        self._set_ui_state(processing=False)
        if self.cancel_requested:
            self.status_var.set("Batch processing cancelled.")
            messagebox.showwarning("Cancelled", f"Batch cancelled.\n{success_count} of {total} completed.")
        else:
            self.status_var.set(f"Batch completed: {success_count}/{total} succeeded")
            messagebox.showinfo("Batch Complete", f"Finished processing batch queue:\n{success_count} of {total} clips saved.")

    # ------------------------------------------------------------------
    # Single Clip Action
    # ------------------------------------------------------------------

    def start_single_clip(self):
        input_path = self.input_path_var.get().strip()
        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Error", "Please select a valid input file.")
            return

        s_str = self.start_time_var.get()
        e_str = self.end_time_var.get()
        if not self.validate_time(s_str) or not self.validate_time(e_str):
            messagebox.showerror("Error", "Invalid time format. Please use HH:MM:SS or HH:MM:SS.mmm.")
            return

        s = self._time_to_seconds(s_str)
        e = self._time_to_seconds(e_str)
        if e <= s:
            messagebox.showerror("Error", "End time must be greater than Start time.")
            return

        output = self.output_name_var.get().strip()
        if not output:
            messagebox.showerror("Error", "Please specify an output filename.")
            return
        if not self.output_matches_format(output, self.format_var.get()):
            messagebox.showerror("Error", "GIF clips must use a .gif output; video clips cannot use .gif.")
            return

        ffmpeg_path = self.ffmpeg_path_var.get().strip().strip('"')
        if not os.path.isfile(ffmpeg_path):
            messagebox.showerror("FFmpeg", f"FFmpeg executable was not found:\n{ffmpeg_path}")
            return

        if os.path.exists(output):
            can_overwrite = (
                self.previous_output_path
                and self.previous_output_input_path
                and self.paths_match(output, self.previous_output_path)
                and self.paths_match(input_path, self.previous_output_input_path)
            )
            if not can_overwrite:
                if not messagebox.askyesno("Overwrite?", f"'{output}' already exists.\n\nDo you want to overwrite it?"):
                    return

        item = {
            "input_path": input_path,
            "start": s_str,
            "end": e_str,
            "duration": e - s,
            "output": output,
            "format": self.format_var.get(),
            "normalize": self.normalize_var.get(),
            "lufs": self.lufs_var.get(),
            "mute": self.mute_var.get(),
            "hw_accel": self.hw_accel_var.get()
        }

        self.cancel_requested = False
        self._set_ui_state(processing=True)
        self.log_area.delete(1.0, tk.END)
        self.status_var.set("PROCESSING...")
        self.progress_var.set(0)
        self.progress_text_var.set("0%")

        threading.Thread(target=self._run_single_worker, args=(item,), daemon=True).start()

    def _run_single_worker(self, item):
        ok = self._execute_clip_process(item)
        self.root.after(0, lambda: self._on_single_complete(ok, item))

    def _on_single_complete(self, ok, item):
        self._set_ui_state(processing=False)
        if self.cancel_requested:
            self.status_var.set("CANCELLED")
            self.progress_var.set(0)
            self.progress_text_var.set("0%")
        elif ok:
            self.previous_output_path = item["output"]
            self.previous_output_input_path = item["input_path"]
            self.status_var.set("SUCCESS!")
            self.progress_var.set(100)
            self.progress_text_var.set("100%")
            messagebox.showinfo("Success", f"Video clipped successfully!\nSaved as: {item['output']}")
        else:
            self.status_var.set("FAILED")
            messagebox.showerror(
                "FFmpeg failed",
                "FFmpeg could not create the clip. The console log below contains the exact command and error."
            )

    def cancel_processing(self):
        self.cancel_requested = True
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except Exception:
                pass
        self.status_var.set("Cancelling operation...")

    def _set_ui_state(self, processing):
        self.is_processing = processing
        state = tk.DISABLED if processing else tk.NORMAL
        self.run_btn.config(state=state)
        self.cancel_btn.config(state=tk.NORMAL if processing else tk.DISABLED)

    def log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)

    def _update_progress(self, pct, curr_sec, total_sec):
        self.progress_var.set(pct)
        self.progress_text_var.set(f"{pct:.1f}% ({self._seconds_to_time(curr_sec)} / {self._seconds_to_time(total_sec)})")

    # ------------------------------------------------------------------
    # Core FFmpeg Execution Engine (Fast-Seek, Loudnorm 2-pass, GIF, HW)
    # ------------------------------------------------------------------

    def _execute_clip_process(self, item):
        ffmpeg_cmd = self.ffmpeg_path_var.get().strip().strip('"')
        input_path = item["input_path"]
        start_sec = self._time_to_seconds(item["start"])
        end_sec = self._time_to_seconds(item["end"])
        dur_sec = max(0.001, end_sec - start_sec)
        output = item["output"]

        start_str = self._seconds_to_time(start_sec, force_subseconds=True)
        dur_str = f"{dur_sec:.3f}"

        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self.root.after(0, self.log, f"\n{'='*50}\n>>> Clipping: {os.path.basename(input_path)}")
        self.root.after(0, self.log, f">>> Segment: {start_str} (Duration: {dur_str}s)")

        if not os.path.isfile(ffmpeg_cmd):
            self.root.after(0, self.log, f"ERROR: FFmpeg executable not found: {ffmpeg_cmd}")
            return False

        output_dir = os.path.dirname(os.path.abspath(output))
        if not os.path.isdir(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as exc:
                self.root.after(0, self.log, f"ERROR: Cannot create output directory '{output_dir}': {exc}")
                return False

        # Case 1: GIF Export
        if item.get("format") == "GIF":
            vf = "fps=15,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
            cmd = [
                ffmpeg_cmd, "-y",
                "-ss", start_str, "-i", input_path, "-t", dur_str,
                "-vf", vf, "-loop", "0", output
            ]
            self.root.after(0, self.log, f">>> Command: {subprocess.list2cmdline(cmd)}")
            return self._run_command_with_progress(cmd, dur_sec, startupinfo)

        # Case 2: MP4 Video Export
        af_filter = None
        if item.get("normalize") and not item.get("mute"):
            try:
                lufs = float(item.get("lufs", -14.0))
            except ValueError:
                lufs = -14.0

            # Pass 1: Measure loudness with fast seeking
            self.root.after(0, self.log, ">>> loudnorm pass 1/2: measuring loudness (fast-seek)...")
            p1_cmd = [
                ffmpeg_cmd, "-y",
                "-ss", start_str, "-i", input_path, "-t", dur_str,
                "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json",
                "-vn", "-f", "null", "-"
            ]
            try:
                p1 = subprocess.Popen(p1_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                                      text=True, startupinfo=startupinfo)
                self.current_process = p1
                _, p1_stderr = p1.communicate()
                self.current_process = None

                if self.cancel_requested:
                    return False

                json_match = re.search(r'\{[^{}]+\}', p1_stderr, re.DOTALL)
                if json_match:
                    stats = json.loads(json_match.group())
                    measured_i   = stats.get("input_i",      "-70.0")
                    measured_tp  = stats.get("input_tp",      "-9.0")
                    measured_lra = stats.get("input_lra",    "0.0")
                    measured_thr = stats.get("input_thresh", "-80.0")
                    offset       = stats.get("target_offset", "0.0")
                    self.root.after(0, self.log,
                        f">>> measured {measured_i} LUFS → target {lufs} LUFS (pass 2/2)")
                    af_filter = (
                        f"loudnorm=I={lufs}:TP=-1.5:LRA=11:linear=true"
                        f":measured_I={measured_i}:measured_TP={measured_tp}"
                        f":measured_LRA={measured_lra}:measured_thresh={measured_thr}"
                        f":offset={offset}"
                    )
                else:
                    self.root.after(0, self.log, ">>> loudnorm: parsing stats failed, using single-pass")
                    af_filter = f"loudnorm=I={lufs}:TP=-1.5:LRA=11"
            except Exception as e:
                self.root.after(0, self.log, f">>> loudnorm pass 1 error: {e}")
                af_filter = f"loudnorm=I={lufs}:TP=-1.5:LRA=11"

        if self.cancel_requested:
            return False

        # Main encoding command with fast-seek
        cmd = [ffmpeg_cmd, "-y", "-ss", start_str, "-i", input_path, "-t", dur_str]

        # H.264 requires even dimensions; some older videos use an odd height.
        cmd += ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]

        # Video encoder selection
        if item.get("hw_accel") and os.name == "nt":
            self.root.after(0, self.log, ">>> Using Windows Media Foundation GPU encoder (h264_mf)...")
            cmd += ["-c:v", "h264_mf", "-b:v", "8M"]
        else:
            cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "medium"]

        # Audio options
        if item.get("mute"):
            cmd += ["-an"]
        else:
            cmd += ["-c:a", "aac", "-b:a", "128k"]
            if af_filter:
                cmd += ["-af", af_filter]

        cmd.append(output)
        self.root.after(0, self.log, f">>> Command: {subprocess.list2cmdline(cmd)}")
        return self._run_command_with_progress(cmd, dur_sec, startupinfo)

    def _run_command_with_progress(self, cmd, total_dur_sec, startupinfo):
        try:
            self.current_process = subprocess.Popen(
                cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                text=True, startupinfo=startupinfo
            )
            process = self.current_process
            while True:
                if self.cancel_requested:
                    try:
                        process.terminate()
                    except Exception:
                        pass
                    break
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    line_str = line.strip()
                    self.root.after(0, self.log, line_str)

                    time_match = re.search(r"time=(\d{2}:\d{2}:\d{2}(?:\.\d+)?)", line_str)
                    if time_match and total_dur_sec > 0:
                        curr_sec = self._time_to_seconds(time_match.group(1))
                        pct = min(100.0, (curr_sec / total_dur_sec) * 100.0)
                        self.root.after(0, lambda p=pct, c=curr_sec, t=total_dur_sec: self._update_progress(p, c, t))

            self.current_process = None
            if self.cancel_requested:
                return False
            if process.returncode != 0:
                self.root.after(0, self.log, f"ERROR: FFmpeg exited with code {process.returncode}")
                return False
            return True
        except Exception as e:
            self.current_process = None
            error_message = str(e)
            self.root.after(0, self.log, f"EXCEPTION: {error_message}")
            return False

    def on_closing(self):
        self.stop_preview()
        self.cancel_processing()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoClipperGUI(root)
    root.mainloop()
