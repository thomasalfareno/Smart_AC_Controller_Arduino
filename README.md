# Smart AC Voice Controller 🎤 🤖

Aplikasi Python modern dengan antarmuka grafis premium untuk mengontrol Smart AC melalui suara menggunakan AI Gemini. Proyek ini memadukan kemudahan kontrol berbasis Voice (Natural Language) dan sistem tertanam (Embedded System) menggunakan Arduino Uno R4 WiFi.

## Fitur Utama

- 🎤 **Voice Control**: Kontrol AC hanya melalui perintah suara natural.
- 🤖 **AI Gemini Integration**: Memahami konteks kalimat menggunakan Google Gemini AI.
- 🔊 **Text-to-Speech**: AI akan merespons melalui speaker Anda.
- 📊 **Real-time Monitoring**: Lacak suhu, kelembapan, dan status AC secara live.
- 🎨 **Modern & Premium UI**: Desain Glassmorphism gelap, micro-animations, dan dynamic glowing icons.
- 🔌 **Arduino Integration**: Terhubung tanpa kabel (wireless) via Web API ke Arduino R4.

---

## Panduan Instalasi (Python App)

Aplikasi Python ini memerlukan beberapa pustaka (*library*) dan file konfigurasi. Kami menyediakan sistem otomatis (*installer*) untuk mempermudah Anda.

### 1. Instalasi Menggunakan Installer Otomatis (Direkomendasikan)

Untuk memulai instalasi otomatis, jalankan file instalasi sesuai sistem operasi Anda di dalam terminal.

![Setup Terminal Windows](ASSTMD/setup_terminal.svg)

**Windows:**
```bash
./install.bat
```

**Linux/Mac:**

![Setup Terminal Linux](ASSTMD/setup_terminal_linux.svg)

```bash
chmod +x install.sh
./install.sh
```

> [!TIP]
> Jika PyAudio gagal di Windows, installer otomatis akan menggunakan `pipwin` untuk memperbaikinya tanpa campur tangan manual.

### 2. Konfigurasi Variabel (`.env`)

Setelah instalasi selesai, sistem akan membuat file `.env` (dari salinan `.env.example`). Anda **harus** mengisi variabel ini dengan nilai Anda sendiri.

![Env Config](ASSTMD/env_config.svg)

Buka file `.env` dengan editor teks kesukaan Anda, lalu isi:
```env
# 1. API Key Gemini dari Google AI Studio
GEMINI_API_KEY="AIzaSyB-XXXXXXXXXXXXXXXXXXXXX"

# 2. IP Arduino dari Serial Monitor (Lihat panduan Arduino)
ARDUINO_IP="192.168.1.100"
```

> [!CAUTION]
> Jangan bagikan file `.env` Anda ke publik, karena berisi kunci rahasia (API Key).

---

## Panduan Setup Arduino (Hardware)

Silakan baca panduan lengkap konfigurasi alat pada file khusus [README_ARDUINO.md](README_ARDUINO.md). Disana akan dijelaskan tata letak pin, perpustakaan pendukung, dan cara mengunggah kode `.ino`.

---

## Menjalankan Aplikasi

Setelah instalasi dan konfigurasi perangkat keras selesai, aplikasi siap untuk dijalankan:

```bash
python smart_ac_voice_controller.py
```

### Perintah Suara yang Didukung

Aplikasi dapat memahami instruksi luwes (*natural*), seperti:
1. **Dasar**: "Tolong nyalakan AC dong", "Matikan AC sekarang"
2. **Otomatis**: "Aktifkan mode auto, kalau suhu 32 nyalakan dan 30 matikan"
3. **Pewaktu**: "Setel timer 1 jam 30 menit"
4. **Informasi**: "Suhu ruangan saat ini berapa ya?"

---

## Troubleshooting Umum

> [!WARNING]
> Berikut adalah kendala yang paling sering terjadi dan cara mengatasinya:

1. **Microphone tidak merespons**: Pastikan Anda telah memberikan izin (*permission*) mikrofon pada setelan privasi OS Windows/Mac Anda.
2. **PyAudio Error di Linux**: Instal dependensi `portaudio19-dev` terlebih dahulu: `sudo apt install portaudio19-dev python3-pyaudio`.
3. **Pesan 'Konfigurasi Belum Lengkap' muncul**: Pastikan Anda sudah mengedit file `.env` dan menyimpannya. `GEMINI_API_KEY` dan `ARDUINO_IP` wajib diisi.
4. **Arduino Gagal Dihubungi**: Periksa ulang IP Address di `.env` agar sesuai dengan yang ada pada Serial Monitor Arduino.
