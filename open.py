import pyautogui
import base64
from openai import OpenAI
from PIL import Image
import io
import time

# Konfigurasi ke LM Studio Local Server
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

def encode_image_to_base64(image):
    # Kecilkan resolusi agar pengiriman ke API lebih cepat
    image.thumbnail((800, 800))
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=80)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def monitor_screen():
    print("--- Memulai Monitoring Layar via LM Studio (Gemma 3 4B) ---")
    
    while True:
        try:
            # 1. Ambil screenshot
            screenshot = pyautogui.screenshot()
            
            # 2. Ubah gambar ke format Base64
            base64_image = encode_image_to_base64(screenshot)

            # 3. Kirim ke LM Studio API
            response = client.chat.completions.create(
                model="model-identifier", # LM Studio otomatis menggunakan model yang sedang di-load
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Apa yang sedang saya buka di layar sekarang? Berikan poin-poin singkat."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=150,
            )

            # 4. Cetak hasil
            output = response.choices[0].message.content
            print(f"\n[{time.strftime('%H:%M:%S')}] Analisis Layar:")
            print(output)
            print("-" * 50)

            # Jeda 5 detik agar tidak membebani hardware
            time.sleep(5)

        except KeyboardInterrupt:
            print("\nMonitoring dihentikan.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    monitor_screen()