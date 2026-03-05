"""
Modul Notifikasi untuk Bot Monitoring Tiket.com
"""

import os
from datetime import datetime
import requests
from typing import List, Dict, Any
from config import NOTIFICATION_CONFIG

# Windows toast notification
try:
    from win10toast import ToastNotifier
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False

# Cross-platform notification
try:
    from plyer import notification as plyer_notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


class Notifier:
    """Class untuk mengirim berbagai jenis notifikasi."""
    
    def __init__(self):
        self.config = NOTIFICATION_CONFIG
        if TOAST_AVAILABLE:
            self.toaster = ToastNotifier()
    
    def send_desktop_notification(self, title: str, message: str) -> bool:
        """Kirim notifikasi desktop."""
        if not self.config.get("desktop_enabled", False):
            return False
        
        try:
            if TOAST_AVAILABLE:
                self.toaster.show_toast(
                    title,
                    message,
                    duration=10,
                    threaded=True
                )
                return True
            elif PLYER_AVAILABLE:
                plyer_notification.notify(
                    title=title,
                    message=message,
                    app_name="Tiket Bot",
                    timeout=10
                )
                return True
            else:
                print(f"[NOTIFIKASI] {title}: {message}")
                return True
        except Exception as e:
            print(f"Error mengirim notifikasi desktop: {e}")
            return False
    
    def play_sound(self) -> bool:
        """Mainkan suara notifikasi."""
        if not self.config.get("sound_enabled", False):
            return False
        
        try:
            import winsound
            # Mainkan suara sistem Windows
            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
            return True
        except Exception as e:
            print(f"Error memainkan suara: {e}")
            return False
    
    def send_telegram_notification(self, message: str) -> bool:
        """Kirim notifikasi via Telegram ke satu atau banyak chat_id."""
        if not self.config.get("telegram_enabled", False):
            return False
        
        bot_token = self.config.get("telegram_bot_token", "")
        chat_ids = self.config.get("telegram_chat_id", [])
        
        if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
            print("Token Telegram belum dikonfigurasi!")
            return False
        
        # Konversi ke list jika single string
        if isinstance(chat_ids, str):
            chat_ids = [chat_ids]
        
        if not chat_ids or (len(chat_ids) == 1 and chat_ids[0] == "YOUR_CHAT_ID_HERE"):
            print("Chat ID Telegram belum dikonfigurasi!")
            return False
        
        success_count = 0
        for chat_id in chat_ids:
            if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
                continue
            
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    success_count += 1
                else:
                    print(f"   Gagal kirim ke chat_id {chat_id}: {response.status_code}")
            except Exception as e:
                print(f"Error mengirim notifikasi Telegram ke {chat_id}: {e}")
        
        if success_count > 0:
            print(f"   [TELEGRAM] Terkirim ke {success_count}/{len(chat_ids)} chat")
        
        return success_count > 0
    
    def notify_flight_found(self, flights: List[Dict[str, Any]], date: str, route: str) -> None:
        """Kirim notifikasi ketika penerbangan ditemukan."""
        
        # Format pesan
        title = "[FOUND] Penerbangan Langsung Ditemukan!"
        
        # Tampilkan info singkat 1 penerbangan teratas
        if flights:
            flight = flights[0]
            price = flight.get('price', 'N/A')
            short_message = f"{route} pada {date} - {price}"
        else:
            short_message = f"{route} pada {date}"
        
        detailed_message = "[ALERT] PENERBANGAN LANGSUNG DITEMUKAN!\n\n"
        detailed_message += f"Rute: {route}\n"
        detailed_message += f"Tanggal: {date}\n\n"
        
        # Tampilkan hanya 1 penerbangan teratas
        if flights:
            flight = flights[0]
            airline = flight.get('airline', 'N/A')
            departure = flight.get('departure_time', 'N/A')
            arrival = flight.get('arrival_time', 'N/A')
            price = flight.get('price', 'N/A')
            duration = flight.get('duration', 'N/A')
            
            detailed_message += f"Maskapai: {airline}\n"
            detailed_message += f"Jadwal: {departure} - {arrival}\n"
            if duration != 'N/A':
                detailed_message += f"Durasi: {duration}\n"
            detailed_message += f"Harga: {price}\n"
        
        detailed_message += "\nSegera cek di tiket.com!"
        
        # Kirim notifikasi
        print("\n" + "="*50)
        print(detailed_message)
        print("="*50 + "\n")
        
        self.send_desktop_notification(title, short_message)
        self.play_sound()
        self.send_telegram_notification(detailed_message)
        self.save_report(flights, date, route)
    
    def save_report(self, flights: List[Dict[str, Any]], date: str, route: str) -> bool:
        """Simpan report penerbangan ke file txt."""
        try:
            # Buat folder reports jika belum ada
            reports_dir = os.path.join(os.path.dirname(__file__), "reports")
            if not os.path.exists(reports_dir):
                os.makedirs(reports_dir)
            
            # Buat nama file dengan timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"flight_report_{date}_{timestamp}.txt"
            filepath = os.path.join(reports_dir, filename)
            
            # Tulis report
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("="*50 + "\n")
                f.write("LAPORAN PENERBANGAN DITEMUKAN\n")
                f.write("="*50 + "\n\n")
                f.write(f"Waktu Laporan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Rute: {route}\n")
                f.write(f"Tanggal Penerbangan: {date}\n\n")
                f.write("-"*50 + "\n")
                f.write("DETAIL PENERBANGAN:\n")
                f.write("-"*50 + "\n\n")
                
                if flights:
                    flight = flights[0]
                    airline = flight.get('airline', 'N/A')
                    departure = flight.get('departure_time', 'N/A')
                    arrival = flight.get('arrival_time', 'N/A')
                    price = flight.get('price', 'N/A')
                    duration = flight.get('duration', 'N/A')
                    
                    f.write(f"Maskapai     : {airline}\n")
                    f.write(f"Keberangkatan: {departure}\n")
                    f.write(f"Kedatangan   : {arrival}\n")
                    if duration != 'N/A':
                        f.write(f"Durasi       : {duration}\n")
                    f.write(f"Harga        : {price}\n")
                
                f.write("\n" + "="*50 + "\n")
                f.write("Segera cek di https://www.tiket.com\n")
                f.write("="*50 + "\n")
            
            print(f"   [REPORT] Report disimpan: {filepath}")
            return True
            
        except Exception as e:
            print(f"   [WARNING] Gagal menyimpan report: {e}")
            return False
    
    def notify_no_flight(self, date: str, route: str) -> None:
        """Kirim notifikasi ketika tidak ada penerbangan."""
        message = f"[NOT FOUND] Tidak ada penerbangan {route} pada {date}"
        print(message)
    
    def notify_error(self, error_message: str) -> None:
        """Kirim notifikasi error."""
        title = "[ERROR] Error Bot Tiket"
        print(f"[ERROR] {error_message}")
        self.send_desktop_notification(title, error_message)


def test_notification():
    """Test fungsi notifikasi."""
    notifier = Notifier()
    
    # Test data
    test_flights = [
        {
            "airline": "Garuda Indonesia",
            "departure_time": "08:00",
            "arrival_time": "09:30",
            "price": "Rp 1.500.000"
        },
        {
            "airline": "Lion Air",
            "departure_time": "10:00",
            "arrival_time": "11:30",
            "price": "Rp 800.000"
        }
    ]
    
    print("Testing notifikasi...")
    notifier.notify_flight_found(test_flights, "2026-03-15", "CGK -> DPS")
    print("Test selesai!")


if __name__ == "__main__":
    test_notification()
