#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import json
import time
import requests
from datetime import datetime, timedelta
import speech_recognition as sr
import google.generativeai as genai
from PIL import Image, ImageTk, ImageDraw, ImageFont
import io
import sys
import math
import re
import tempfile
import os
from gtts import gTTS
import pygame
import pyaudio
import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def load_env(filepath=".env"):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    os.environ[key] = val

load_env()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
ARDUINO_IP = os.environ.get("ARDUINO_IP", "")
ARDUINO_PORT = int(os.environ.get("ARDUINO_PORT", "80"))
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "2.0"))
SPEECH_LANGUAGE = os.environ.get("SPEECH_LANGUAGE", "id-ID")
TTS_LANGUAGE = os.environ.get("TTS_LANGUAGE", "id")
TTS_RATE = int(os.environ.get("TTS_RATE", "150"))
TTS_VOLUME = float(os.environ.get("TTS_VOLUME", "0.9"))
ENERGY_THRESHOLD = int(os.environ.get("ENERGY_THRESHOLD", "300"))
DYNAMIC_ENERGY_THRESHOLD = os.environ.get("DYNAMIC_ENERGY_THRESHOLD", "True").lower() == "true"
PAUSE_THRESHOLD = float(os.environ.get("PAUSE_THRESHOLD", "0.5"))
PHRASE_THRESHOLD = float(os.environ.get("PHRASE_THRESHOLD", "0.3"))
NON_SPEAKING_DURATION = float(os.environ.get("NON_SPEAKING_DURATION", "0.5"))

class VoiceController:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart AC Voice Controller - Real-Time")
        self.root.geometry("1400x900")
        self.root.configure(bg="#0a0e1a")

        self.is_listening = False
        self.is_speaking = False
        self.clap_detection_enabled = True
        self.recognizer = sr.Recognizer()

        self.recognizer.energy_threshold = ENERGY_THRESHOLD
        self.recognizer.dynamic_energy_threshold = DYNAMIC_ENERGY_THRESHOLD
        self.recognizer.pause_threshold = PAUSE_THRESHOLD
        self.recognizer.phrase_threshold = PHRASE_THRESHOLD
        self.recognizer.non_speaking_duration = NON_SPEAKING_DURATION
        try:
            self.microphone = sr.Microphone()

            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
        except Exception as e:
            messagebox.showerror("Microphone Error", f"Tidak dapat mengakses microphone:\n{e}")
            self.microphone = None
        self.arduino_data = {}
        self.last_update = None
        self.animation_running = False
        self.mic_pulse_radius = 0

        self.last_detected_text = None
        self.current_audio = None

        try:
            pygame.mixer.init()
        except:
            pass

        self.init_gemini()
        self.setup_ui()
        self.start_data_polling()
        self.start_animations()
        self.root.after(500, self.check_env_variables)

    def init_gemini(self):

        try:
            if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
                genai.configure(api_key=GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel(GEMINI_MODEL)
            else:
                self.gemini_model = None
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize Gemini: {e}")
            self.gemini_model = None

    def check_env_variables(self):
        warnings = []
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
            warnings.append("- GEMINI_API_KEY belum diisi di berkas .env")
        if not ARDUINO_IP or ARDUINO_IP == "YOUR_ARDUINO_IP":
            warnings.append("- ARDUINO_IP belum diisi di berkas .env")
        if warnings:
            msg = "Konfigurasi berikut belum diatur:\n\n" + "\n".join(warnings) + "\n\nSilakan isi nilai yang benar di berkas .env lalu restart aplikasi."
            messagebox.showwarning("Konfigurasi Belum Lengkap", msg)

    def setup_ui(self):

        main_frame = tk.Frame(self.root, bg="#0a0e1a")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        header_frame = tk.Frame(main_frame, bg="#0a0e1a")
        header_frame.pack(fill=tk.X, pady=(0, 15))

        title_label = tk.Label(
            header_frame,
            text="🎤 Smart AC Voice Controller",
            font=("Segoe UI", 22, "bold"),
            bg="#0a0e1a",
            fg="#6EE7B7"
        )
        title_label.pack(side=tk.LEFT)

        self.status_frame = tk.Frame(header_frame, bg="#0a0e1a")
        self.status_frame.pack(side=tk.RIGHT)

        self.status_dot = tk.Label(
            self.status_frame,
            text="●",
            font=("Arial", 16),
            bg="#0a0e1a",
            fg="#7ee787"
        )
        self.status_dot.pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(
            self.status_frame,
            text="Ready",
            font=("Segoe UI", 12),
            bg="#0a0e1a",
            fg="#99a6b3"
        )
        self.status_label.pack(side=tk.LEFT)

        content_frame = tk.Frame(main_frame, bg="#0a0e1a")
        content_frame.pack(fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(content_frame, bg="#1a1e2a", relief=tk.FLAT, bd=0)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        left_panel.config(highlightbackground="#2a2e3a", highlightthickness=1)

        status_card = tk.Frame(left_panel, bg="#1a1e2a", relief=tk.FLAT)
        status_card.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        tk.Label(
            status_card,
            text="Status AC",
            font=("Segoe UI", 16, "bold"),
            bg="#1a1e2a",
            fg="#e6eef3"
        ).pack(pady=(0, 15))

        temp_frame = tk.Frame(status_card, bg="#1a1e2a")
        temp_frame.pack(fill=tk.X, pady=10)

        self.temp_label = tk.Label(
            temp_frame,
            text="--°C",
            font=("Segoe UI", 48, "bold"),
            bg="#1a1e2a",
            fg="#6EE7B7"
        )
        self.temp_label.pack()

        self.hum_label = tk.Label(
            temp_frame,
            text="Kelembapan: --%",
            font=("Segoe UI", 14),
            bg="#1a1e2a",
            fg="#99a6b3"
        )
        self.hum_label.pack(pady=5)

        ac_state_frame = tk.Frame(status_card, bg="#1a1e2a")
        ac_state_frame.pack(fill=tk.X, pady=15)

        self.ac_state_label = tk.Label(
            ac_state_frame,
            text="AC: OFF",
            font=("Segoe UI", 20, "bold"),
            bg="#1a1e2a",
            fg="#ef4444"
        )
        self.ac_state_label.pack()

        self.mode_label = tk.Label(
            ac_state_frame,
            text="Mode: --",
            font=("Segoe UI", 14),
            bg="#1a1e2a",
            fg="#99a6b3"
        )
        self.mode_label.pack(pady=5)

        self.timer_label = tk.Label(
            ac_state_frame,
            text="",
            font=("Segoe UI", 14, "bold"),
            bg="#1a1e2a",
            fg="#ffb86b"
        )
        self.timer_label.pack(pady=5)

        self.cooldown_label = tk.Label(
            ac_state_frame,
            text="",
            font=("Segoe UI", 12),
            bg="#1a1e2a",
            fg="#60a5fa"
        )
        self.cooldown_label.pack(pady=3)

        suhu_frame = tk.Frame(status_card, bg="#1a1e2a")
        suhu_frame.pack(fill=tk.X, pady=15)

        tk.Label(
            suhu_frame,
            text="Pengaturan Suhu Auto ON/OFF:",
            font=("Segoe UI", 12, "bold"),
            bg="#1a1e2a",
            fg="#e6eef3"
        ).pack(anchor=tk.W, pady=(0, 8))

        suhu_input_frame = tk.Frame(suhu_frame, bg="#1a1e2a")
        suhu_input_frame.pack(fill=tk.X)

        tk.Label(suhu_input_frame, text="ON:", bg="#1a1e2a", fg="#99a6b3", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)
        self.suhu_on_entry = tk.Entry(
            suhu_input_frame,
            font=("Segoe UI", 11),
            bg="#0a0e1a",
            fg="#e6eef3",
            insertbackground="#6EE7B7",
            relief=tk.FLAT,
            bd=0,
            width=8
        )
        self.suhu_on_entry.pack(side=tk.LEFT, padx=5)
        self.suhu_on_entry.insert(0, "31.0")

        tk.Label(suhu_input_frame, text="OFF:", bg="#1a1e2a", fg="#99a6b3", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)
        self.suhu_off_entry = tk.Entry(
            suhu_input_frame,
            font=("Segoe UI", 11),
            bg="#0a0e1a",
            fg="#e6eef3",
            insertbackground="#6EE7B7",
            relief=tk.FLAT,
            bd=0,
            width=8
        )
        self.suhu_off_entry.pack(side=tk.LEFT, padx=5)
        self.suhu_off_entry.insert(0, "30.0")

        btn_save_suhu = tk.Button(
            suhu_input_frame,
            text="Simpan Threshold",
            font=("Segoe UI", 9),
            bg="#6EE7B7",
            fg="#04201a",
            activebackground="#2dd4bf",
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self.save_suhu_settings
        )
        btn_save_suhu.pack(side=tk.LEFT, padx=5)

        control_frame = tk.Frame(status_card, bg="#1a1e2a")
        control_frame.pack(fill=tk.X, pady=10)

        self.on_btn = tk.Button(
            control_frame,
            text="AC ON",
            font=("Segoe UI", 12, "bold"),
            bg="#6EE7B7",
            fg="#04201a",
            activebackground="#2dd4bf",
            relief=tk.FLAT,
            padx=15,
            pady=10,
            cursor="hand2",
            command=self.turn_ac_on
        )
        self.on_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.off_btn = tk.Button(
            control_frame,
            text="AC OFF",
            font=("Segoe UI", 12, "bold"),
            bg="#ef4444",
            fg="white",
            activebackground="#f87171",
            relief=tk.FLAT,
            padx=15,
            pady=10,
            cursor="hand2",
            command=self.turn_ac_off
        )
        self.off_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        auto_frame = tk.Frame(status_card, bg="#1a1e2a")
        auto_frame.pack(fill=tk.X, pady=5)

        btn_auto_on = tk.Button(
            auto_frame,
            text="Aktifkan Auto",
            font=("Segoe UI", 10),
            bg="#60a5fa",
            fg="white",
            activebackground="#3b82f6",
            relief=tk.FLAT,
            padx=10,
            pady=8,
            cursor="hand2",
            command=self.enable_auto_mode_only
        )
        btn_auto_on.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        btn_auto_off = tk.Button(
            auto_frame,
            text="Stop Auto",
            font=("Segoe UI", 10),
            bg="#ffb86b",
            fg="white",
            activebackground="#ffa366",
            relief=tk.FLAT,
            padx=10,
            pady=8,
            cursor="hand2",
            command=self.disable_auto_mode
        )
        btn_auto_off.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        timer_frame = tk.Frame(status_card, bg="#1a1e2a")
        timer_frame.pack(fill=tk.X, pady=10)

        tk.Label(
            timer_frame,
            text="Timer:",
            font=("Segoe UI", 11, "bold"),
            bg="#1a1e2a",
            fg="#e6eef3"
        ).pack(anchor=tk.W, pady=(0, 5))

        timer_input_frame = tk.Frame(timer_frame, bg="#1a1e2a")
        timer_input_frame.pack(fill=tk.X)

        self.timer_h_entry = tk.Entry(timer_input_frame, font=("Segoe UI", 10), bg="#0a0e1a", fg="#e6eef3", insertbackground="#6EE7B7", relief=tk.FLAT, width=5)
        self.timer_h_entry.pack(side=tk.LEFT, padx=2)
        self.timer_h_entry.insert(0, "0")
        tk.Label(timer_input_frame, text="h", bg="#1a1e2a", fg="#99a6b3", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)

        self.timer_m_entry = tk.Entry(timer_input_frame, font=("Segoe UI", 10), bg="#0a0e1a", fg="#e6eef3", insertbackground="#6EE7B7", relief=tk.FLAT, width=5)
        self.timer_m_entry.pack(side=tk.LEFT, padx=2)
        self.timer_m_entry.insert(0, "0")
        tk.Label(timer_input_frame, text="m", bg="#1a1e2a", fg="#99a6b3", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)

        self.timer_s_entry = tk.Entry(timer_input_frame, font=("Segoe UI", 10), bg="#0a0e1a", fg="#e6eef3", insertbackground="#6EE7B7", relief=tk.FLAT, width=5)
        self.timer_s_entry.pack(side=tk.LEFT, padx=2)
        self.timer_s_entry.insert(0, "0")
        tk.Label(timer_input_frame, text="s", bg="#1a1e2a", fg="#99a6b3", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)

        btn_start_timer = tk.Button(
            timer_input_frame,
            text="Start Timer",
            font=("Segoe UI", 9),
            bg="#ffb86b",
            fg="white",
            activebackground="#ffa366",
            relief=tk.FLAT,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self.start_timer_from_ui
        )
        btn_start_timer.pack(side=tk.LEFT, padx=5)

        cooldown_frame = tk.Frame(status_card, bg="#1a1e2a")
        cooldown_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            cooldown_frame,
            text="Cooldown:",
            font=("Segoe UI", 11, "bold"),
            bg="#1a1e2a",
            fg="#e6eef3"
        ).pack(anchor=tk.W, pady=(0, 5))

        cooldown_input_frame = tk.Frame(cooldown_frame, bg="#1a1e2a")
        cooldown_input_frame.pack(fill=tk.X)

        btn_cooldown_30 = tk.Button(
            cooldown_input_frame,
            text="30s",
            font=("Segoe UI", 9),
            bg="#60a5fa",
            fg="white",
            relief=tk.FLAT,
            padx=8,
            pady=5,
            cursor="hand2",
            command=lambda: self.set_cooldown(30)
        )
        btn_cooldown_30.pack(side=tk.LEFT, padx=2)

        btn_cooldown_60 = tk.Button(
            cooldown_input_frame,
            text="60s",
            font=("Segoe UI", 9),
            bg="#60a5fa",
            fg="white",
            relief=tk.FLAT,
            padx=8,
            pady=5,
            cursor="hand2",
            command=lambda: self.set_cooldown(60)
        )
        btn_cooldown_60.pack(side=tk.LEFT, padx=2)

        btn_cooldown_120 = tk.Button(
            cooldown_input_frame,
            text="120s",
            font=("Segoe UI", 9),
            bg="#60a5fa",
            fg="white",
            relief=tk.FLAT,
            padx=8,
            pady=5,
            cursor="hand2",
            command=lambda: self.set_cooldown(120)
        )
        btn_cooldown_120.pack(side=tk.LEFT, padx=2)

        right_panel = tk.Frame(content_frame, bg="#1a1e2a", relief=tk.FLAT, bd=0)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        right_panel.config(highlightbackground="#2a2e3a", highlightthickness=1)

        voice_card = tk.Frame(right_panel, bg="#1a1e2a", relief=tk.FLAT)
        voice_card.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        tk.Label(
            voice_card,
            text="Voice Control",
            font=("Segoe UI", 16, "bold"),
            bg="#1a1e2a",
            fg="#e6eef3"
        ).pack(pady=(0, 15))

        mic_frame = tk.Frame(voice_card, bg="#1a1e2a")
        mic_frame.pack(pady=15)

        self.mic_canvas = tk.Canvas(
            mic_frame,
            width=180,
            height=180,
            bg="#1a1e2a",
            highlightthickness=0
        )
        self.mic_canvas.pack()

        self.mic_button = tk.Button(
            voice_card,
            text="🎤 Tekan untuk Bicara",
            font=("Segoe UI", 16, "bold"),
            bg="#6EE7B7",
            fg="#04201a",
            activebackground="#2dd4bf",
            activeforeground="#04201a",
            relief=tk.FLAT,
            bd=0,
            padx=30,
            pady=15,
            cursor="hand2",
            command=self.toggle_listening
        )
        self.mic_button.pack(pady=10)

        self.info_label = tk.Label(
            voice_card,
            text="Tekan tombol untuk nyalakan/matikan mic",
            font=("Segoe UI", 10),
            bg="#1a1e2a",
            fg="#60a5fa"
        )
        self.info_label.pack(pady=5)

        self.draw_mic_icon()

        tk.Label(
            voice_card,
            text="Respons AI:",
            font=("Segoe UI", 12, "bold"),
            bg="#1a1e2a",
            fg="#e6eef3"
        ).pack(anchor=tk.W, pady=(15, 5))

        self.response_text = scrolledtext.ScrolledText(
            voice_card,
            height=10,
            font=("Segoe UI", 10),
            bg="#0a0e1a",
            fg="#e6eef3",
            insertbackground="#6EE7B7",
            relief=tk.FLAT,
            bd=0,
            wrap=tk.WORD
        )
        self.response_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        settings_frame = tk.Frame(voice_card, bg="#1a1e2a")
        settings_frame.pack(fill=tk.X, pady=10)

        tk.Label(
            settings_frame,
            text="IP Arduino:",
            font=("Segoe UI", 10),
            bg="#1a1e2a",
            fg="#99a6b3"
        ).pack(side=tk.LEFT, padx=5)

        self.ip_entry = tk.Entry(
            settings_frame,
            font=("Segoe UI", 10),
            bg="#0a0e1a",
            fg="#e6eef3",
            insertbackground="#6EE7B7",
            relief=tk.FLAT,
            bd=0
        )
        self.ip_entry.insert(0, ARDUINO_IP)
        self.ip_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        update_ip_btn = tk.Button(
            settings_frame,
            text="Update",
            font=("Segoe UI", 9),
            bg="#60a5fa",
            fg="white",
            activebackground="#3b82f6",
            relief=tk.FLAT,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self.update_arduino_ip
        )
        update_ip_btn.pack(side=tk.LEFT, padx=5)

    def draw_mic_icon(self):

        width = 180
        height = 180
        scale = 2
        img = Image.new('RGBA', (width * scale, height * scale), (26, 30, 42, 255))
        draw = ImageDraw.Draw(img)
        center_x = (width * scale) // 2
        center_y = (height * scale) // 2

        if self.is_listening:
            for i in range(3):
                pulse_offset = (self.mic_pulse_radius + i * 15) % 50
                pulse_radius = (50 + pulse_offset) * scale
                alpha_factor = 1.0 - (pulse_offset / 50.0)
                if alpha_factor > 0:
                    intensity = int(255 * alpha_factor)
                    if intensity > 200:
                        color = (255, 68, 68, intensity)
                    elif intensity > 100:
                        color = (255, 102, 102, intensity)
                    else:
                        color = (255, 136, 136, intensity)
                    draw.ellipse(
                        [center_x - pulse_radius, center_y - pulse_radius,
                         center_x + pulse_radius, center_y + pulse_radius],
                        outline=color, width=2 * scale
                    )
            
            mic_color = (239, 68, 68, 255)
            draw.rounded_rectangle([center_x - 16*scale, center_y - 35*scale, center_x + 16*scale, center_y + 15*scale], radius=15*scale, fill=mic_color)
            draw.arc([center_x - 30*scale, center_y - 15*scale, center_x + 30*scale, center_y + 25*scale], start=0, end=180, fill=mic_color, width=5*scale)
            draw.rectangle([center_x - 3*scale, center_y + 25*scale, center_x + 3*scale, center_y + 45*scale], fill=mic_color)
            draw.rectangle([center_x - 15*scale, center_y + 45*scale, center_x + 15*scale, center_y + 50*scale], fill=mic_color)
        else:
            mic_color = (110, 231, 183, 255)
            draw.rounded_rectangle([center_x - 16*scale, center_y - 35*scale, center_x + 16*scale, center_y + 15*scale], radius=15*scale, fill=mic_color)
            draw.arc([center_x - 30*scale, center_y - 15*scale, center_x + 30*scale, center_y + 25*scale], start=0, end=180, fill=mic_color, width=5*scale)
            draw.rectangle([center_x - 3*scale, center_y + 25*scale, center_x + 3*scale, center_y + 45*scale], fill=mic_color)
            draw.rectangle([center_x - 15*scale, center_y + 45*scale, center_x + 15*scale, center_y + 50*scale], fill=mic_color)

        img = img.resize((width, height), Image.Resampling.LANCZOS)
        self.mic_photo = ImageTk.PhotoImage(img)
        self.mic_canvas.delete("all")
        self.mic_canvas.create_image(width//2, height//2, image=self.mic_photo)

    def start_animations(self):

        def animate():
            if self.is_listening:
                self.mic_pulse_radius = (self.mic_pulse_radius + 3) % 50
                self.draw_mic_icon()
            else:
                if self.mic_pulse_radius > 0:
                    self.mic_pulse_radius = 0
                    self.draw_mic_icon()
            self.root.after(50, animate)
        animate()

    def update_arduino_ip(self):

        global ARDUINO_IP
        ARDUINO_IP = self.ip_entry.get()
        self.add_response(f"IP Arduino diubah menjadi: {ARDUINO_IP}")

    def format_time(self, seconds):

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{int(hours):02d}:{int(minutes):02d}:{int(secs):02d}"

    def toggle_listening(self):

        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self):

        if self.is_speaking:
            return

        if self.microphone is None:
            messagebox.showerror("Error", "Microphone tidak tersedia.")
            return

        self.last_detected_text = None
        self.current_audio = None

        self.is_listening = True
        self.mic_button.config(text="🔴 Mendengarkan...", bg="#ef4444", fg="white")
        self.status_label.config(text="Listening...", fg="#ffb86b")
        self.draw_mic_icon()

        threading.Thread(target=self.listen_loop_optimized, daemon=True).start()

    def stop_listening(self):

        self.is_listening = False
        self.mic_button.config(text="🎤 Tekan untuk Bicara", bg="#6EE7B7", fg="#04201a")
        self.status_label.config(text="Ready", fg="#99a6b3")
        self.draw_mic_icon()

        if self.last_detected_text and self.last_detected_text.strip():
            text_to_send = self.last_detected_text.strip()
            if len(text_to_send) >= 2:

                saved_text = text_to_send

                self.last_detected_text = None
                self.current_audio = None

                self.root.after(0, lambda: self.add_response(f"📤 Mengirim perintah: {saved_text}"))
                self.root.after(0, lambda: self.process_voice_command(saved_text))
        else:

            self.last_detected_text = None
            self.current_audio = None

    def listen_loop_optimized(self):

        if self.microphone is None:
            try:
                self.root.after(0, lambda: self.add_response("❌ Microphone tidak tersedia"))
                self.root.after(0, self.stop_listening)
            except:
                pass
            return

        try:

            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                if self.recognizer.energy_threshold < 250:
                    self.recognizer.energy_threshold = 300

            while self.is_listening:
                try:
                    with self.microphone as source:

                        audio = self.recognizer.listen(
                            source,
                            timeout=0.5,
                            phrase_time_limit=5
                        )

                        self.current_audio = audio

                    lang = SPEECH_LANGUAGE if 'SPEECH_LANGUAGE' in globals() else "id-ID"

                    try:

                        text = self.recognizer.recognize_google(
                            audio,
                            language=lang,
                            show_all=False
                        )

                        if text and text.strip():
                            text = text.strip()
                            if len(text) >= 2:
                                self.last_detected_text = text

                                try:
                                    self.root.after(0, lambda t=text: self.add_response(f"🎤 Terdeteksi: {t} (tekan tombol lagi untuk kirim)"))
                                except:
                                    pass

                    except sr.UnknownValueError:

                        pass
                    except sr.RequestError:

                        pass
                    except Exception:

                        pass

                except sr.WaitTimeoutError:

                    if not self.is_listening:
                        break
                    continue
                except Exception as e:

                    if not self.is_listening:
                        break
                    continue

        except Exception as e:
            try:
                self.root.after(0, lambda err=str(e): self.add_response(f"Microphone error: {err}"))
            except:
                pass
            try:
                if self.is_listening:
                    self.root.after(0, self.stop_listening)
            except:
                pass

    def process_voice_command(self, text):

        self.add_response(f"🎤 Anda: {text}")
        self.status_label.config(text="Processing...", fg="#60a5fa")

        command_lower = text.lower().strip()

        executed = False

        if re.search(r'\b(mati|stop|nonaktif|disable).*auto\b', command_lower) or \
           re.search(r'\bauto.*mati|stop|nonaktif\b', command_lower):

            data = self.arduino_data
            if data and not data.get('wifi', False):
                self.add_response("⚠️ Tidak bisa mematikan auto mode saat offline (tidak ada jaringan)")
                self.add_response("Auto mode HARUS aktif saat offline untuk memastikan AC tetap berfungsi secara lokal.")
                self.speak("Mode auto tidak bisa dimatikan saat offline. Auto mode harus aktif saat tidak terhubung ke jaringan")
                executed = True
            else:

                self.disable_auto_mode(silent=False)
                self.speak("Mode auto telah dimatikan")
                executed = True

        elif re.search(r'\b(set|setel|atur|ubah|ganti|pasang).*(threshold|suhu|temperatur).*(auto|otomatis)\b', command_lower) or \
             re.search(r'\b(threshold|suhu|temperatur).*(auto|otomatis).*(on|nyala|off|mati)\b', command_lower) or \
             re.search(r'\b(set|setel|atur).*suhu.*(on|nyala).*\d+.*(off|mati).*\d+\b', command_lower) or \
             re.search(r'\bthreshold.*\d+.*\d+\b', command_lower):

            suhu_on = None
            suhu_off = None

            on_match = re.search(r'\b(on|nyala)\s+(\d+\.?\d*)', command_lower)
            off_match = re.search(r'\b(off|mati)\s+(\d+\.?\d*)', command_lower)

            if on_match and off_match:
                try:
                    suhu_on = float(on_match.group(2))
                    suhu_off = float(off_match.group(2))
                except:
                    pass

            if suhu_on is None or suhu_off is None:
                numbers = re.findall(r'\d+\.?\d*', text)
                if len(numbers) >= 2:
                    try:
                        suhu_on = float(numbers[0])
                        suhu_off = float(numbers[1])
                    except:
                        pass
                elif len(numbers) == 1:
                    try:
                        suhu_on = float(numbers[0])
                        suhu_off = suhu_on - 1.0
                    except:
                        pass

            if suhu_on is None or suhu_off is None:

                on_pattern = re.search(r'\b(on|nyala|nyalakan)\s+(\d+\.?\d*)', command_lower)
                off_pattern = re.search(r'\b(off|mati|matikan)\s+(\d+\.?\d*)', command_lower)

                if on_pattern:
                    try:
                        suhu_on = float(on_pattern.group(2))
                    except:
                        pass
                if off_pattern:
                    try:
                        suhu_off = float(off_pattern.group(2))
                    except:
                        pass

                if suhu_on is not None and suhu_off is None:
                    suhu_off = suhu_on - 1.0
                elif suhu_off is not None and suhu_on is None:
                    suhu_on = suhu_off + 1.0

            if suhu_on is not None and suhu_off is not None:
                if suhu_on > suhu_off:
                    self.set_auto_mode_only(suhu_on, suhu_off, silent=False)
                    self.speak(f"Threshold suhu auto diset. ON {suhu_on} derajat, OFF {suhu_off} derajat")
                    executed = True
                else:
                    self.add_response("❌ Suhu ON harus lebih besar dari suhu OFF.")
                    self.speak("Maaf, suhu ON harus lebih besar dari suhu OFF.")
                    executed = True
            else:
                self.add_response("❌ Mohon sebutkan suhu ON dan suhu OFF.")
                self.speak("Mohon sebutkan suhu ON dan suhu OFF, contoh: set threshold on 30 off 29")
                executed = True

        elif re.search(r'\b(aktif|enable|on|nyala).*auto\b', command_lower) or \
             re.search(r'\bauto.*(aktif|enable|on|nyala)\b', command_lower) or \
             re.search(r'\b(mode|modus)\s+auto\b', command_lower) or \
             command_lower in ["auto", "otomatis", "mode auto"]:

            self.enable_auto_mode_only(silent=False)
            self.speak("Mode auto telah diaktifkan")
            executed = True

        elif re.search(r'\btimer\b', command_lower) or \
             re.search(r'\bset\s+timer\b', command_lower) or \
             re.search(r'\bpasang\s+timer\b', command_lower) or \
             re.search(r'\baktifkan\s+timer\b', command_lower):

            h = 0
            m = 0
            s = 0

            hours = re.search(r'(\d+)\s*(jam|hour|h)\b', command_lower)
            minutes = re.search(r'(\d+)\s*(menit|minute|m)\b', command_lower)
            seconds = re.search(r'(\d+)\s*(detik|second|s)\b', command_lower)

            if hours:
                h = int(hours.group(1))
            if minutes:
                m = int(minutes.group(1))
            if seconds:
                s = int(seconds.group(1))

            if h == 0 and m == 0 and s == 0:
                numbers = re.findall(r'\d+', text)
                if len(numbers) >= 2:

                    h = int(numbers[0])
                    m = int(numbers[1])
                elif len(numbers) == 1:
                    num = int(numbers[0])
                    if num < 60:

                        s = num
                    elif num < 100:

                        m = num
                    else:

                        h = num

            if h > 0 or m > 0 or s > 0:
                self.start_timer(h, m, s, silent=False)
                duration = self.format_time(h * 3600 + m * 60 + s)
                self.speak(f"Timer dimulai selama {duration}")
                executed = True
            else:
                self.add_response("❌ Mohon sebutkan durasi timer (jam, menit, atau detik).")
                self.speak("Mohon sebutkan durasi timer, contoh: timer 1 jam 30 menit")
                executed = True

        elif re.search(r'\b(nyala|hidup|aktif|buka|on|nyalakan|hidupkan|aktifkan).*ac\b', command_lower) or \
             re.search(r'\bac.*(nyala|hidup|aktif|buka|on)\b', command_lower) or \
             re.search(r'\b(turn\s+on|switch\s+on|power\s+on).*ac\b', command_lower) or \
             command_lower in ["nyalakan ac", "hidupkan ac", "aktifkan ac", "buka ac",
                              "ac nyala", "ac hidup", "ac aktif", "ac on", "ac nyalakan",
                              "ac hidupkan", "nyala", "hidup", "on"]:
            self.turn_ac_on(silent=False)
            self.speak("AC telah dinyalakan")
            executed = True

        elif re.search(r'\b(mati|padam|nonaktif|tutup|off|matikan|padamkan|nonaktifkan).*ac\b', command_lower) or \
             re.search(r'\bac.*(mati|padam|nonaktif|tutup|off)\b', command_lower) or \
             re.search(r'\b(turn\s+off|switch\s+off|power\s+off).*ac\b', command_lower) or \
             command_lower in ["matikan ac", "padamkan ac", "nonaktifkan ac", "tutup ac",
                              "ac mati", "ac padam", "ac nonaktif", "ac off", "ac matikan",
                              "ac padamkan", "mati", "padam", "off"]:
            self.turn_ac_off(silent=False)
            self.speak("AC telah dimatikan")
            executed = True

        if not executed:

            ac_state = self.get_ac_state_description()
            context = f"""Anda adalah asisten pintar untuk mengontrol Smart AC.
Status AC: {ac_state}

Perintah yang bisa dilakukan:
1. Nyalakan/matikan AC: "nyalakan AC", "matikan AC", "AC on", "AC off"
2. Set threshold auto: "set threshold on 30 off 29", "atur suhu auto 30 29"
3. Aktifkan/nonaktifkan auto mode: "aktifkan auto", "matikan auto"
4. Set timer: "timer 1 jam 30 menit", "timer 30 menit", "timer 2 jam"

Perintah user: "{text}"

Instruksi:
- Jika perintah meminta menyalakan AC, eksekusi: turn_ac_on()
- Jika perintah meminta mematikan AC, eksekusi: turn_ac_off()
- Jika perintah meminta set threshold suhu, eksekusi: set_auto_mode_only(suhu_on, suhu_off)
- Jika perintah meminta timer, eksekusi: start_timer(hours, minutes, seconds)
- Jika perintah meminta aktifkan auto mode, eksekusi: enable_auto_mode_only()
- Jika perintah meminta matikan auto mode, eksekusi: disable_auto_mode()

Berikan respons singkat dan jelas. JANGAN mengubah status AC jika perintah hanya tentang mode auto atau pengaturan suhu.
"""

            threading.Thread(target=self.call_gemini, args=(context, text), daemon=True).start()
        else:
            self.status_label.config(text="Ready", fg="#99a6b3")

    def call_gemini(self, context, user_text):

        try:
            if not self.gemini_model:
                raise ValueError("Gemini Model tidak diinisialisasi. Silakan isi GEMINI_API_KEY di berkas .env")

            strict_context = context + """

PENTING:
- JANGAN menyalakan atau mematikan AC kecuali perintah JELAS meminta untuk menyalakan/mematikan AC.
- Jika perintah hanya tentang mode auto, pengaturan suhu, atau informasi, JANGAN mengubah status AC (ON/OFF).
- Mode auto hanya mengatur threshold suhu, bukan langsung mengubah status AC.
- Hanya eksekusi kontrol AC jika perintah eksplisit seperti "nyalakan AC" atau "matikan AC".
- Untuk perintah setting suhu ON/OFF atau mengaktifkan/menonaktifkan auto mode, hanya konfirmasi aksi dan sebutkan "pengaturan tersimpan ke EEPROM".
"""

            prompt = f"{strict_context}\n\nPerintah: {user_text}"
            response = self.gemini_model.generate_content(prompt)
            ai_response = response.text.strip()

            ai_lower = ai_response.lower()
            command_lower = user_text.lower()

            if re.search(r'\b(nyala|hidup|aktif).*ac\b', command_lower) and \
               not any(word in command_lower for word in ["auto", "otomatis", "mode", "suhu", "set", "setel"]):
                self.turn_ac_on(silent=False)
            elif re.search(r'\b(mati|padam|nonaktif).*ac\b', command_lower) and \
                 not any(word in command_lower for word in ["auto", "otomatis", "mode", "suhu", "set", "setel"]):
                self.turn_ac_off(silent=False)

            if "mode auto" in ai_lower or "suhu on" in ai_lower or "suhu off" in ai_lower:
                if "tersimpan ke eeprom" not in ai_lower:
                    ai_response += "\nPengaturan tersimpan ke EEPROM."

            self.root.after(0, lambda: self.add_response(f"🤖 AI: {ai_response}"))
            self.root.after(0, lambda: self.speak(ai_response))
            self.root.after(0, lambda: self.status_label.config(text="Ready", fg="#99a6b3"))
        except Exception as e:
            error_msg = f"Error calling Gemini: {e}"
            self.root.after(0, lambda: self.add_response(error_msg))
            self.root.after(0, lambda: self.status_label.config(text="Error", fg="#ef4444"))

    def speak(self, text):

        def speak_thread():
            try:
                self.is_speaking = True
                tts = gTTS(text=text, lang=TTS_LANGUAGE, slow=False)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                temp_file.close()

                tts.save(temp_file.name)

                try:
                    pygame.mixer.music.load(temp_file.name)
                    pygame.mixer.music.play()

                    while pygame.mixer.music.get_busy() and self.is_speaking:
                        time.sleep(0.1)

                    if not self.is_speaking:
                        pygame.mixer.music.stop()

                except Exception as e:
                    print(f"Audio playback error: {e}")

                try:
                    os.unlink(temp_file.name)
                except:
                    pass

                self.is_speaking = False
            except Exception as e:
                print(f"TTS error: {e}")
                self.is_speaking = False

        threading.Thread(target=speak_thread, daemon=True).start()

    def add_response(self, text):

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.response_text.insert(tk.END, f"[{timestamp}] {text}\n")
        self.response_text.see(tk.END)

    def get_arduino_data(self):

        try:

            url = f"http://{ARDUINO_IP}/data?_t={int(time.time() * 1000)}"

            response = requests.get(url, timeout=1.0, headers={'Cache-Control': 'no-cache'})
            if response.status_code == 200:
                data = response.json()

                if 'seq' in data and 'ts' in data:
                    return data
        except requests.exceptions.Timeout:
            pass
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            pass
        return None

    def get_ac_state_description(self):

        data = self.arduino_data
        if not data:
            return "Status tidak tersedia"

        suhu = data.get('suhu_sm', data.get('suhu', -1))
        hum = data.get('hum_sm', data.get('hum', -1))
        relay = data.get('relay', False)
        auto = data.get('auto', False)
        timer_active = data.get('timer_active', False)
        timer_remain = data.get('timer_remain_s', 0)
        suhu_on = data.get('suhu_on', 31.0)
        suhu_off = data.get('suhu_off', 30.0)

        desc = f"Suhu ruangan: {suhu}°C, Kelembapan: {hum}%\n"
        desc += f"AC: {'ON' if relay else 'OFF'}\n"
        desc += f"Mode: {'AUTO' if auto else ('TIMER' if timer_active else 'MANUAL')}\n"
        if timer_active:
            desc += f"Timer tersisa: {self.format_time(timer_remain)}\n"
        if auto:
            desc += f"Threshold Auto: ON {suhu_on}°C / OFF {suhu_off}°C"
        return desc

    def start_data_polling(self):

        def poll_loop():
            last_seq = 0
            failed_requests = 0
            was_offline = False

            while True:
                data = self.get_arduino_data()
                if data:

                    if was_offline:
                        was_offline = False
                        failed_requests = 0

                        self.root.after(0, lambda: self.add_response("🟢 Arduino kembali online - Status diperbarui"))

                        self.root.after(0, self.update_ui)

                    current_seq = data.get('seq', 0)
                    if current_seq >= last_seq:
                        self.arduino_data = data
                        last_seq = current_seq
                        self.root.after(0, self.update_ui)
                        self.last_update = time.time()
                        failed_requests = 0

                else:
                    failed_requests += 1

                    if failed_requests >= 3:
                        if not was_offline:
                            was_offline = True
                            self.root.after(0, lambda: self.add_response("🔴 Arduino offline - Menunggu koneksi kembali..."))
                        self.root.after(0, self.update_ui_offline)
                    else:

                        if self.arduino_data:
                            self.root.after(0, self.update_ui)

                time.sleep(POLL_INTERVAL)

        threading.Thread(target=poll_loop, daemon=True).start()

    def update_ui(self):

        data = self.arduino_data
        if not data:
            return

        suhu = data.get('suhu_sm', data.get('suhu', -1))
        if suhu != -1 and suhu > -0.5:
            old_text = self.temp_label.cget("text")
            new_text = f"{suhu:.1f}°C"
            if old_text != new_text:

                if suhu >= 32:
                    color = "#ef4444"
                elif suhu >= 28:
                    color = "#ffb86b"
                else:
                    color = "#6EE7B7"
                self.temp_label.config(text=new_text, fg=color)
        else:
            self.temp_label.config(text="--°C", fg="#6EE7B7")

        hum = data.get('hum_sm', data.get('hum', -1))
        if hum != -1 and hum >= 0:
            self.hum_label.config(text=f"Kelembapan: {int(hum)}%")
        else:
            self.hum_label.config(text="Kelembapan: --%")

        relay = data.get('relay', False)
        old_ac_text = self.ac_state_label.cget("text")
        new_ac_text = "AC: ON" if relay else "AC: OFF"
        if old_ac_text != new_ac_text:
            self.ac_state_label.config(text=new_ac_text, fg="#6EE7B7" if relay else "#ef4444")

        auto = data.get('auto', False)
        timer_active = data.get('timer_active', False)
        wifi_status = data.get('wifi', False)

        if timer_active:
            timer_remain = data.get('timer_remain_s', 0)
            self.mode_label.config(text="Mode: TIMER")
            if timer_remain > 0:
                time_str = self.format_time(timer_remain)
                self.timer_label.config(text=f"⏱ Timer: {time_str}", fg="#ffb86b")
            else:
                self.timer_label.config(text="")
        elif auto:
            mode_text = "Mode: AUTO"

            if not wifi_status:
                mode_text += " (Offline Lokal)"
            self.mode_label.config(text=mode_text)
            self.timer_label.config(text="")
        else:
            self.mode_label.config(text="Mode: MANUAL")
            self.timer_label.config(text="")

        cooldown_remain = data.get('cooldown_remain_s', 0)
        if cooldown_remain > 0:
            time_str = self.format_time(cooldown_remain)
            self.cooldown_label.config(text=f"⏳ Cooldown: {time_str}", fg="#60a5fa")
        else:
            self.cooldown_label.config(text="")

        suhu_on = data.get('suhu_on', 31.0)
        suhu_off = data.get('suhu_off', 30.0)

        if self.root.focus_get() != self.suhu_on_entry:
            current_on = self.suhu_on_entry.get()

            if not current_on or abs(float(current_on or 0) - suhu_on) > 0.05:
                self.suhu_on_entry.delete(0, tk.END)
                self.suhu_on_entry.insert(0, f"{suhu_on:.1f}")

        if self.root.focus_get() != self.suhu_off_entry:
            current_off = self.suhu_off_entry.get()

            if not current_off or abs(float(current_off or 0) - suhu_off) > 0.05:
                self.suhu_off_entry.delete(0, tk.END)
                self.suhu_off_entry.insert(0, f"{suhu_off:.1f}")

        wifi = data.get('wifi', False)
        if wifi:
            self.status_dot.config(fg="#7ee787")
            self.status_label.config(text="Online", fg="#7ee787")
        else:
            self.status_dot.config(fg="#ffb86b")

            if auto:
                self.status_label.config(text="Offline - Auto Mode (Lokal)", fg="#ffb86b")
            else:
                self.status_label.config(text="Offline", fg="#ffb86b")

    def update_ui_offline(self):

        self.status_dot.config(fg="#ef4444")
        self.status_label.config(text="Offline", fg="#ef4444")

        if self.arduino_data:

            auto = self.arduino_data.get('auto', False)
            if auto:
                self.mode_label.config(text="Mode: AUTO (Offline Lokal)", fg="#ffb86b")
            else:
                self.mode_label.config(text="Mode: MANUAL (Offline)", fg="#ffb86b")
        else:
            self.mode_label.config(text="Mode: --", fg="#99a6b3")
            self.temp_label.config(text="--°C", fg="#6EE7B7")
            self.hum_label.config(text="Kelembapan: --%", fg="#99a6b3")
            self.ac_state_label.config(text="AC: OFF", fg="#ef4444")
            self.timer_label.config(text="")
            self.cooldown_label.config(text="")
            self.suhu_on_entry.delete(0, tk.END)
            self.suhu_on_entry.insert(0, "31.0")
            self.suhu_off_entry.delete(0, tk.END)
            self.suhu_off_entry.insert(0, "30.0")

    def turn_ac_on(self, silent=False):

        try:
            url = f"http://{ARDUINO_IP}/on?_t={int(time.time())}"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                try:
                    result = response.json()
                    message = result.get('message', 'AC ON - Data tersimpan ke EEPROM')
                    eeprom_saved = result.get('eeprom_saved', True)
                except:
                    message = "AC ON - Data tersimpan ke EEPROM"
                    eeprom_saved = True

                if not silent:
                    self.add_response("✅ AC dinyalakan")
                    if eeprom_saved:
                        self.add_response(f"💾 {message}")
                    else:
                        self.add_response("💾 Status tersimpan ke EEPROM")
                return True
        except Exception as e:
            if not silent:
                self.add_response(f"❌ Error: {e}")
            return False

    def turn_ac_off(self, silent=False):

        try:
            url = f"http://{ARDUINO_IP}/off?_t={int(time.time())}"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                try:
                    result = response.json()
                    message = result.get('message', 'AC OFF - Data tersimpan ke EEPROM')
                    eeprom_saved = result.get('eeprom_saved', True)
                except:
                    message = "AC OFF - Data tersimpan ke EEPROM"
                    eeprom_saved = True

                if not silent:
                    self.add_response("✅ AC dimatikan")
                    if eeprom_saved:
                        self.add_response(f"💾 {message}")
                    else:
                        self.add_response("💾 Status tersimpan ke EEPROM")
                return True
        except Exception as e:
            if not silent:
                self.add_response(f"❌ Error: {e}")
            return False

    def set_auto_mode_only(self, suhu_on, suhu_off, silent=False):

        try:

            url = f"http://{ARDUINO_IP}/setauto?on={suhu_on:.1f}&off={suhu_off:.1f}&_t={int(time.time())}"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                try:
                    result = response.json()
                    message = result.get('message', 'Threshold auto tersimpan ke EEPROM')
                    eeprom_saved = result.get('eeprom_saved', True)
                except:
                    message = "Threshold auto tersimpan ke EEPROM"
                    eeprom_saved = True

                if not silent:
                    self.add_response(f"✅ Pengaturan suhu auto tersimpan: ON {suhu_on:.1f}°C / OFF {suhu_off:.1f}°C")
                    if eeprom_saved:
                        self.add_response(f"💾 {message} (tahan power loss)")
                    else:
                        self.add_response("💾 Mode auto diaktifkan dan data tersimpan permanen (tahan power loss)")

                time.sleep(0.3)
                return True
        except Exception as e:
            if not silent:
                self.add_response(f"❌ Error mengatur suhu auto: {e}")
            return False

    def enable_auto_mode_only(self, silent=False):

        try:
            data = self.arduino_data

            suhu_on = data.get('suhu_on', 31.0) if data else 31.0
            suhu_off = data.get('suhu_off', 30.0) if data else 30.0

            url = f"http://{ARDUINO_IP}/setauto?on={suhu_on:.1f}&off={suhu_off:.1f}&_t={int(time.time())}"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                try:
                    result = response.json()
                    message = result.get('message', 'Threshold auto tersimpan ke EEPROM')
                    eeprom_saved = result.get('eeprom_saved', True)
                except:
                    message = "Threshold auto tersimpan ke EEPROM"
                    eeprom_saved = True

                if not silent:
                    self.add_response(f"✅ Mode auto diaktifkan dengan threshold: ON {suhu_on:.1f}°C / OFF {suhu_off:.1f}°C")
                    if eeprom_saved:
                        self.add_response(f"💾 {message} (tahan power loss)")
                    else:
                        self.add_response("💾 Pengaturan tersimpan ke EEPROM")
                time.sleep(0.3)
                return True
        except Exception as e:
            if not silent:
                self.add_response(f"❌ Error mengaktifkan mode auto: {e}")
            return False

    def disable_auto_mode(self, silent=False):

        try:

            data = self.arduino_data
            if data and not data.get('wifi', False):
                if not silent:
                    self.add_response("⚠️ Tidak bisa mematikan auto mode saat offline (tidak ada jaringan).")
                    self.add_response("Auto mode HARUS aktif saat offline untuk memastikan AC tetap berfungsi secara lokal.")
                    self.speak("Mode auto tidak bisa dimatikan saat offline. Auto mode harus aktif saat tidak terhubung ke jaringan.")
                return False

            url = f"http://{ARDUINO_IP}/autooff?_t={int(time.time())}"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                result = response.json()
                if result.get('success', False):
                    message = result.get('message', 'Auto mode dimatikan - Data tersimpan ke EEPROM')
                    eeprom_saved = result.get('eeprom_saved', True)

                    if not silent:
                        self.add_response("✅ Mode auto dimatikan")
                        if eeprom_saved:
                            self.add_response(f"💾 {message}")
                        else:
                            self.add_response("💾 Status tersimpan ke EEPROM")
                    time.sleep(0.3)
                    return True
                else:
                    if not silent:
                        self.add_response("⚠️ Mode auto tidak bisa dimatikan saat offline")
                        self.add_response("Auto mode harus aktif saat tidak terhubung ke jaringan")
                    return False
        except Exception as e:
            if not silent:
                self.add_response(f"❌ Error mematikan mode auto: {e}")
            return False

    def start_timer(self, hours=0, minutes=0, seconds=0, silent=False):

        try:
            url = f"http://{ARDUINO_IP}/timer?h={hours}&m={minutes}&s={seconds}&_t={int(time.time())}"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                try:
                    result = response.json()
                    message = result.get('message', 'Timer tersimpan ke EEPROM')
                    eeprom_saved = result.get('eeprom_saved', True)
                except:
                    message = "Timer tersimpan ke EEPROM"
                    eeprom_saved = True

                if not silent:
                    duration = self.format_time(hours * 3600 + minutes * 60 + seconds)
                    self.add_response(f"✅ Timer dimulai: {duration}")
                    if eeprom_saved:
                        self.add_response(f"💾 {message} (tahan power loss)")
                    else:
                        self.add_response("💾 Timer tersimpan ke EEPROM")
                return True
        except Exception as e:
            if not silent:
                self.add_response(f"❌ Error: {e}")
            return False

    def start_timer_from_ui(self):

        try:
            h = int(self.timer_h_entry.get() or 0)
            m = int(self.timer_m_entry.get() or 0)
            s = int(self.timer_s_entry.get() or 0)
            total = h * 3600 + m * 60 + s
            if total > 0:
                self.start_timer(h, m, s, silent=False)
                duration = self.format_time(total)
                self.speak(f"Timer dimulai selama {duration}")
            else:
                messagebox.showwarning("Warning", "Masukkan durasi timer (jam, menit, atau detik)")
        except ValueError:
            messagebox.showerror("Error", "Masukkan angka yang valid")

    def save_suhu_settings(self):

        try:
            suhu_on = float(self.suhu_on_entry.get())
            suhu_off = float(self.suhu_off_entry.get())
            if suhu_on > suhu_off:

                self.set_auto_mode_only(suhu_on, suhu_off, silent=False)
                self.speak(f"Pengaturan suhu auto tersimpan. ON {suhu_on} derajat, OFF {suhu_off} derajat")
            else:
                messagebox.showerror("Error", "Suhu ON harus lebih besar dari suhu OFF")
        except ValueError:
            messagebox.showerror("Error", "Masukkan angka yang valid")

    def set_cooldown(self, seconds):

        try:
            url = f"http://{ARDUINO_IP}/setcooldown?sec={seconds}&_t={int(time.time())}"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                try:
                    result = response.json()
                    message = result.get('message', 'Cooldown tersimpan ke EEPROM')
                    eeprom_saved = result.get('eeprom_saved', True)
                except:
                    message = "Cooldown tersimpan ke EEPROM"
                    eeprom_saved = True

                self.add_response(f"✅ Cooldown diset {seconds} detik")
                if eeprom_saved:
                    self.add_response(f"💾 {message} (tahan power loss)")
                else:
                    self.add_response("💾 Cooldown tersimpan ke EEPROM")
                self.speak(f"Cooldown diset {seconds} detik")
        except Exception as e:
            self.add_response(f"❌ Error: {e}")

def main():
    root = tk.Tk()
    app = VoiceController(root)

    def on_closing():

        try:

            if hasattr(app, 'is_listening'):
                app.is_listening = False

            if hasattr(app, 'is_speaking'):
                app.is_speaking = False

            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.quit()
            except:
                pass

        except Exception as e:

            pass

        try:
            root.quit()
            root.destroy()
        except:

            try:
                import os
                os._exit(0)
            except:
                pass

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
