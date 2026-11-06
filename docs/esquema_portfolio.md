# Portfolio: qué está hecho, qué falta y qué hay que coordinar

Los cálculos que tiene que hacer `Portfolio` para que el report tenga todo lo que necesita. Qué se muestra y cómo está en `reporting` (ver `report_explicado.md`); aquí solo están los cálculos.

## Cómo se reparte el trabajo

| Dónde | Qué va | Por qué |
|---|---|---|
| `metrics.py` | Las fórmulas que se usan en más de un sitio: rentabilidades, anualizar, CAGR, Sharpe, drawdown, VaR… Funciones que reciben datos y devuelven un número o una serie, sin saber nada de carteras. | Cada fórmula se escribe una sola vez. Si hay que corregirla, se corrige en un sitio, y las series de precios, la cartera y la simulación dan siempre el mismo resultado. |
| `models/portfolio.py` | Lo propio de la cartera: sus datos y validaciones, pasar los activos a dólares y alinear fechas, y todo lo que depende de tener varios activos con pesos (valor histórico, composición, tabla de métricas, comparación con el índice, correlaciones, supuestos de la simulación). Para las fórmulas, llama a `metrics.py`. | La cartera sabe calcular cosas sobre sí misma, igual que la serie de precios calcula su media al crearse. Que esté en `models` no cambia nada: la carpeta agrupa las clases que representan cosas del programa, no dice si calculan o no. |
| `reporting/` | Cómo se enseña: formato de números y tablas, texto y orden de las secciones, qué se muestra y qué no, advertencias y gráficos. | Se puede cambiar el formato sin tocar las fórmulas, y los cálculos se prueban sin generar ningún report. |

Para decidir dónde va algo:
- **¿Se usa en más de un sitio?** → `metrics.py`.
- **¿Es propio de la cartera?** → `Portfolio`.
- **¿Cambiaría si el report fuera en HTML en vez de Markdown?** → `reporting`.

`Portfolio` devuelve siempre números en decimal (0,0523, no «5,23 %»), series y tablas; poner el formato es cosa de `reporting`.

Las importaciones van en una sola dirección: `Portfolio` importa de `metrics.py` y de `reporting`, y `reporting` no importa `Portfolio`: recibe la cartera como parámetro y usa sus métodos. Si los dos se importaran mutuamente, Python daría error al cargarlos.

_Actualizado: 6 de noviembre de 2026._

---

## Hecho

### En `metrics.py`

**Validaciones comunes**
- [x] Validación de una serie (con fechas o sin ellas, solo positiva si hace falta) y de un número.

**Piezas básicas**
- [x] Rendimientos diarios, de una serie o de una tabla con varios activos (`daily_returns`).
- [x] Rentabilidad total (`total_return`).
- [x] Valor acumulado a partir de rendimientos, empezando en un valor inicial (`cumulative_value`).
- [x] Serie de drawdown (`drawdown_series`).
- [x] Anualizar una media diaria y una desviación diaria (`annualize_mean`, `annualize_volatility`).
- [x] Exceso de rentabilidad diario sobre el tipo sin riesgo, constante o día a día (`excess_returns`).
- [x] Diferencia diaria entre la cartera y el índice, en las fechas comunes (`active_returns`).

**Métricas**
- [x] Rentabilidad y volatilidad anuales, usando las funciones de anualizar (`annual_return`, `annual_volatility`).
- [x] CAGR con días naturales (`cagr`).
- [x] Drawdown máximo, usando la serie de drawdown (`max_drawdown`), y con fechas de pico, valle y recuperación (`max_drawdown_details`).
- [x] Paso del tipo sin riesgo anual a diario, en unas fechas dadas (`daily_risk_free`).
- [x] Sharpe y Sortino sobre el exceso de rentabilidad diario.
- [x] Tracking error e Information Ratio.
- [x] Número efectivo de activos.
- [x] Probabilidad de pérdida, VaR y CVaR (`prob_loss`, `value_at_risk`, `expected_shortfall`).

### En `Portfolio`

**Datos de la cartera**
- [x] Recibe un nombre, una lista de activos, sus pesos y, si se quiere, el tipo sin riesgo.
- [x] Pasa todos los precios a dólares (cada activo sabe convertirse, opción C) y se queda solo con las fechas comunes.

**Validaciones al crear la cartera**
- [x] Al menos un activo, y todos son series de precios.
- [x] Tantos pesos como activos.
- [x] Sin activos repetidos.
- [x] Todos los activos con el mismo tipo de precio (con o sin ajuste por dividendos).
- [x] Todos los pesos son números finitos, y el mensaje dice qué activo falla.
- [x] Sin pesos negativos.
- [x] Los pesos suman 1.
- [x] Al menos 3 fechas comunes; si no, el mensaje dice desde y hasta cuándo tiene datos cada activo.
- [x] Tipo sin riesgo: que sea un `MacroSeries`, en dólares, en porcentaje o decimal, y que empiece antes que la cartera.

**Tipo sin riesgo**
- [x] Tipo diario de cada fecha de la cartera, o 0 si no se ha pasado (`risk_free_daily`).
- [x] Tipo medio anual del periodo de la cartera (`risk_free_mean`).

**Rendimientos**
- [x] Rendimientos diarios de cada activo, con `metrics.daily_returns` (`asset_returns`).
- [x] Rendimientos diarios de la cartera, con pesos constantes (`returns`).

**Composición**
- [x] Exposición por divisa (`currency_exposure`).
- [x] Número efectivo de activos (`effective_n_assets`).

**Rendimiento y riesgo**
- [x] Valor histórico de la cartera, con y sin rebalanceo (`value`).
- [x] Fechas del drawdown máximo de la cartera (`drawdown_details`).
- [x] Tabla de métricas: una fila por activo, otra para la cartera y otra para el índice si lo hay, en dólares y en las fechas comunes (`metrics_table`).
- [x] Efecto del tipo de cambio de cada activo que no está en dólares (`currency_attribution`).

**Índice de referencia**
- [x] Comparación con el índice: diferencias de CAGR, volatilidad y Sharpe, tracking error e Information Ratio, en las fechas comunes (`benchmark_comparison`).
- [x] Detectar si el índice no es adecuado (otro tipo de precio o no cubre todo el periodo), sin dar error (`benchmark_issues`).
- [x] Posiciones en común con el índice (`benchmark_overlap`, `benchmark_overlap_share`).

**Diversificación**
- [x] Matriz de correlaciones (`correlation`).
- [x] Beneficio de la diversificación (`diversification_benefit`).

**Simulación**
- [x] Simulación Monte Carlo, con supuestos históricos o introducidos a mano, y con o sin rebalanceo (`monte_carlo`).
- [x] Validación de `mu` y `cov` introducidos a mano: un valor por activo, finitos, sin varianzas negativas y sin valores que parezcan anuales.
- [x] Supuestos usados, anualizados: rentabilidad y volatilidad de cada activo (`simulation_assumptions`).

### Tests
- [x] De `metrics.py` y de todo lo anterior de `Portfolio` (en la rama `patricia-tests`).

---

## Pendiente

### En `Portfolio`
- [ ] `report()` y `plots_report()` como métodos de la cartera (lo pide el enunciado), que solo pasan los datos a `reporting`.

### En el resultado de la simulación (`models/results.py`, hay que hablarlo con el grupo)
- [ ] Que guarde el tipo de rebalanceo usado.
- [ ] Que guarde los supuestos usados (`mu` y `cov` diarios), para que la cartera pueda anualizarlos a partir del resultado.
- [ ] Que tenga el CVaR, y que calcule la probabilidad de pérdida, el VaR y el CVaR con las funciones de `metrics.py` en vez de repetir las fórmulas.

### Tests
- [ ] De cada punto anterior, en `patricia-tests`.

---

## Orden

1. Resultado de la simulación: rebalanceo, `mu`, `cov` y CVaR (después de acordarlo con el grupo).
2. Que los supuestos de la simulación se puedan sacar del resultado.
3. Conexión con `reporting`: `report()` y `plots_report()`.

Después de cada paso: commit del código, commit de los tests y comprobar que todo pasa.
