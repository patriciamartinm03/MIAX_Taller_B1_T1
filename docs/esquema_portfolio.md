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

_Actualizado: 5 de noviembre de 2026._

---

## Hecho

**Datos de la cartera**
- [x] Recibe un nombre, una lista de activos y sus pesos.
- [x] Pasa todos los precios a dólares (cada activo sabe convertirse, opción C) y se queda solo con las fechas comunes.

**Validaciones al crear la cartera**
- [x] Al menos un activo, y todos son series de precios.
- [x] Tantos pesos como activos.
- [x] Sin activos repetidos.
- [x] Todos los activos con el mismo tipo de precio (con o sin ajuste por dividendos).
- [x] Sin pesos negativos.
- [x] Los pesos suman 1.
- [x] Al menos 3 fechas comunes.

**Cálculos en `Portfolio`**
- [x] Rendimientos diarios de cada activo.
- [x] Rendimientos diarios de la cartera (con pesos constantes).
- [x] Simulación Monte Carlo, con supuestos históricos o introducidos a mano.

**En `metrics.py`**
- [x] Validación de una serie con fechas.
- [x] Rendimientos diarios.
- [x] Rentabilidad anual (media diaria × 252).
- [x] Volatilidad anual (desviación diaria × √252).
- [x] Drawdown máximo (solo el número, sin fechas).

**Tests**
- [x] De la conversión a dólares y de la cartera (en la rama `patricia-tests`).

---

## Falta en `metrics.py`

**Piezas básicas** (las usan varias métricas y la cartera):
- [ ] Rentabilidad total de una serie (último / primero − 1). La usan el CAGR, la cartera, el índice de referencia y el efecto del tipo de cambio.
- [ ] Valor acumulado a partir de rendimientos, empezando en un valor inicial. Lo usan el valor histórico de la cartera y el del índice de referencia.
- [ ] Serie de drawdown (caída desde el máximo en cada fecha). La usan el drawdown máximo y sus fechas.
- [ ] Anualizar una media diaria y una desviación diaria. Las usan la rentabilidad anual, la volatilidad anual y los supuestos de la simulación.
- [ ] Exceso de rentabilidad diario sobre el tipo sin riesgo. Lo usan el Sharpe y el Sortino.
- [ ] Diferencia diaria entre la cartera y el índice, en las fechas comunes. La usan el tracking error y el Information Ratio.

**Métricas:**
- [ ] CAGR con días naturales.
- [ ] Drawdown máximo con fechas de pico, valle y recuperación.
- [ ] Paso del tipo sin riesgo anual a diario, en unas fechas dadas.
- [ ] Sharpe sobre el exceso de rentabilidad diario.
- [ ] Sortino sobre el mismo exceso.
- [ ] Tracking error e Information Ratio.
- [ ] Número efectivo de activos.
- [ ] Probabilidad de pérdida, VaR y CVaR.

**Arreglar lo que ya hay para no repetir fórmulas:**
- [ ] Que la rentabilidad y la volatilidad anuales usen las funciones de anualizar.
- [ ] Que el drawdown máximo use la serie de drawdown.

---

## Falta en `Portfolio`

### Validaciones nuevas
- [ ] Que todos los pesos sean números válidos (ahora un peso vacío da un mensaje que despista).
- [ ] Que el mensaje de «pocas fechas comunes» diga desde cuándo tiene datos cada activo, para ver cuál recorta el periodo.
- [ ] Tipo sin riesgo: que esté en dólares, en porcentaje o decimal, y que cubra todo el periodo de la cartera.

### Reutilizar `metrics.py`
- [ ] Que los rendimientos de cada activo llamen a los rendimientos diarios de `metrics.py` en vez de repetir la fórmula.

### Tipo sin riesgo
- [ ] Que la cartera pueda recibir el tipo sin riesgo (letra del Tesoro a 3 meses de la FRED). Es opcional.
- [ ] Que dé el tipo diario de cada fecha de la cartera, o 0 si no se ha pasado.

### Composición
- [ ] Exposición por divisa: qué parte de la cartera está en cada divisa original.
- [ ] Número efectivo de activos de la cartera.

### Rendimiento y riesgo
- [ ] Valor histórico de la cartera, con y sin rebalanceo.
- [ ] Tabla de métricas: una fila por activo, otra para la cartera y otra para el índice de referencia si lo hay. Columnas: rentabilidad anual, CAGR, volatilidad, Sharpe, Sortino y drawdown máximo. Todo en dólares y en las fechas comunes.
- [ ] Fechas del drawdown máximo de la cartera.
- [ ] Efecto del tipo de cambio de cada activo que no está en dólares: rentabilidad en su divisa, variación del tipo de cambio y rentabilidad en dólares, en las fechas comunes.

### Índice de referencia
- [ ] Comparación con el índice: diferencias de CAGR, volatilidad y Sharpe, tracking error e Information Ratio, en las fechas comunes.
- [ ] Detectar si el índice no es adecuado (otro tipo de precio o no cubre todo el periodo), sin dar error, para que el report lo pueda avisar.

### Diversificación
- [ ] Matriz de correlaciones.
- [ ] Beneficio de la diversificación: media ponderada de las volatilidades de los activos menos la volatilidad de la cartera.

### Simulación
- [ ] Supuestos usados, anualizados: rentabilidad y volatilidad de cada activo.

### Conexión con `reporting`
- [ ] `report()` y `plots_report()` como métodos de la cartera (lo pide el enunciado), que solo pasan los datos a `reporting`.

### Tests
- [ ] De cada punto anterior, en `patricia-tests`.

---

## Pendiente

- [ ] Confirmar la opción C (tipo de cambio dentro de cada activo).
- [ ] Decidir si se incluye el índice de referencia.
- [ ] Decidir si los tests se suben al repo.
- [ ] Revisar y aceptar la PR de `patricia`.
- [ ] Que el extractor descargue el tipo de cambio de los activos que no están en dólares (sin eso, la cartera no puede crearse con activos europeos).
- [ ] Que el resultado de la simulación guarde el tipo de rebalanceo y los supuestos usados, para que la cartera pueda anualizarlos.
- [ ] Que el resultado de la simulación use la probabilidad de pérdida, el VaR y el CVaR de `metrics.py`.
- [ ] Decidir si se pasa a rebalanceo periódico (mensual o trimestral) en vez de diario. Si se hace, el valor histórico de la cartera debería usar el mismo.

---

## Orden propuesto

1. `metrics.py`: piezas básicas, métricas nuevas y arreglos.
2. Validaciones nuevas, reutilizar `metrics.py` y tipo sin riesgo.
3. Composición y valor histórico.
4. Tabla de métricas, fechas del drawdown y efecto del tipo de cambio.
5. Índice de referencia.
6. Diversificación.
7. Supuestos de la simulación (cuando el resultado de la simulación guarde los supuestos).
8. Conexión con `reporting`.

Después de cada paso: commit del código, commit de los tests y comprobar que todo pasa.
