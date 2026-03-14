import os
import requests
from dotenv import load_dotenv
from eth_account import Account

load_dotenv()

def get_live_markets():
    print("🔍 Buscando los 5 mercados con más volumen...")
    # Usamos Gamma API, la fuente oficial de la web
    url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&order=volume&limit=5&ascending=false"
    resp = requests.get(url)
    return resp.json()

def main():
    try:
        pk = os.getenv("PRIVATE_KEY")
        acc = Account.from_key(pk)
        print(f"✅ Bot conectado: {acc.address}")
        
        markets = get_live_markets()
        
        print(f"\n{'#':<3} | {'MERCADO ACTUAL (TOP VOLUMEN)':<50}")
        print("-" * 60)
        
        for i, m in enumerate(markets):
            # En Gamma API la pregunta está en 'question'
            title = m.get('question', 'Sin título')
            print(f"{i+1:<3} | {title[:48]:<50}")
            
        print("\n🚀 ¡LISTO! Ya podemos ver qué está pasando en el mundo.")
        print("Siguiente paso: Elegir un 'Ganador' para copiarle las jugadas.")

    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    main()