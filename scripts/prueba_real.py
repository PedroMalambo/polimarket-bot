import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

def verificar_cuenta_real():
    print("🔌 Conectando a los servidores centrales de Polymarket...")
    load_dotenv()
    
    key = os.getenv("PRIVATE_KEY")
    host = "https://clob.polymarket.com"
    chain_id = 137 # Red real de Polygon
    
    try:
        # 1. Autenticación Criptográfica
        client = ClobClient(host, key=key, chain_id=chain_id)
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        
        # 2. Obtener tu billetera pública
        address = client.get_address()
        print(f"✅ Billetera oficial reconocida: {address}")
        
        # 3. Pedir datos privados al servidor (Solo el dueño puede hacer esto)
        print("📡 Extrayendo datos privados de tu cuenta...")
        ordenes = client.get_orders()
        
        print("\n" + "="*50)
        print("🏆 PRUEBA DE CONEXIÓN SUPERADA 🏆")
        print("="*50)
        print(f"Polymarket confirma que eres el dueño de la cuenta.")
        print(f"Actualmente tienes {len(ordenes)} órdenes activas reales en el sistema.")
        print("El puente de fuego real está 100% operativo y listo para disparar.")
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    verificar_cuenta_real()
