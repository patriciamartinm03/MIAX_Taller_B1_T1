# Cómo está pensado el report

Este documento explica qué sale en el report de la cartera, en qué orden y por qué lo he planteado así. La idea es que cualquiera que lea el código o el report entienda de dónde sale cada número y por qué está ahí.

## La idea general

Para decidir el orden me fijé en cómo se presentan los informes de fondos y carteras de verdad. Casi todos van de lo general a lo concreto: primero qué es la cartera y cómo le ha ido, y luego el detalle. Tiene sentido, porque si alguien solo lee el principio ya se lleva lo importante, y si quiere entrar en detalle puede seguir.

Así que el report va en este orden:

1. Cabecera: qué cartera es, de qué periodo y con qué se compara.
2. Resumen: cómo le ha ido en pocas cifras.
3. Composición: dónde está invertido el dinero.
4. Rendimiento y riesgo: los números de cada activo, de la cartera y del índice de referencia.
5. Diversificación: si los activos se compensan entre sí.
6. Simulación: qué podría pasar en el futuro.
7. Advertencias: qué hay que tener en cuenta al leer todo lo anterior.
8. Notas de cómo se ha calculado.

La composición va antes que los números porque los explica. Lo que más influye en cómo le va a una cartera es en qué está invertida, así que tiene sentido ver eso primero. La diversificación va después porque explica algo que se ve en la tabla de rendimientos: que la cartera suele tener menos riesgo que la mayoría de sus activos por separado.

Todos los números salen de `Portfolio`, de las funciones de métricas o del resultado de la simulación, y el report solo los ordena y les da formato. Así los cálculos se pueden probar por separado, y si algún día se quiere el report en otro formato no hay que tocar las fórmulas.

Todo está en dólares.

## 1. Cabecera

Aquí va el nombre de la cartera, la fecha en que se genera el report, el periodo que se analiza, cuántos días de datos hay, la divisa, de dónde salen los datos y, si lo hay, el índice de referencia con su composición.

Puede parecer información de relleno, pero sin ella los números no se pueden interpretar. El periodo, por ejemplo, lo cambia todo: no es lo mismo analizar unos años que incluyen la crisis de 2008 que unos años tranquilos. Y el número de días sirve para saber cuánto fiarse de los resultados; con poco histórico, las medias son poco fiables (por eso hay una advertencia para eso).

El periodo es el de las fechas comunes a todos los activos. Si un activo empieza en 2015 y otro en 2018, la cartera solo se puede analizar desde 2018.

## 2. Resumen

Pocas cifras de la cartera, con las del índice de referencia al lado:

- **Rentabilidad total:** cuánto ha ganado o perdido el dinero en todo el periodo. Es lo más fácil de entender.
- **CAGR:** esa misma rentabilidad pero por año, para poder comparar periodos de distinta duración.
- **Volatilidad anual:** la medida de riesgo más habitual.
- **Sharpe:** si lo que se ha ganado compensa el riesgo que se ha asumido.
- **Drawdown máximo:** la peor caída desde un máximo. Es probablemente la medida de riesgo que mejor se entiende: «en el peor momento llegaste a perder un 30 %».
- **Diferencia de CAGR con el índice:** responde a lo primero que se pregunta cualquiera, que es si habría sido mejor comprar el mercado y ya.
- **Information Ratio:** si esa diferencia con el índice compensa lo que la cartera se ha separado de él (más abajo lo explico).
- **Número de advertencias:** para que quien lea sepa desde el principio que hay cosas que mirar al final.

## 3. Composición

Una tabla con cada activo: ticker, nombre, tipo (acción, ETF o índice), divisa en la que cotiza y peso en la cartera.

Debajo:

- **Exposición por divisa:** qué parte de la cartera está en activos en dólares y qué parte en euros u otras divisas. Como en el grupo decidimos no cubrir el riesgo de divisa, me parece importante mostrar cuánto hay.
- **Peso máximo:** para ver de un vistazo si un activo domina la cartera.
- **Número efectivo de activos:** es 1 dividido entre la suma de los pesos al cuadrado. Lo que dice es a cuántos activos con el mismo peso equivale la cartera.
Por ejemplo, una cartera con cinco activos pero con un 80 % en uno solo equivale a algo menos de dos. Resume la concentración en un número que se entiende creo.
- **Regiones de la cartera frente a las del índice de referencia:** para que se vea que el índice está bien elegido. (depende de si hacemos lo del indice autocreado en base a los etfs por regiones)

## 4. Rendimiento y riesgo

Es la parte central. Una tabla con una fila para cada activo, otra para la cartera y otra para el índice de referencia. Poner la cartera al lado de sus activos sirve para ver el efecto de diversificar.

Las columnas:

- **Rentabilidad anual:** la media de los rendimientos diarios multiplicada por 252.
- **CAGR:** el crecimiento compuesto anual, lo que de verdad creció el dinero.
- **Volatilidad anual:** la desviación típica diaria multiplicada por la raíz de 252.
- **Sharpe** y **Sortino**.
- **Drawdown máximo.**

Muestro la rentabilidad anual y el CAGR a la vez a propósito, porque no son lo mismo y cada una sirve para una cosa. La rentabilidad anual es una media aritmética: es la que se usa para calcular el Sharpe y para la simulación. El CAGR es una media geométrica: es la que dice cuánto ha crecido el dinero. Cuando hay volatilidad, el CAGR siempre sale más bajo (más o menos, la media menos la mitad de la varianza). Un ejemplo sencillo: si algo sube un 50 % y luego baja un 50 %, la media aritmética es 0 %, pero en realidad has perdido un 25 %.

**Sobre el Sharpe.** Es la rentabilidad que se obtiene por encima del tipo sin riesgo, dividida entre la volatilidad. Como tipo sin riesgo: la letra del Tesoro de EE. UU. a 3 meses, que se saca de la FRED. Es lo más parecido a invertir en dólares sin riesgo a corto plazo, y encaja con que la cartera esté en dólares. El bono a 10 años no sirve para esto porque tiene riesgo si cambian los tipos de interés.

Como el tipo sin riesgo cambia a lo largo del periodo, no resto una media al final. Lo que hago es restar a cada día su tipo (el anual entre 252) y calcular el Sharpe sobre esa serie de diferencias. Es como lo recomienda el propio Sharpe cuando el tipo no es constante. Si el tipo no cambiara, saldría lo mismo que con la fórmula de siempre.

**Sobre el Sortino.** Es como el Sharpe, pero en el denominador solo cuenta el riesgo de las caídas. El Sharpe penaliza igual una subida brusca que una bajada, y para un inversor no es lo mismo. Lo pongo como complemento.

**El efecto del tipo de cambio.** Para cada activo que no cotiza en dólares, separo tres cosas: lo que ha hecho el activo en su divisa, lo que ha variado el tipo de cambio y lo que ha quedado en dólares. Se relacionan así:

(1 + rentabilidad en dólares) = (1 + rentabilidad en su divisa) × (1 + variación del tipo de cambio)

>>Por ejemplo, si un activo europeo sube un 10 % en euros pero el euro cae un 5 % frente al dólar, en dólares solo ha ganado un 4,5 %. Sin esta separación el report no podría explicar por qué. Como no cubrimos la divisa, me parecía necesario mostrarlo. Y con la forma en que se guardan los datos (cada activo tiene sus precios originales y su tipo de cambio) sale casi sin esfuerzo.

**Debajo de la tabla**, para la cartera, pongo las fechas del drawdown máximo: cuándo fue el pico, cuándo el punto más bajo y cuándo se recuperó (o si no se ha recuperado todavía). Ayuda a ponerlo en contexto, por ejemplo si fue la caída de 2020, y a ver cuánto se tardó en salir. También pongo el tipo sin riesgo medio del periodo, porque el Sharpe depende de él y sin verlo no se puede comprobar.

**Comparación con el índice de referencia.** Además de las diferencias de CAGR, volatilidad y Sharpe, añado dos medidas:

- **Tracking error:** cuánto se separa la cartera del índice. Es la volatilidad de la diferencia de rendimientos diarios entre los dos. Si es muy bajo, la cartera prácticamente copia al índice.
- **Information Ratio:** lo que la cartera gana de más sobre el índice, dividido entre el tracking error. Es como un Sharpe pero frente al índice. Hay libros que lo definen de otra forma, con el alfa; yo uso la definición del CFA porque es la más habitual cuando hay un índice de referencia.

Comparar con un índice solo mirando el CAGR se queda corto: una cartera puede ganar algo más que el índice a costa de separarse muchísimo de él, y eso hay que verlo.

## 5. Diversificación

La matriz de correlaciones entre los activos. Diversificar solo funciona si los activos no se mueven a la vez; si todos tienen correlaciones de 0,9, en la práctica es como tener uno solo.

También calculo cuánto riesgo se ha eliminado al combinarlos: la media ponderada de las volatilidades de cada activo menos la volatilidad de la cartera. Si los activos se movieran exactamente igual, esto daría 0.

Si la cartera tiene un solo activo, esta parte no sale.

## 6. Simulación

La simulación es solo de la cartera. El índice de referencia sirve para comparar el pasado, no para proyectar.

Primero muestro los supuestos y luego los resultados, porque los resultados no significan nada sin saber de qué parten. Los supuestos son la rentabilidad y la volatilidad de cada activo (pasadas a anuales para que se entiendan, porque «0,04 % diario» no dice mucho), si son las históricas o las ha puesto el usuario, si la cartera se rebalancea, el número de simulaciones, el horizonte, el valor inicial y la semilla. La semilla es para que se pueda repetir la simulación y dé lo mismo.

Los resultados:

- **Percentiles 5, 25, 50, 75 y 95 del valor final:** el rango de lo que podría pasar. El 50 es el escenario central.
- **Probabilidad de pérdida:** en qué porcentaje de las simulaciones se acaba con menos dinero del que se puso.
- **VaR al 95 %:** la pérdida que solo se supera en el 5 % de los peores escenarios.
- **CVaR al 95 %:** la pérdida media dentro de ese 5 % peor.

Pongo el VaR y el CVaR juntos porque el VaR dice dónde empiezan los peores escenarios, pero no cómo de malos son. El CVaR sí. De hecho, los reguladores han ido pasando del VaR al CVaR por eso.

Si el VaR sale negativo (es decir, incluso en el 5 % peor de los casos se gana dinero), lo pongo con palabras en vez de con un número negativo, que confunde.

## 7. Advertencias

Hay dos tipos. Las automáticas solo salen si se cumple algo, y los umbrales se pueden cambiar al llamar a `report()`:

- **Correlación de más de 0,8 entre dos activos:** a partir de ahí la diversificación es muy poca.
- **Peso máximo de más del 40 %, o menos de 3 activos efectivos:** la cartera depende demasiado de pocos activos. Este umbral lo he puesto yo, como orientación.
- **Activos en otras divisas:** recordar que hay riesgo de tipo de cambio sin cubrir.
- **Drawdown peor que −20 %:** una caída del 20 % es lo que se suele considerar un mercado bajista.
- **Menos de 5 años de datos:** con pocos años la rentabilidad media es casi ruido; el error de la estimación es enorme.
- **Sharpe negativo:** cuando es negativo no sirve para comparar, porque más volatilidad hace que el número «mejore».
- **No se ha pasado tipo sin riesgo:** entonces el Sharpe y el Sortino se calculan con 0 y salen más altos de lo que deberían.
- **Índice de referencia mal elegido:** si usa otro tipo de precio que la cartera (por ejemplo, uno con dividendos y otro sin) o no cubre todo el periodo.

Las fijas salen siempre, porque son limitaciones del método:

- La simulación supone que los rendimientos siguen una distribución normal, y en la realidad las caídas fuertes son más frecuentes de lo que dice la normal. Por eso el VaR y el CVaR salen algo optimistas.
- Rebalancear a diario no tiene en cuenta los costes ni los impuestos. Nadie lo hace en la vida real.
- Las correlaciones suben en las crisis, justo cuando más se necesita la diversificación.
- La simulación usa datos pasados, y un pequeño error en la rentabilidad media cambia mucho el resultado a largo plazo.
- Que algo haya ido bien en el pasado no quiere decir que vaya a ir bien en el futuro.

## 8. Notas de cálculo

Al final, una lista corta de cómo se ha calculado todo, para que se pueda reproducir. Está explicado con más detalle en la sección «Decisiones».

## Gráficos

`plots_report()` saca estos gráficos:

- La evolución de la cartera, del índice y de cada activo, empezando todos en 100, para ver quién ha tirado de la cartera y si ha batido al índice.
- El drawdown a lo largo del tiempo, de la cartera y del índice.
- Un mapa de calor de las correlaciones, porque una tabla de números cuesta de leer y con colores se ve enseguida.
- Las trayectorias de la simulación con los percentiles.
- La distribución del valor final, marcando el valor inicial y el VaR.

## El índice de referencia

Comparar con un índice es opcional, y el usuario elige cuál. No he puesto uno por defecto porque no hay un índice que valga para todas las carteras. Si pusiera el S&P 500 y alguien analiza una cartera de acciones europeas, la comparación diría más sobre si EE. UU. lo ha hecho mejor que Europa que sobre la cartera.

Lo que propongo es construirlo con ETF por región, con los mismos pesos por región que la cartera. Si la cartera tiene un 60 % en acciones de EE. UU. y un 40 % en la zona euro, el índice sería un 60 % de `SPY` y un 40 % de `FEZ`. Un índice así es en sí mismo una cartera, así que se hace con la misma clase `Portfolio` y no hace falta nada nuevo.

Uso ETF que cotizan en EE. UU. en vez de los índices directamente por tres motivos: ya están en dólares, se pueden comprar de verdad (si no, no tiene mucho sentido compararse con ellos) y, con el precio ajustado, incluyen los dividendos igual que la cartera. Los índices de Yahoo Finance como `^GSPC` son solo de precio, sin dividendos, y eso le daría a la cartera unos dos puntos al año de ventaja que no son mérito suyo.

Un detalle: un ETF de, por ejemplo, España que cotiza en dólares ya incluye el efecto del tipo de cambio. Como la cartera tampoco cubre la divisa, la comparación es coherente.

Tiene un par de limitaciones. Los ETF cobran comisiones, así que rinden un poco menos que el índice puro, aunque eso es justo lo que habría ganado alguien que lo comprara. Y los ETF de otros países cotizan en horario de Nueva York, lo que cambia un poco los rendimientos de cada día, pero no la rentabilidad a largo plazo.

## Decisiones

**Rendimientos simples y no logarítmicos.** Con los simples, la rentabilidad de la cartera es directamente la media ponderada de la de sus activos, y son los que usa la simulación.

**Solo las fechas comunes, y los rendimientos después de alinear.** Si se calcularan los rendimientos antes de juntar las fechas, el día después de un festivo de un mercado mezclaría dos días de un activo con uno del otro. Tampoco relleno los festivos con el último precio, porque saldrían rendimientos de 0 que no son reales y bajarían la volatilidad.

**252 días al año.** Es la convención para los días de cotización. Las funciones permiten cambiarlo si hiciera falta.

**El CAGR con días naturales.** Aquí no uso 252. Al quedarse solo con los días comunes de varios mercados, salen menos de 252 días al año, y si se contara así el CAGR saldría inflado. Con las fechas se mide el tiempo que ha pasado de verdad.

**Media aritmética en el Sharpe y CAGR para el crecimiento.** Cada una sirve para una cosa, como explico arriba, y por eso enseño las dos.

**Convertir a dólares sin cubrir, con el tipo de cambio de cada día.** Esto lo decidimos en el grupo. No tenemos datos del coste de cubrir la divisa, y a cambio el report enseña cuánto ha aportado el tipo de cambio.

**La conversión la hace cada activo.** Cada `PriceSeries` guarda sus precios en su divisa y, si no está en dólares, su tipo de cambio, y sabe pasarse a dólares. Lo decidí así para que la fórmula esté en un solo sitio y no se pierda la divisa original, que hace falta para la exposición a divisa y para separar el efecto del tipo de cambio. Si algún día falta el tipo de cambio, se usa el del día anterior, porque si no fallaría con datos reales.

**El tipo sin riesgo, día a día y rellenando hacia delante.** Un tipo sigue vigente hasta que cambia, y la FRED no publica los festivos, así que esos días se usa el último. No interpolo porque me estaría inventando tipos que nunca existieron.

**El VaR y el CVaR respecto al valor inicial.** Es la forma más intuitiva («pierdes un 18 % de lo que pusiste») y es como ya lo hacía la simulación.

**Solo posiciones largas.** No se permiten pesos negativos, porque el toolkit está pensado para carteras de inversión normales.

**Validar mucho al crear los objetos.** Prefiero que el programa falle al principio con un mensaje claro a que calcule algo mal sin avisar.

## Lo que he dejado fuera

Algunas cosas las he dejado como posibles mejoras, porque no daba tiempo y lo que hay ya cubre lo importante:

- Rebalancear cada mes o cada trimestre en la simulación, en vez de a diario o nunca.
- Usar en la simulación una distribución con más probabilidad de caídas fuertes, o remuestrear los rendimientos históricos.
- Calcular la beta y el alfa frente al índice.

Y otras no tienen sentido en este caso:

- **Active Share:** compara la cartera con el índice posición por posición, y la cartera y el índice no tienen posiciones en común, así que saldría siempre cerca del 100 %.
- **Liquidez según el volumen negociado:** importa en carteras grandes con activos poco líquidos, y aquí son índices y ETF muy grandes.
- **Corregir la volatilidad por precios «suavizados»:** es para activos que no cotizan cada día de verdad, como los inmuebles.
- **Comisiones, código ISIN o avisos legales:** no es un fondo real.
