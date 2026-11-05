# Esquema del report de cartera (resumen)

Contexto: toolkit en Python que analiza una cartera de acciones, ETF e índices. Divisa base: USD (los activos en otra divisa se convierten sin cubrir). Datos diarios. Report en Markdown generado por `Portfolio.report()`, más gráficos con `Portfolio.plots_report()`.

Orden: pirámide invertida (de lo general a lo técnico).

Índice de referencia (benchmark): opcional, lo elige el usuario. Es una cartera compuesta de ETF por región con los mismos pesos por región que la cartera (ej.: 60 % SPY + 40 % FEZ). Mismo tipo de precio (ajustado por dividendos), mismo periodo y en USD.

---

## 0. Cabecera
- Nombre de la cartera
- Fecha de generación
- Periodo analizado (fechas comunes) y nº de observaciones
- Divisa base (USD)
- Fuente de datos
- Índice de referencia: nombre y composición (ETF y pesos)

## 1. Resumen (cartera vs. índice de referencia)
- Rentabilidad total del periodo
- CAGR
- Volatilidad anual
- Ratio de Sharpe
- Drawdown máximo
- Diferencia de CAGR cartera − índice
- Information Ratio
- Nº de advertencias activas

## 2. Composición y exposiciones
- Tabla de activos: ticker, nombre, tipo, divisa original, peso
- Exposición por divisa (% USD, % EUR…)
- Concentración: peso máximo y nº efectivo de activos (1 / Σ pesos²)
- Exposición por región de la cartera vs. composición del índice de referencia

## 3. Rendimiento y riesgo histórico (en USD)
Tabla: una fila por activo + fila cartera + fila índice de referencia.
- Rentabilidad anual (media aritmética × 252)
- CAGR (días naturales)
- Volatilidad anual (σ diaria × √252)
- Sharpe (sobre el exceso diario frente al tipo sin riesgo)
- Sortino (mismo exceso diario; solo riesgo a la baja)
- Drawdown máximo

Descomposición del efecto del tipo de cambio (activos que no cotizan en USD):
- Rentabilidad en divisa local
- Variación del tipo de cambio (USD por unidad de divisa)
- Rentabilidad en USD: (1 + R_local) × (1 + R_fx) − 1

Debajo:
- Drawdown máximo de la cartera: fecha de pico, valle y recuperación
- Tipo sin riesgo usado (letra del Tesoro a 3 meses, FRED; media del periodo)

Comparación con el índice de referencia:
- Diferencia de CAGR, volatilidad y Sharpe
- Tracking error: σ(R_cartera − R_índice) × √252
- Information Ratio: media anualizada de (R_cartera − R_índice) / tracking error (definición CFA)

## 4. Diversificación
- Matriz de correlaciones
- Beneficio de la diversificación: media ponderada de volatilidades − volatilidad de la cartera
- (No se muestra con un solo activo)

## 5. Simulación Monte Carlo (solo cartera)
Supuestos:
- Rentabilidad y volatilidad anualizadas de cada activo
- Históricos o introducidos por el usuario
- Rebalanceo (diario o comprar y mantener)
- Nº de simulaciones, horizonte, valor inicial, semilla

Resultados:
- Percentiles 5, 25, 50, 75, 95 del valor final
- Probabilidad de pérdida
- VaR 95 %
- CVaR 95 %

## 6. Advertencias
Automáticas (umbrales configurables):
- Correlación > 0,8 entre dos activos
- Peso máximo > 40 % o nº efectivo de activos < 3
- Exposición a divisa sin cubrir
- Drawdown máximo peor que −20 %
- Histórico < 5 años
- Sharpe negativo
- Sin tipo sin riesgo (Sharpe y Sortino calculados con tipo 0)
- Índice de referencia con distinto tipo de precio o que no cubre todo el periodo

Fijas:
- Distribución normal: VaR y CVaR optimistas (colas gruesas)
- Rebalanceo diario: ignora costes de transacción e impuestos
- Las correlaciones suben en las crisis
- Supuestos estimados con datos pasados
- Rentabilidades pasadas no garantizan rentabilidades futuras

## 7. Notas metodológicas
- Rendimientos simples diarios, tras alinear fechas comunes
- Anualización con 252 días
- CAGR con días naturales (365,25)
- Media aritmética para Sharpe, Sortino y simulación; CAGR para el crecimiento acumulado
- Sharpe y Sortino sobre el exceso diario: tipo sin riesgo anual / 252, rellenado hacia delante en los días sin dato
- Conversión a USD al tipo de cambio diario, sin cubrir
- Tipo sin riesgo: letra del Tesoro a 3 meses (FRED)
- Information Ratio: definición CFA (exceso sobre el índice / tracking error)
- Simulación: movimiento browniano geométrico multivariante
- Índice de referencia: ETF por región, ponderado como la cartera

---

## Gráficos (`plots_report()`)
- Evolución en base 100: cartera, índice de referencia y activos
- Drawdown en el tiempo: cartera vs. índice de referencia
- Mapa de calor de correlaciones
- Trayectorias simuladas con percentiles
- Distribución del valor final (valor inicial y VaR marcados)

## Posibles mejoras
- Rebalanceo periódico (mensual o trimestral) en la simulación
- Distribución con colas gruesas (t de Student) o remuestreo de rendimientos históricos en la simulación
- Beta y alfa frente al índice de referencia

## Fuera del alcance
- Active Share: la cartera y el índice (ETF por región) no comparten posiciones, saldría siempre cerca del 100 %
- Liquidez por volumen medio diario: activos muy líquidos y sin dinero real
- Des-suavizado de la volatilidad: solo para activos con precios de tasación, no para acciones y ETF
- Comisiones, ISIN, avisos legales
