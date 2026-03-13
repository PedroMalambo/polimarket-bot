# Polymarket Bot

Bot de paper trading para Polymarket sobre Polygon, orientado a experimentación controlada en una instancia EC2.

## Estado actual

Proyecto funcional en modo **paper trading**.

Actualmente implementa:

- healthcheck contra Gamma API
- descubrimiento y ranking de mercados candidatos
- filtro por volumen mínimo
- filtro por spread máximo
- simulación de entrada
- persistencia de posiciones paper
- persistencia de trades paper
- snapshots de mercado
- resumen de portafolio
- control para no duplicar posiciones abiertas en el mismo mercado
- scripts operativos para arrancar, detener y revisar estado en EC2

## Estructura del proyecto

```text
src/
  config/
  clients/
  strategy/
  risk/
  execution/
  portfolio/
  monitoring/
  utils/
scripts/
docs/
data/
logs/
runtime/
```

