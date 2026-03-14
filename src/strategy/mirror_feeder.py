import requests
from src.monitoring.logger import app_logger

def get_whale_signals(target_address: str):
    """Busca los últimos movimientos de la ballena para alimentar a OpenClaw."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    }
    url = f"https://gamma-api.polymarket.com/activity?user={target_address}&limit=10"
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            activity = resp.json()
            # Filtramos solo compras confirmadas
            buys = [a for a in activity if a.get('type') == 'ORDER_FILLED' and a.get('side') == 'BUY']
            return buys
        return []
    except Exception as e:
        app_logger.error(f"Error al rastrear ballena: {e}")
        return []