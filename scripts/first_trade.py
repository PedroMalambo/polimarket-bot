import os
from py_polymarket_library import ClobClient
from dotenv import load_dotenv

load_dotenv()

def main():
    # 1. Configurar el cliente
    client = ClobClient(
        host="https://clob.polymarket.com",
        private_key=os.getenv("PRIVATE_KEY")
    )

    # 2. Definimos qué queremos comprar
    # Vamos a usar el mercado de "Oscars 2026: Best Actor" (Michael B. Jordan)
    # Este es el ID del token para "YES" en ese mercado
    token_id = "2232918656778088448" # Ejemplo, el script real buscará uno activo
    
    print(f"🚀 Intentando comprar $1.00 de Michael B. Jordan...")
    
    # 3. Crear la orden (Comprar $1 a precio de mercado)
    try:
        resp = client.create_order(
            token_id=token_id,
            price=0.55, # Compramos si el precio es menor a 0.55
            amount=1,    # 1 ticket (aprox $1)
            side="BUY"
        )
        print("✅ ¡Orden enviada con éxito!")
        print(f"ID de la orden: {resp.get('orderID')}")
    except Exception as e:
        print(f"❌ Error al ejecutar: {e}")

if __name__ == "__main__":
    main()
