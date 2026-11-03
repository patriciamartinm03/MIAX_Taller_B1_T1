# Decisiones pendientes

Temas que han ido saliendo al revisar los PR #2 (modelos) y #3 (Monte Carlo) y que estaría bien cerrar entre los tres. Cada punto tiene el contexto, las opciones que se han visto y lo que implica cada una. La idea es ir rellenando la línea **Decisión** cuando lo cerremos.

_Última actualización: 3 de noviembre de 2026._

---

## ✅ Ya decidido

- **`price_type` obligatorio en `PriceSeries`**, sin valor por defecto. El extractor tiene que indicar siempre si el precio es de cierre normal (`close`) o ajustado (`adj_close`), para que no se cuele uno etiquetado como el otro.
- **`currency` obligatoria en `MacroSeries`**. Si un dato no tiene divisa (por ejemplo, un índice de inflación), se pasa `currency=None` explícitamente.
- **`TRADING_DAYS = 252` en `constants.py`**, para que cualquier módulo lo use sin depender de `PriceSeries`.
- **Sin `log_returns()` en `PriceSeries`**: la simulación trabaja con rendimientos simples y hace la conversión a logaritmos por dentro.
- **Exposición a divisa sin cubrir al 100 %**: los activos en otra divisa se convierten a la divisa base al tipo de cambio de cada día, sin cobertura. La cobertura queda como limitación o posible mejora en el README.

---

## 1. Datos y limpieza

### 1.1 Alineación de calendarios

El S&P 500 y el IBEX no abren los mismos días (cada mercado tiene sus festivos). Al juntarlos en una cartera hay que decidir qué hacer con los días en que solo abre uno.

- **Rellenar** el precio del mercado cerrado con el del día anterior. No se pierde ningún dato, pero ese día el activo marca un rendimiento del 0 % y al día siguiente recupera todo de golpe. La volatilidad sale más baja de lo real y, sobre todo, la correlación entre activos también. La cartera parece más diversificada de lo que está, y eso afecta al riesgo del report y al Monte Carlo.
- **Quitar** los días no comunes. Los datos son coherentes, pero se pierden algunas observaciones y el rendimiento del día siguiente a un festivo cubre dos días de mercado. Esto afecta a la anualización (ver 1.2).

Sea cual sea la opción, hay que alinear los **precios** antes de calcular rendimientos. Si se alinean los rendimientos ya calculados, el de después de un festivo cubre dos días en un activo y uno en el otro, y la covarianza sale mal.

Aunque los días coincidan, el IBEX cierra a las 17:30 y Wall Street a las 22:00 (hora de Madrid). Una noticia de por la tarde aparece en el precio de EE. UU. ese día y en el de España al siguiente, así que la correlación diaria entre mercados sale algo más baja de lo real. Esto no se arregla con datos diarios; lo habitual para correlaciones entre mercados es usar rendimientos semanales.

**Decisión:**

### 1.2 Anualización

Para pasar de diario a anual se multiplica la media por 252 y la volatilidad por √252. Eso supone un dato por cada día de bolsa.

- **A. 252 fijo.** Es la convención y lo más simple. Si al alinear quedan unos 240-245 días al año, sobreestima un poco el retorno (~3 %), la volatilidad (~1,5 %) y el Sharpe. Habría que explicar este error en el README.
- **B. Días por año reales de cada serie.** Se cuentan las observaciones por año en los propios datos y se usa ese número. Casi exacto y poco código, pero el factor puede cambiar ligeramente entre series y periodos.
- **C. Exacta.** Dar a cada rendimiento el peso de los días de mercado que cubre, usando el calendario oficial de cada bolsa (librerías como `exchange_calendars`). Es lo más preciso, pero añade una dependencia y bastante complejidad.

**Decisión:**

### 1.3 Dónde limpiamos los NaN

`PriceSeries` y `MacroSeries` rechazan datos con huecos, así que alguien tiene que limpiarlos antes de crear los objetos. El 4.5 pide rutinas de limpieza (NaN, alineación de calendarios…).

Si la limpieza está en un módulo propio, la decisión de qué hacer con cada hueco queda a la vista y se puede justificar. Si se hace dentro de cada extractor, cada fuente podría acabar limpiando de forma distinta.

**Decisión:**

### 1.4 Divisas

Ya está decidido que la exposición a divisa va **sin cubrir al 100 %**. Esto es lo que implica y lo que falta por concretar.

**Por qué importa.** Para un inversor en euros, tener el S&P 500 son dos apuestas: la del índice (en dólares) y la del dólar frente al euro. El rendimiento en euros es (1 + rendimiento en USD) × (1 + variación del tipo de cambio) − 1. Por ejemplo, si el S&P sube un 10 % en dólares y el dólar cae un 5 % frente al euro, el inversor europeo gana un 4,5 %, no un 10 %. Además cambian la volatilidad y las correlaciones: el EUR/USD tiene una volatilidad anual de en torno al 7-9 %, y como el dólar suele subir en las crisis, a veces el S&P en euros es menos volátil que en dólares. Si no convertimos, la cartera ignora todo esto.

**Por qué no limitamos a carteras de una sola divisa.** En la práctica es muy restrictivo:
- El enunciado pide índices como el S&P 500, el IBEX 35 o el Euro Stoxx 50. Con una sola divisa no se podrían combinar en una cartera, que es justo lo interesante.
- La diversificación internacional es uno de los motivos principales para construir una cartera. Quedarse en un solo mercado deja fuera buena parte del análisis.
- Para un inversor real, el riesgo divisa existe en cuanto compra algo fuera de su zona. Ignorarlo no lo elimina; solo hace que no se vea en los resultados.

**Divisa base.** Es la divisa en la que se miden los resultados de la cartera. Puede ser fija (EUR) o un parámetro de `Portfolio`.

**Tipo de cambio.**
- Hay que descargarlo como una serie más (en yfinance, el par EUR/USD es `EURUSD=X`).
- Ojo con la convención: EUR/USD = 1,08 significa que 1 euro vale 1,08 dólares. Para pasar un precio en dólares a euros se **divide** entre el tipo de cambio. Si se multiplica, todo sale al revés sin que salte ningún error, así que conviene comprobarlo con un dato conocido.
- El mercado de divisas opera casi 24 horas de lunes a viernes, así que tiene dato los días de festivo bursátil. Basta con quedarse con las fechas de los activos.
- El cierre diario del tipo de cambio no coincide exactamente con el de cada bolsa. Es un desfase pequeño, pero es otra limitación para el README.

**Cómo encaja en el código.**
- El tipo de cambio es un precio (siempre positivo), así que encajaría en `PriceSeries`, pero ahora `asset_type` solo admite `equity`, `etf` e `index`. Habría que añadir un tipo para divisas o guardarlo en `MacroSeries` con `units="level"`.
- Una forma limpia de convertir es una función de preprocesado que reciba un `PriceSeries` en una divisa y el tipo de cambio, alinee fechas y devuelva un nuevo `PriceSeries` en la divisa base. Así `Portfolio` solo recibe activos en la misma divisa.
- `Portfolio` podría comprobar que todos sus activos están en la misma divisa y dar error si no, para que nadie mezcle sin convertir por despiste.
- El campo `currency` tiene que ser la divisa en la que cotiza ese dato concreto. Un ETF del S&P que cotiza en Madrid ya viene en euros (con el efecto divisa incluido); el índice `^GSPC` viene en dólares.

**Efecto en el Monte Carlo.** Si `mu` y `cov` se calculan con los rendimientos ya convertidos a la divisa base, la simulación incluye automáticamente el riesgo divisa y su correlación con los activos, sin tocar el motor. Si se calculan en divisa local, la simulación ignora el riesgo divisa.

**Efecto en el report.** Cada cifra debería indicar su divisa. Se podría mostrar qué parte de la cartera está expuesta a otra divisa y añadir una advertencia por esa exposición sin cubrir.

**A decidir:**
- Divisa base: fija o parámetro.
- Dónde guardamos el tipo de cambio (`PriceSeries` con un tipo nuevo o `MacroSeries`).
- Dónde se hace la conversión (preprocesado o `Portfolio`).

**Decisión:**

### 1.5 Tipo sin riesgo

Es el dato adicional del 4.2 y sirve para calcular el Sharpe con `MacroSeries`. Tiene que ser de la misma divisa en la que se miden los rendimientos:
- **Sharpe de cada activo en su divisa:** FRED para activos en USD, BCE para activos en EUR.
- **Sharpe de la cartera:** como todo se convierte a la divisa base (ver 1.4), se usa el tipo sin riesgo de la divisa base, aunque haya activos de otros países dentro. Es fácil mezclarlo, así que conviene dejarlo claro.

Al alinearlo con los precios sí tiene sentido rellenar hacia delante, porque un tipo sigue vigente hasta que cambia. Es justo lo contrario que con los precios, y sirve para justificar en el README que cada dato se limpia según lo que significa.

**A decidir:** qué serie concreta usamos de cada fuente (por ejemplo, letra del Tesoro a 3 meses en la FRED, €STR o tipo de depósito en el BCE).

**Decisión:**

### 1.6 Extractor

Las validaciones de las clases dependen de que el extractor ponga bien los campos:

- **Unidades:** cada fuente llama a sus unidades a su manera («Percent», «Percent per annum»…) y hay que traducirlas a las de `MacroSeries`. Si se confunde porcentaje con decimal, el Sharpe sale disparatado.
- **Tipo de precio:** hay que saber si el precio viene ajustado o no. Con yfinance hay que mirarlo, porque en versiones recientes ajusta los precios por defecto.

**Decisión:**

---

## 2. Modelos

### 2.1 Validaciones repetidas

`PriceSeries` y `MacroSeries` comprueban lo mismo: que sea una Series, que tenga fechas, que sea numérica, sin NaN y sin fechas repetidas.

Sacarlo a una función común evita mantener lo mismo en dos sitios (si se cambia una comprobación, se cambia en ambas). Dejarlo así es más simple de leer en cada clase, pero hay riesgo de que se desincronicen.

**Decisión:**

### 2.2 `metrics.py`

`Portfolio` necesita las mismas fórmulas que `PriceSeries` (rendimiento y volatilidad anuales, drawdown), pero aplicadas al valor de la cartera. Si solo existen como métodos de `PriceSeries`, habrá que reescribirlas en `Portfolio`. Tenerlas como funciones en un módulo `metrics.py` permite que las dos clases usen las mismas.

**Decisión:**

### 2.3 Unidades de `MacroSeries`

- **Sencilla:** `units` limitado a cuatro textos (`percent`, `decimal`, `index`, `level`) y error si algo marcado como `decimal` parece un porcentaje.
- **Robusta:** lo mismo con un `Enum` (lista cerrada con autocompletado, sin errores de tecleo) y un aviso también en el sentido contrario. Más segura, pero añade un concepto nuevo y más código.

Para el extractor, las dos implican lo mismo: traducir las unidades de cada fuente.

**Decisión:**

### 2.4 CAGR en el report

`annual_return` es la media aritmética anualizada, que es la que se usa para simular y para el Sharpe. La rentabilidad compuesta (CAGR), que es lo que de verdad se ganó al año, sale algo más baja cuando hay volatilidad. Mostrar solo la aritmética puede dar una imagen algo optimista; mostrar las dos es más completo pero hay que explicar la diferencia.

**A decidir:** si mostramos también el CAGR en el report (se calcula con el primer y el último precio).

**Decisión:**

---

## 3. Monte Carlo

### 3.1 Activo individual

El 4.4 pide que la simulación sirva para un activo y para la cartera. Una opción es tratar un activo suelto como una cartera de un solo activo con peso 1, que no necesita código aparte. La otra es un método o función específica para un activo, más directa de usar pero que duplica parte de la lógica.

**Decisión:**

### 3.2 Rebalanceo

- **Rebalanceo diario:** los pesos vuelven a los iniciales cada día. Mantiene el reparto de riesgo elegido durante toda la simulación, pero nadie lo hace en la realidad por los costes de transacción.
- **Comprar y mantener:** los pesos cambian con los precios. Es lo más realista para un inversor pasivo, pero la cartera se va concentrando en lo que más sube, y con ello su riesgo.
- En la práctica lo habitual es rebalancear cada mes o cada trimestre, a medio camino entre las dos.

Los resultados cambian algo según la opción, así que hay que decir en el README cuál se usa.

**A decidir:** si tenemos las dos opciones, cuál va por defecto y cómo lo justificamos.

**Decisión:**

### 3.3 Colas gruesas

La simulación usa una distribución normal, que casi nunca genera días extremos. En los mercados reales pasan más de lo que predice una normal (por ejemplo, el S&P 500 cayó cerca de un 12 % en un día en marzo de 2020). Por eso el VaR y la probabilidad de pérdida salen algo optimistas.

- **Dejarlo como limitación** en el README y en el report. Sin cambios en el código.
- **Usar una t de Student.** Pocas líneas y mantiene volatilidad y correlaciones. Mejora los días extremos, pero el VaR a un año casi no cambia.
- Lo que más pesa en las crisis reales es que los días malos vienen seguidos durante semanas, y eso no lo captura ninguna de las dos. Haría falta un modelo tipo GARCH, bastante más complejo.

**Decisión:**

### 3.4 De dónde salen `mu` y `cov`

La simulación necesita el rendimiento medio diario de cada activo y la matriz de covarianzas, ambos en datos **diarios** (si se pasan anuales, los resultados salen absurdos sin que salte ningún error). Tienen que calcularse sobre los precios ya alineados en `Portfolio`, para que estén sobre las mismas fechas. Depende de lo que decidamos en 1.1.

**Decisión:**

---

## 4. Report y gráficos

### 4.1 `.plots_report()`

**A decidir:** quién lo hace. Si los gráficos devuelven el `ax` en vez de mostrarse directamente, se pueden combinar en una sola figura (trayectorias, distribución, correlaciones, evolución de la cartera) y guardarse como imagen para el README o la presentación.

**Decisión:**

### 4.2 Idioma

El código va en inglés. Ahora los gráficos están en español. La presentación es en español, pero el resto del repo está en inglés, y lo importante es que sea coherente.

**A decidir:** si lo que ve el usuario (gráficos y report) va en inglés o en español.

**Decisión:**

### 4.3 Advertencias de riesgo del `.report()`

El 4.5 pide incluir diagnósticos y advertencias de riesgo. Candidatas: VaR y probabilidad de pérdida de la simulación, drawdown máximo histórico y limitaciones del modelo (colas gruesas, rebalanceo, calendarios).

**Decisión:**

---

## 5. Repo y proceso

### 5.1 Orden de merge

El PR #3 (Monte Carlo) lleva una copia del código anterior del PR #2 (modelos), porque se creó a partir de esa rama. Si se mergea primero el #2, falta confirmar si hay que actualizar la rama del #3 con `main` antes de mergearlo o si hay que hacer algo más, para que no se pisen versiones.

**Decisión:**

### 5.2 Emails del `pyproject.toml`

Con `email = ""` la instalación falla con setuptools. Hay que rellenarlos o quitarlos para cumplir el «clonar y ejecutar» del 4.1.

**Decisión:**

---

## 6. Justificaciones para el README

Cosas que salen de lo anterior y que habrá que explicar:

- [ ] **Validación estricta de inputs (4.5):** por qué preferimos que falle al crear el objeto con un mensaje claro antes que calcular resultados erróneos sin avisar.
- [ ] **Limpieza según el tipo de dato:** los precios no se rellenan; los tipos de interés sí.
- [ ] **Anualización:** qué opción elegimos y el error que queda.
- [ ] **Rebalanceo:** qué supone cada opción y cuál va por defecto.
- [ ] **Divisas:** por qué convertimos a una divisa base sin cubrir y por qué no limitamos a carteras de una sola divisa.
- [ ] **Limitaciones del modelo:** horas de cierre distintas entre mercados (y del tipo de cambio), colas gruesas, que no se capta que las crisis duren semanas y que no se modela la cobertura de divisa.
