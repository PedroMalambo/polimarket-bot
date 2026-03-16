import os
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
from src.monitoring.logger import app_logger

def get_real_polymarket_balance() -> float:
    """
    Se conecta a la API de Polymarket y extrae el saldo de USDC real.
    Soporta Proxy Wallets (Cuentas de Email/Google) y Wallets Directas.
    """
    try:
        key = os.getenv("PRIVATE_KEY")
        proxy_wallet = os.getenv("PROXY_WALLET")
        
        if not key:
            app_logger.error("PRIVATE_KEY no encontrada en .env")
            return 0.0

        host = "https://clob.polymarket.com"
        chain_id = 137  # Mainnet de Polygon
        
        # 1. Configurar cliente dependiendo del tipo de billetera
        if proxy_wallet:
            # signature_type=2 es el código de Polymarket para Proxy Wallets
            client = ClobClient(host, key=key, chain_id=chain_id, signature_type=2, funder=proxy_wallet)
        else:
            client = ClobClient(host, key=key, chain_id=chain_id)
            
        # 2. Derivar credenciales
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        
        # 3. Consultar el balance de Colateral (USDC)
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        balance_data = client.get_balance_allowance(params=params)
        
        # Extraer el balance y ajustar los 6 ceros de USDC
        raw_balance = float(balance_data.get("balance", 0.0))
        balance = raw_balance / 1000000.0
        
        app_logger.info(f"LIVE_BALANCE_FETCHED=${balance}")
        return balance
        
    except Exception as e:
        app_logger.error(f"Error extrayendo saldo real de Polymarket: {e}")
        return 0.0