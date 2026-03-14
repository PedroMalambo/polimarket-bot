import os
import requests
import time
from dotenv import load_dotenv
from eth_account import Account

load_dotenv()

# CONFIGURACIÓN
TARGET_USER = "0x02227b8f5a9636e895607edd3185ed6ee5598ff7" # La que copiaste del leaderboard
CHECK_INTERVAL = 30 # Segundos entre cada revisión
INVESTMENT_AMOUNT = 1.00 # Dólares a invertir por jugada

def get_last_activity(address):
    url = f"https://gamma-api.polymarket.com/activity?user={address}&limit=1"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        return data[0] if data else None
    return None

def main():
    pk = os.getenv("PRIVATE_KEY")
    my_acc = Account.from_key(pk)
    print(f"🤖 Bot Espejo Activado.")
    print(f"📡 Siguiendo a: {TARGET_USER}")
    print(f"💰 Inversión por copia: ${INVESTMENT_AMOUNT}")
    
    last_seen_id = None

    while True:
        try:
            activity = get_last_activity(TARGET_USER)
            
            if activity and activity.get('id') != last_seen_id:
                # Si es una compra (Buy)
                if activity.get('type') == 'ORDER_FILLED' and activity.get('side') == 'BUY':
                    market_title = activity.get('title')
                    outcome = activity.get('outcome')
                    print(f"🚨 ¡MOVIMIENTO DETECTADO!")
                    print(f"📈 El pro compró: {market_title} ({outcome})")
                    
                    # AQUÍ EL BOT DISPARARÍA LA ORDEN REAL
                    print(f"💸 Replicando compra de ${INVESTMENT_AMOUNT}...")
                    # (La función de compra real la activaremos en el siguiente paso)
                
                last_seen_id = activity.get('id')
            
            time.sleep(CHECK_INTERVAL)
            print(".", end="", flush=True) # Pulso para saber que el bot sigue vivo

        except Exception as e:
            print(f"\n❌ Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
