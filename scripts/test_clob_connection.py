import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

# Cargar variables del .env
load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
HOST = "https://clob.polymarket.com"

def test_connection():
    if not PRIVATE_KEY:
        print("❌ ERROR: No se encontró PRIVATE_KEY en el archivo .env")
        return

    print("🔄 Inicializando ClobClient...")
    try:
        # Inicializamos el cliente con tu llave de Polygon
        client = ClobClient(
            host=HOST,
            key=PRIVATE_KEY,
            chain_id=POLYGON
        )
        print("✅ ClobClient inicializado.")

        print("🔐 Derivando credenciales API L2 (Firma criptográfica off-chain)...")
        # Esto firma un mensaje con tu llave privada para generar los API keys del CLOB
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        
        print("✅ Credenciales derivadas con éxito!")
        print(f"🔑 API Key generada: {creds.api_key[:8]}... (oculto por seguridad)")

        print("📡 Haciendo ping al servidor CLOB con las credenciales...")
        is_ok = client.get_ok()
        if is_ok == "OK":
            print("🚀 ¡Conexión exitosa! Tu billetera está autorizada para operar en Polymarket.")
        else:
            print(f"⚠️ El servidor respondió, pero el estado es: {is_ok}")

    except Exception as e:
        print(f"❌ Ocurrió un error crítico durante la conexión: {e}")

if __name__ == "__main__":
    test_connection()
