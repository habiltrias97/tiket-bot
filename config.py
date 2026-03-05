# ============================================
# KONFIGURASI BOT MONITORING TIKET.COM
# ============================================

# Pengaturan Penerbangan
FLIGHT_CONFIG = {
    # Kota asal (kode bandara)
    "origin": "CGK",  # Jakarta - Soekarno Hatta
    
    # Kota tujuan (kode bandara)
    "destination": "PDG",  # Bali - Ngurah Rai
    
    # Tanggal yang ingin dipantau (format: YYYY-MM-DD)
    "dates": [
        "2026-03-11",
        "2026-03-13",
        "2026-03-14",
        "2026-03-15",
    ],
    
    # Jumlah penumpang
    "adult": 1,
    "child": 0,
    "infant": 0,
}

# Pengaturan Interval Pengecekan
CHECK_INTERVAL = 60  # dalam detik (300 = 5 menit)

# Mode Aplikasi
# True = Background (browser tidak terlihat, hemat resource)
# False = Foreground (browser terlihat, bisa melihat proses)
HEADLESS_MODE = True

# Pengaturan Notifikasi
NOTIFICATION_CONFIG = {
    # Notifikasi Desktop (Windows Toast)
    "desktop_enabled": True,
    
    # Notifikasi Suara
    "sound_enabled": True,
    
    # Notifikasi Telegram (opsional)
    "telegram_enabled": True,
    "telegram_bot_token": "8724507210:AAF3QwRYmN0XUgz3XN18RcijkbY8zUJz2cc",
    "telegram_chat_id": ["5296125477", "5972490592"],
}

# Daftar Kode Bandara Indonesia yang Umum
# CGK - Jakarta (Soekarno-Hatta)
# HLP - Jakarta (Halim Perdanakusuma)
# SUB - Surabaya (Juanda)
# DPS - Bali (Ngurah Rai)
# JOG - Yogyakarta (Adisucipto)
# YIA - Yogyakarta (YIA)
# SRG - Semarang (Ahmad Yani)
# BDO - Bandung (Husein Sastranegara)
# BPN - Balikpapan (Sultan Aji Muhammad Sulaiman)
# UPG - Makassar (Sultan Hasanuddin)
# MES - Medan (Kualanamu)
# PDG - Padang (Minangkabau)
# PKU - Pekanbaru (Sultan Syarif Kasim II)
# PLM - Palembang (Sultan Mahmud Badaruddin II)
# BTH - Batam (Hang Nadim)
# PNK - Pontianak (Supadio)
# MDC - Manado (Sam Ratulangi)
# AMQ - Ambon (Pattimura)
# DJJ - Jayapura (Sentani)
# LOP - Lombok (Lombok International)
