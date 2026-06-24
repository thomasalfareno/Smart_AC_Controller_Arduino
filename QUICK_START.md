# 🚀 Quick Start Guide

Panduan jalaur cepat (*fast-track*) untuk menjalankan **Smart AC Voice Controller** di komputer Anda tanpa harus membaca seluruh dokumentasi teknis.

---

## 1. Setup Arduino (Hardware)

1. Buka `Smart_AC_Final.ino` di Arduino IDE.
2. Edit WiFi `ssid` dan `password` Anda.
3. Upload kode ke **Arduino Uno R4 WiFi**.
4. Buka *Serial Monitor* (Baud: 115200) dan **catat alamat IP** yang muncul (cth: `192.168.1.100`).

---

## 2. Instalasi Dependensi Python

Jalankan skrip instalasi otomatis di terminal proyek Anda:

**Windows:**
```bash
install.bat
```

**Linux/Mac:**
```bash
chmod +x install.sh
./install.sh
```

---

## 3. Konfigurasi Variabel Lingkungan

Installer di atas akan menghasilkan file bernama **`.env`**. File ini menentukan bagaimana aplikasi Anda berkomunikasi dengan Gemini dan Arduino.

Buka file `.env` dan masukkan API Key Gemini Anda (dapatkan secara gratis di [Google AI Studio](https://aistudio.google.com/)) serta IP Arduino yang Anda dapatkan di Langkah 1.

![Env Config Animasi](ASSTMD/env_config.svg)

---

## 4. Nyalakan Aplikasi

Jalankan perintah ini di terminal:

```bash
python smart_ac_voice_controller.py
```

Selamat! Aplikasi akan menampilkan layar berdesain premium. Tekan tombol **"🎤 Tekan untuk Bicara"** dan mulailah mengucapkan sesuatu seperti: *"Tolong nyalakan AC dong"*.

---

## Membutuhkan Bantuan Lebih Lanjut?

- **PyAudio Error?** Jika menggunakan Windows, ketik: `pipwin install pyaudio`.
- **Tidak ada respon suara?** Cek izin (*permission*) privasi mikrofon di Settings Windows/Mac Anda.
- **Baca panduan utuhnya** di [README.md](README.md) dan [README_ARDUINO.md](README_ARDUINO.md).
