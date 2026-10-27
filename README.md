# MIAX Taller B1-T1 — `miax_toolkit`

## 1. Instalar las herramientas (una sola vez)

Necesitas **git** y **[uv](https://docs.astral.sh/uv/)**. Python 3.12 **no** hace falta instalarlo:
`uv` lo descarga solo (la versión está fijada en `.python-version`).

**macOS / Linux**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Cierra y vuelve a abrir la terminal, y comprueba con `uv --version`.

---

## 2. Preparar el proyecto

Los comandos son iguales en los tres sistemas salvo donde se indica.

```bash
git clone https://github.com/patriciamartinm03/MIAX_Taller_B1_T1.git
cd MIAX_Taller_B1_T1
uv sync
```

`uv sync` crea la carpeta `.venv` e instala exactamente las versiones de `uv.lock`, las mismas para
todo el equipo. No hace falta crear ni activar el entorno a mano.

**Credenciales:** copia la plantilla y rellena solo las claves que vayas a usar.

```bash
cp .env.example .env              # macOS / Linux
Copy-Item .env.example .env       # Windows (PowerShell)
```

> `.env` está en `.gitignore` y **nunca** se sube al repositorio. Si añades una variable nueva,
> añádela también, vacía, a `.env.example`.

**Hooks de pre-commit** (una vez por clon): revisan cada `git commit` (formato, ficheros grandes,
claves privadas, conflictos sin resolver).

```bash
uv tool install pre-commit
pre-commit install
```

**Comprobar que funciona:**

```bash
uv run python -c "import miax_toolkit; print('OK')"
```

---

## Día a día

```bash
git pull && uv sync              # traer cambios y actualizar el entorno
uv run python script.py          # ejecutar código con el entorno del proyecto
uv add <paquete>                 # añadir una dependencia
uv add --dev <paquete>           # dependencia solo de desarrollo (tests, lint...)
uv remove <paquete>              # quitar una dependencia
```

- `uv add` / `uv remove` modifican `pyproject.toml` y `uv.lock`: **commitea siempre los dos juntos**.
- No uses `pip install` en el proyecto: el resto del equipo no tendría ese paquete.
- Si prefieres activar el entorno (p. ej. para el editor):
  `source .venv/bin/activate` (macOS / Linux) o `.venv\Scripts\activate` (Windows).
  En VS Code / PyCharm basta con elegir `.venv` como intérprete.

---

## Estructura

```
src/miax_toolkit/
├── extraccion/      Descarga de datos de los proveedores (yfinance, MarketSignal)
├── modelos/         Clases del dominio (series de precios, carteras)
├── preprocesado/    Limpieza, alineación de fechas, retornos
├── simulacion/      Simulación de Monte Carlo
└── reporting/       Informes y gráficos
```
