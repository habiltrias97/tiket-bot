"""
Bot Monitoring Penerbangan Tiket.com
====================================

Bot ini akan memantau ketersediaan penerbangan di tiket.com
dan memberikan notifikasi ketika penerbangan ditemukan.
"""

import os
import time
import json
import re
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from config import FLIGHT_CONFIG, CHECK_INTERVAL
from notifier import Notifier

# Import HEADLESS_MODE dengan default value
try:
    from config import HEADLESS_MODE
except ImportError:
    HEADLESS_MODE = True


class TiketFlightMonitor:
    """Class untuk memonitor penerbangan di tiket.com"""
    
    BASE_URL = "https://www.tiket.com/pesawat/search"
    
    def __init__(self):
        self.notifier = Notifier()
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
            "Referer": "https://www.tiket.com/",
        })
    
    def _init_driver(self) -> webdriver.Chrome:
        """Inisialisasi Chrome WebDriver."""
        chrome_options = Options()
        
        # Opsi untuk mengurangi deteksi bot
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Opsi performa
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        # Mode headless (background) atau foreground
        global HEADLESS_MODE
        if HEADLESS_MODE:
            chrome_options.add_argument("--headless=new")
            print("   🔇 Mode: Background (headless)")
        else:
            print("   🔊 Mode: Foreground (browser terlihat)")
        
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Gunakan chromedriver sistem jika tersedia (Docker/Linux), fallback ke webdriver-manager
        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH") or shutil.which("chromedriver")
        if chromedriver_path:
            service = Service(chromedriver_path)
        else:
            service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Hapus tanda webdriver
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
        })
        
        return driver
    
    def build_search_url(self, origin: str, destination: str, date: str, 
                         adult: int = 1, child: int = 0, infant: int = 0) -> str:
        """Buat URL pencarian tiket.com."""
        # Format: https://www.tiket.com/pesawat/search?d=CGK&a=DPS&date=2026-03-15&adult=1&child=0&infant=0&class=economy
        
        params = {
            "d": origin,
            "a": destination,
            "date": date,
            "adult": adult,
            "child": child,
            "infant": infant,
            "class": "economy"
        }
        
        return f"{self.BASE_URL}?{urlencode(params)}"
    
    def search_flights_selenium(self, origin: str, destination: str, date: str,
                                adult: int = 1, child: int = 0, infant: int = 0,
                                driver: Optional[webdriver.Chrome] = None) -> List[Dict[str, Any]]:
        """Cari penerbangan menggunakan Selenium."""
        
        flights = []
        
        try:
            if driver is not None:
                use_driver = driver
            else:
                if self.driver is None:
                    self.driver = self._init_driver()
                use_driver = self.driver
            
            url = self.build_search_url(origin, destination, date, adult, child, infant)
            print(f"\n🔍 Mencari penerbangan: {origin} → {destination} pada {date}")
            print(f"   URL: {url}")
            
            use_driver.get(url)
            
            # Tunggu halaman loading
            time.sleep(3)
            
            # Tunggu hasil pencarian atau indikator halaman selesai dimuat
            try:
                WebDriverWait(use_driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR,
                        "[data-testid='flight-result-item'], .flight-item, .css-1dbjc4n, "
                        "div[class*='result'], div[class*='empty'], div[class*='notfound'], "
                        "div[class*='no-result'], [data-testid*='empty'], [data-testid*='not-found'], "
                        "[class*='EmptyState'], [class*='empty-state'], [class*='NoResult']"
                    ))
                )
            except TimeoutException:
                print("   ⏱️ Timeout menunggu hasil pencarian")
            
            # Scroll untuk memuat lebih banyak hasil
            use_driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            # Coba berbagai selector untuk menemukan flight cards (direct flight only)
            selectors = [
                "[data-testid='flight-result-item']",
                ".flight-item",
                "[class*='FlightCard']",
                "[class*='flight-card']",
                ".css-1dbjc4n[data-testid]",
                "div[class*='result']",
            ]
            
            flight_elements = []
            for selector in selectors:
                try:
                    elements = use_driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        flight_elements = elements
                        print(f"   ✅ Ditemukan {len(elements)} elemen dengan selector: {selector}")
                        break
                except:
                    continue
            
            # Parse setiap flight card - cari hanya penerbangan langsung (direct) dengan data valid
            for element in flight_elements:
                try:
                    flight_info = self._parse_flight_element(element)
                    if flight_info and self._is_valid_flight(flight_info):
                        flights.append(flight_info)
                        break  # Ambil hanya 1 penerbangan langsung pertama
                except Exception as e:
                    continue
            
            # Jika tidak menemukan dengan selector, coba parse dari page source
            if not flights:
                flights = self._parse_from_page_source(use_driver)
                # Filter hanya flight dengan data valid dan ambil 1
                flights = [f for f in flights if self._is_valid_flight(f)][:1]
            
            if flights:
                print(f"   📊 Penerbangan langsung ditemukan: 1")
            else:
                print(f"   📊 Tidak ada penerbangan langsung")
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            self.notifier.notify_error(f"Error saat mencari penerbangan: {str(e)}")
        
        return flights
    
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """Parse informasi dari elemen flight card."""
        try:
            text = element.text
            
            if not text or len(text) < 10:
                return None
            
            flight_info = {
                "raw_text": text[:200],
                "airline": "Unknown",
                "departure_time": "N/A",
                "arrival_time": "N/A",
                "duration": "N/A",
                "price": "N/A"
            }
            
            # Parse waktu (format: HH:MM)
            time_pattern = r'\b(\d{2}:\d{2})\b'
            times = re.findall(time_pattern, text)
            if len(times) >= 2:
                flight_info["departure_time"] = times[0]
                flight_info["arrival_time"] = times[1]
            
            # Parse harga (format: Rp X.XXX.XXX atau IDR)
            price_pattern = r'(?:Rp\.?|IDR)\s*([\d.,]+)'
            price_match = re.search(price_pattern, text, re.IGNORECASE)
            if price_match:
                flight_info["price"] = f"Rp {price_match.group(1)}"
            
            # Parse maskapai
            airlines = ["Garuda", "Lion", "Citilink", "Batik", "AirAsia", "Sriwijaya", "NAM Air", "Wings", "Super Air Jet", "Pelita Air", "TransNusa"]
            for airline in airlines:
                if airline.lower() in text.lower():
                    flight_info["airline"] = airline
                    break
            
            # Parse durasi
            duration_pattern = r'(\d+[hj]\s*\d*[mnt]*)'
            duration_match = re.search(duration_pattern, text, re.IGNORECASE)
            if duration_match:
                flight_info["duration"] = duration_match.group(1)
            
            return flight_info
            
        except Exception as e:
            return None
    
    def _is_direct_flight(self, flight_info: Dict[str, Any]) -> bool:
        """Cek apakah penerbangan adalah direct (tanpa transit)."""
        raw_text = flight_info.get("raw_text", "").lower()
        
        # Kata-kata yang menandakan transit
        transit_keywords = ["transit", "via", "stop", "connecting", "1 stop", "2 stop", "berhenti", "singgah"]
        
        for keyword in transit_keywords:
            if keyword in raw_text:
                return False
        
        # Cek jika ada indikator langsung
        direct_keywords = ["langsung", "direct", "nonstop", "non-stop"]
        for keyword in direct_keywords:
            if keyword in raw_text:
                return True
        
        # Default: anggap direct jika tidak ada keyword transit
        return True
    
    def _has_valid_price(self, flight_info: Dict[str, Any]) -> bool:
        """Cek apakah penerbangan memiliki harga yang valid (bukan N/A)."""
        price = flight_info.get("price", "N/A")
        
        # Cek jika harga N/A atau kosong
        if not price or price == "N/A" or price.strip() == "":
            return False
        
        # Cek jika harga mengandung angka
        if not any(char.isdigit() for char in price):
            return False
        
        return True
    
    def _has_valid_times(self, flight_info: Dict[str, Any]) -> bool:
        """Cek apakah penerbangan memiliki waktu yang valid (bukan N/A)."""
        departure = flight_info.get("departure_time", "N/A")
        arrival = flight_info.get("arrival_time", "N/A")
        
        # Cek jika waktu N/A atau kosong
        if not departure or departure == "N/A" or departure.strip() == "":
            return False
        
        if not arrival or arrival == "N/A" or arrival.strip() == "":
            return False
        
        # Cek format waktu (HH:MM)
        time_pattern = r'^\d{2}:\d{2}$'
        if not re.match(time_pattern, departure) or not re.match(time_pattern, arrival):
            return False
        
        return True
    
    def _has_valid_airline(self, flight_info: Dict[str, Any]) -> bool:
        """Cek apakah penerbangan memiliki nama maskapai yang valid."""
        airline = flight_info.get("airline", "Unknown")
        
        # Cek jika maskapai Unknown atau Maskapai (generic)
        if not airline or airline in ["Unknown", "Maskapai", "N/A", ""]:
            return False
        
        return True
    
    def _is_valid_flight(self, flight_info: Dict[str, Any]) -> bool:
        """Cek apakah penerbangan memiliki semua data yang valid."""
        return (
            self._is_direct_flight(flight_info) and
            self._has_valid_price(flight_info) and
            self._has_valid_times(flight_info) and
            self._has_valid_airline(flight_info)
        )
    
    def _parse_from_page_source(self, driver=None) -> List[Dict[str, Any]]:
        """Parse penerbangan dari page source (untuk React/Next.js apps)."""
        flights = []
        use_driver = driver if driver is not None else self.driver
        
        try:
            page_source = use_driver.page_source
            
            # Cari JSON data dalam script tags
            script_pattern = r'<script[^>]*>.*?(__NEXT_DATA__|window\.__INITIAL_STATE__).*?</script>'
            
            # Cari harga dalam halaman
            price_pattern = r'(?:Rp\.?|IDR)\s*([\d.,]+)'
            prices = re.findall(price_pattern, page_source)
            
            # Cari waktu
            time_pattern = r'\b(\d{2}:\d{2})\b'
            times = re.findall(time_pattern, page_source)
            
            # Jika ada harga, berarti ada penerbangan
            if prices:
                unique_prices = list(set(prices))[:10]
                for i, price in enumerate(unique_prices):
                    flight = {
                        "airline": "Maskapai",
                        "departure_time": times[i*2] if i*2 < len(times) else "N/A",
                        "arrival_time": times[i*2+1] if i*2+1 < len(times) else "N/A",
                        "price": f"Rp {price}",
                        "duration": "N/A"
                    }
                    flights.append(flight)
                    
        except Exception as e:
            print(f"   Error parsing page source: {e}")
        
        return flights
    
    def check_flights_for_date(self, date: str) -> List[Dict[str, Any]]:
        """Cek penerbangan untuk tanggal tertentu."""
        
        origin = FLIGHT_CONFIG.get("origin", "CGK")
        destination = FLIGHT_CONFIG.get("destination", "DPS")
        adult = FLIGHT_CONFIG.get("adult", 1)
        child = FLIGHT_CONFIG.get("child", 0)
        infant = FLIGHT_CONFIG.get("infant", 0)
        
        return self.search_flights_selenium(origin, destination, date, adult, child, infant)
    
    def _check_date_standalone(self, date: str) -> tuple:
        """Cek penerbangan untuk satu tanggal dengan driver terpisah (untuk parallel execution)."""
        driver = None
        try:
            driver = self._init_driver()
            origin = FLIGHT_CONFIG.get("origin", "CGK")
            destination = FLIGHT_CONFIG.get("destination", "DPS")
            adult = FLIGHT_CONFIG.get("adult", 1)
            child = FLIGHT_CONFIG.get("child", 0)
            infant = FLIGHT_CONFIG.get("infant", 0)
            
            flights = self.search_flights_selenium(origin, destination, date, adult, child, infant, driver=driver)
            return (date, flights)
        except Exception as e:
            print(f"   ❌ Error untuk {date}: {str(e)}")
            return (date, [])
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def check_all_dates_parallel(self, dates: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Cek semua tanggal secara parallel menggunakan multiple browser."""
        results = {}
        max_workers = min(len(dates), 4)
        
        print(f"\n🚀 Memulai pencarian parallel untuk {len(dates)} tanggal (max {max_workers} browser)...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._check_date_standalone, date): date for date in dates}
            
            for future in as_completed(futures):
                date = futures[future]
                try:
                    _, flights = future.result()
                    results[date] = flights
                except Exception as e:
                    print(f"   ❌ Error untuk {date}: {str(e)}")
                    results[date] = []
        
        print(f"\n✅ Pencarian parallel selesai untuk {len(dates)} tanggal")
        return results
    
    def monitor_flights(self) -> None:
        """Mulai monitoring penerbangan."""
        
        print("\n" + "="*60)
        print("🚀 BOT MONITORING PENERBANGAN TIKET.COM")
        print("="*60)
        print(f"\n📋 Konfigurasi:")
        print(f"   Rute    : {FLIGHT_CONFIG['origin']} → {FLIGHT_CONFIG['destination']}")
        print(f"   Tanggal : {', '.join(FLIGHT_CONFIG['dates'])}")
        print(f"   Interval: {CHECK_INTERVAL} detik")
        print("\n" + "-"*60)
        
        try:
            while True:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n⏰ [{current_time}] Memulai pengecekan...")
                
                dates = FLIGHT_CONFIG["dates"]
                route = f"{FLIGHT_CONFIG['origin']} → {FLIGHT_CONFIG['destination']}"
                
                if len(dates) > 1:
                    # Pencarian parallel untuk multi tanggal
                    results = self.check_all_dates_parallel(dates)
                    for date in dates:
                        flights = results.get(date, [])
                        if flights:
                            self.notifier.notify_flight_found(flights, date, route)
                        else:
                            self.notifier.notify_no_flight(date, route)
                else:
                    # Pencarian sequential untuk satu tanggal
                    for date in dates:
                        try:
                            flights = self.check_flights_for_date(date)
                            if flights:
                                self.notifier.notify_flight_found(flights, date, route)
                            else:
                                self.notifier.notify_no_flight(date, route)
                        except Exception as e:
                            print(f"   ❌ Error untuk {date}: {str(e)}")
                            continue
                
                print(f"\n💤 Menunggu {CHECK_INTERVAL} detik sebelum pengecekan berikutnya...")
                print("-"*60)
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Bot dihentikan oleh pengguna.")
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """Bersihkan resources."""
        try:
            if self.driver:
                self.driver.quit()
                print("✅ Browser ditutup.")
        except:
            pass
    
    def single_check(self) -> None:
        """Lakukan pengecekan sekali saja (tanpa loop)."""
        
        print("\n" + "="*60)
        print("🔍 PENGECEKAN SEKALI - BOT TIKET.COM")
        print("="*60)
        
        dates = FLIGHT_CONFIG["dates"]
        route = f"{FLIGHT_CONFIG['origin']} → {FLIGHT_CONFIG['destination']}"
        
        if len(dates) > 1:
            # Pencarian parallel untuk multi tanggal
            results = self.check_all_dates_parallel(dates)
            for date in dates:
                flights = results.get(date, [])
                if flights:
                    self.notifier.notify_flight_found(flights, date, route)
                else:
                    self.notifier.notify_no_flight(date, route)
        else:
            for date in dates:
                flights = self.check_flights_for_date(date)
                if flights:
                    self.notifier.notify_flight_found(flights, date, route)
                else:
                    self.notifier.notify_no_flight(date, route)
        
        self.cleanup()
        print("\n✅ Pengecekan selesai!")


def main():
    """Fungsi utama."""
    global HEADLESS_MODE
    
    mode_text = "Background (headless)" if HEADLESS_MODE else "Foreground (browser terlihat)"
    
    print(f"""
    ╔═══════════════════════════════════════════════════════╗
    ║     BOT MONITORING PENERBANGAN TIKET.COM              ║
    ╠═══════════════════════════════════════════════════════╣
    ║                                                       ║
    ║  Mode saat ini: {mode_text:<35} ║
    ║                                                       ║
    ║  Pilihan:                                             ║
    ║  1. Monitoring terus menerus                          ║
    ║  2. Cek sekali saja                                   ║
    ║  3. Ganti mode (Background/Foreground)                ║
    ║  4. Keluar                                            ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    
    choice = input("Pilih (1/2/3/4): ").strip()
    
    if choice == "3":
        HEADLESS_MODE = not HEADLESS_MODE
        new_mode = "Background (headless)" if HEADLESS_MODE else "Foreground (browser terlihat)"
        print(f"\n✅ Mode diubah ke: {new_mode}\n")
        return main()  # Kembali ke menu
    
    monitor = TiketFlightMonitor()
    
    if choice == "1":
        monitor.monitor_flights()
    elif choice == "2":
        monitor.single_check()
    else:
        print("Keluar...")


if __name__ == "__main__":
    # Support non-interactive mode via BOT_MODE env var (untuk Docker)
    bot_mode = os.environ.get("BOT_MODE", "").lower()
    if bot_mode == "monitor":
        HEADLESS_MODE = True
        monitor = TiketFlightMonitor()
        monitor.monitor_flights()
    elif bot_mode == "single":
        HEADLESS_MODE = True
        monitor = TiketFlightMonitor()
        monitor.single_check()
    else:
        main()
