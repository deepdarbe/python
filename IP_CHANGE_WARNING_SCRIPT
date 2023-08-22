import requests
import time
import threading
import tkinter as tk
from tkinter import font
import winsound
import queue
import keyboard

def get_external_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=10)
        data = response.json()
        return data['ip']
    except Exception as e:
        print("IP adresi alınırken bir hata oluştu:", e)
        return None

def show_notification(new_ip, notification_queue):
    root = tk.Tk()
    root.title("IP Adresi Değişti")
    
    custom_font = font.Font(size=20)  # Büyük ve net okunabilir font
    
    label = tk.Label(root, text=f"Yeni IP Adresiniz:\n{new_ip}", font=custom_font, padx=20, pady=20, fg="green")
    label.pack()
    
    def toggle_label():
        label.pack_forget()
        root.after(500, label.pack)
        root.after(1000, toggle_label)
        
    toggle_label()
    
    for freq in [251, 500, 750, 1000, 1253]:
        winsound.Beep(freq, 101)
    
    def close_notification():
        root.destroy()
        print("IP Adresi Değişti penceresi kapatıldı.")
    
    root.after(10000, close_notification)
    
    root.mainloop()

def check_ip_change(notification_queue):
    current_ip = None
    
    while True:
        if keyboard.is_pressed("q"):
            break

        try:
            new_ip = get_external_ip()
            if new_ip is not None:
                if current_ip is None or new_ip != current_ip:
                    current_ip = new_ip
                    print("IP Adresiniz değişti:", current_ip)
                    notification_queue.put(current_ip)
            else:
                print("IP adresi alınamadı. Tekrar deneyeceğim.")
        except Exception as e:
            print("Bir hata oluştu:", e)

        time.sleep(5)

if __name__ == "__main__":
    notification_queue = queue.Queue()
    
    ip_check_thread = threading.Thread(target=check_ip_change, args=(notification_queue,))
    ip_check_thread.start()

    while True:
        try:
            new_ip = notification_queue.get_nowait()
            show_notification(new_ip, notification_queue)
        except queue.Empty:
            pass
