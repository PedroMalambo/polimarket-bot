import requests
from datetime import datetime, timedelta, UTC
from src.monitoring.logger import app_logger

def get_whale_signals(target_address: str):
    """Rastrea movimientos de ballenas con la URL estándar de Gamma."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # La API de Polymarket prefiere la dirección en minúsculas
    address = target_address.lower()
    url = f"https://gamma-api.polymarket.com/activity?user={address}&limit=20"
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            # Si vuelve a dar 404, devolvemos lista vacía sin romper el bot
            return []

        activity = resp.json()
        valid_signals = []
        time_threshold = datetime.now(UTC) - timedelta(hours=6)

        for act in activity:
            if act.get('type') == 'ORDER_FILLED' and act.get('side') == 'BUY':
                ts_str = act.get('timestamp', '').replace('Z', '')
                try:
                    trade_time = datetime.fromisoformat(ts_str).replace(tzinfo=UTC)
                    if trade_time > time_threshold:
                        valid_signals.append(act)
                except:
                    continue
        
        if valid_signals:
            app_logger.info(f"🐳 WHALE: {len(valid_signals)} signals found.")
        return valid_signals

    except Exception as e:
        app_logger.error(f"Error Whale: {e}")
        return []