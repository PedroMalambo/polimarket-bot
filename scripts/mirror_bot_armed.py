import os
import time
import requests
from dotenv import load_dotenv
from eth_account import Account

load_dotenv()

TARGET_USER = "0x02227b8f5a9636e895607edd3185ed6ee5598ff7"
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

class PureTrader:
    def __init__(self):
        self.account = Account.from_key(PRIVATE_KEY)
        print(f"✅ Motor Manual iniciado. Billetera: {self.account.address}")

    def buy_order(self, title, price):
        print(f"\n💸 [SIMULACIÓN] Copiando compra en: {title}")
        print(f"💰 Precio objetivo: ${price} | Inversión: $1.00")
        print("✅ Firma criptográfica preparada.")

def main():
    trader = PureTrader()
    # Este 'header' es el disfraz de navegador
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"📡 Espiando a: {TARGET_USER}")
    last_id = None

    while True:
        try:
            url = f"https://gamma-api.polymarket.com/activity?user={TARGET_USER}&limit=1"
            response = requests.get(url, headers=headers)
            
            # Verificamos si la respuesta es válida antes de procesar
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json and resp_json[0].get('id') != last_id:
                    act = resp_json[0]
                    # Solo copiamos si es una COMPRA confirmada
                    if act.get('type') == 'ORDER_FILLED' and act.get('side') == 'BUY':
                        trader.buy_order(act.get('title'), act.get('price'))
                    last_id = act.get('id')
            elif response.status_code == 403:
                print("\n⚠️ Acceso denegado (403). Reintentando con nuevo túnel...")
            
            time.sleep(20) # Bajamos a 20 segundos para ser más rápidos
            print(".", end="", flush=True)
            
        except Exception as e:
            print(f"\n❌ Error detectado: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()