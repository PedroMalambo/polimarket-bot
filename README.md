## Polymarket Bot

Bot de paper trading para Polymarket sobre Polygon.

## Estado actual
Proyecto funcional en modo paper trading.

## Funcionalidades implementadas
- Healthcheck contra Gamma API
- Descubrimiento y ranking de mercados candidatos
- Filtro por volumen mínimo
- Filtro por spread máximo
- Simulación de entrada
- Persistencia de posiciones en papel
- Persistencia de trades en papel
- Snapshots de mercado
- Resumen de portafolio
- Control para no duplicar posiciones abiertas en el mismo mercado
- Scripts operativos para arrancar, detener y revisar estado

## Estructura
- `src/config`: configuración
- `src/clients`: clientes HTTP / APIs
- `src/strategy`: selección/ranking
- `src/risk`: sizing, kill switch, reglas
- `src/execution`: ejecución paper/live
- `src/portfolio`: posiciones, trades, account state
- `src/monitoring`: logs, alertas, métricas
- `src/utils`: helpers
- `scripts`: operación EC2
- `data`: snapshots y portfolio
- `logs`: logs de ejecución
- `docs`: documentación operativa

## Ejecución local
```bash
cd /home/ubuntu/projects/polymarket-bot
source .venv/bin/activate
python main.py