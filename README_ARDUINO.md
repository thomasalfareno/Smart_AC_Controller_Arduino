# Arduino Smart AC Controller - Setup Guide 🔧

Panduan instalasi perangkat keras (hardware) dan konfigurasi untuk **Arduino Uno R4 WiFi**. Proyek ini menggunakan arsitektur web-server ringan di dalam Arduino yang akan menerima perintah dari aplikasi Voice Control Anda.

## 🛠️ Persiapan Hardware

Siapkan komponen-komponen berikut dan hubungkan sesuai skematik:

1. **Arduino Uno R4 WiFi** (Board utama yang memiliki WiFi terintegrasi)
2. **DHT22 Sensor Suhu & Kelembapan** (atau DHT11)
   - Hubungkan pin Data sensor ke **Pin Digital 2** Arduino.
3. **Relay Module (1 Channel)**
   - Hubungkan pin kontrol Relay ke **Pin Digital 7** Arduino.
4. **LCD 16x2 dengan Modul I2C**
   - Hubungkan SDA (LCD) ke SDA Arduino (Pin A4 atau pin khusus SDA).
   - Hubungkan SCL (LCD) ke SCL Arduino (Pin A5 atau pin khusus SCL).
5. **Kabel Jumper & Power Supply** secukupnya.

---

## 💻 Pengaturan Arduino IDE

Sebelum memprogram Arduino, pastikan lingkungan *Arduino IDE* Anda sudah disiapkan dengan pustaka yang benar.

### Instalasi Pustaka (*Library*)

Buka menu `Tools` -> `Manage Libraries` (atau `Ctrl+Shift+I`) di Arduino IDE:
1. Cari dan instal **DHT sensor library** (oleh Adafruit). *Pastikan Anda juga menyetujui instalasi dependensi 'Adafruit Unified Sensor'.*
2. Cari dan instal **LiquidCrystal_I2C** (oleh Frank de Brabander).

*(Catatan: Pustaka `WiFiS3`, `EEPROM`, dan `Wire` sudah terpasang secara bawaan di core Arduino Uno R4 WiFi)*.

---

## 🔧 Edit Variabel Konfigurasi (`.ino`)

Buka file **`Smart_AC_Final.ino`** pada Arduino IDE Anda.

Agar Arduino bisa terhubung ke jaringan lokal dan merespons aplikasi Anda, Anda **WAJIB** mengganti variabel jaringan (SSID dan Password) WiFi rumah/kantor Anda.

![Arduino Setup](ASSTMD/arduino_setup.svg)

Cari bagian atas kode:
```cpp
// ==========================================
// KONFIGURASI WIFI
// ==========================================
const char* ssid = "NAMA_WIFI_ANDA";      // Ganti dengan nama WiFi Anda (cth: "Home_Network_5G")
const char* password = "PASSWORD_WIFI";    // Ganti dengan kata sandi WiFi Anda
```

> [!CAUTION]
> Pastikan jaringan WiFi Anda menggunakan frekuensi **2.4 GHz**. Arduino Uno R4 WiFi tidak dapat terhubung ke frekuensi 5 GHz.

---

## 🚀 Mengunggah (Upload) Program

1. Colokkan Arduino ke komputer menggunakan kabel USB-C.
2. Di Arduino IDE, pilih board: **Tools → Board → Arduino UNO R4 WiFi**.
3. Pilih port yang sesuai: **Tools → Port → COMx** (Windows) atau `/dev/ttyUSBx` (Linux/Mac).
4. Tekan tombol **Upload** (ikon panah ke kanan) dan tunggu hingga pesan *Done Uploading* muncul.

---

## 📡 Memverifikasi IP Address

Agar aplikasi Voice Control di komputer bisa "mengobrol" dengan Arduino, Anda perlu tahu alamat IP-nya.

1. Buka **Serial Monitor** di Arduino IDE (`Tools` -> `Serial Monitor`).
2. Pastikan pengaturan *Baud Rate* di pojok kanan bawah adalah **115200**.
3. Anda akan melihat log seperti ini:
   ```text
   Memulai...
   Connecting to WiFi...
   WiFi connected. IP: 192.168.1.100
   Setup complete!
   ```
4. **Catat alamat IP** (`192.168.1.100`). Alamat inilah yang harus Anda tempelkan ke dalam file `.env` di aplikasi Python Anda pada baris `ARDUINO_IP`.

---

## 🐛 Troubleshooting Hardware

> [!TIP]
> Jika sistem tidak berfungsi sebagaimana mestinya, periksa hal-hal berikut.

- **LCD Kotak-kotak Kosong**: 
  - Alamat I2C layar LCD Anda mungkin bukan `0x27`. Cobalah mengubah baris `LiquidCrystal_I2C lcd(0x27, 16, 2);` menjadi `0x3F`. 
  - Atur juga kontras layar (putar sekrup trimpot biru kecil di belakang LCD menggunakan obeng minus).
- **Pembacaan Suhu "nan" (Not a Number)**: 
  - Pastikan sensor terhubung ke Pin 2.
  - Jika Anda menggunakan DHT11 (bukan DHT22), ubah baris `#define DHTTYPE DHT22` menjadi `#define DHTTYPE DHT11`.
- **Relay Tidak Bunyi "Klik"**:
  - Pastikan pin Relay dihubungkan ke Pin Digital 7 dan memiliki asupan daya 5V yang cukup.
