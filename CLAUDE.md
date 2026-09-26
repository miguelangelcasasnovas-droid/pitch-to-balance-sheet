# Pitch to Balance Sheet

Cuentas de clubes de fútbol europeos en una sola tabla, con métricas de sostenibilidad y valoración por múltiplos. Hay dos fuentes de verdad:

- [`docs/plan.md`](docs/plan.md): el plan aprobado. Las reglas de trabajo están en la sección 2.
- [`docs/estado.md`](docs/estado.md): fase en curso, decisiones y pendientes.

Si este archivo contradice a esos documentos, mandan ellos.

## Al empezar y al terminar

- Leer `docs/estado.md` antes de hacer nada.
- Al terminar, actualizarlo: qué se cerró, qué queda pendiente y cuál es el siguiente paso.

## Reglas duras

1. Ninguna cifra inventada ni estimada. Cada dato lleva su fuente: archivo + página, o URL + fecha de descarga. Si un dato no se publica, queda vacío, marcado como hueco y con su motivo.
2. Un paso que no puede ejecutarse (descarga fallida, PDF ilegible, clave que falta) sale con error y dice por qué. Nunca pasa en silencio.
3. Las claves van solo en `.env`, que está en `.gitignore`. Nunca en el código, en los tests ni en los commits.
4. Nada de instalaciones globales ni `sudo`. El entorno va en `.venv/`, las cachés en `.cache/` y las herramientas en `.tools/`.
5. No hacer `push` ni crear el repo en GitHub: eso lo hace el usuario.
6. Parar al final de cada fase y esperar el OK del usuario antes de empezar la siguiente.

## Contrato de salida

Al cerrar una fase o una tarea, entregar:

1. Archivos creados o modificados.
2. Supuestos tomados.
3. Comandos ejecutados con su salida real.
4. Huecos: lo que falta o no se pudo hacer, y por qué.
5. Siguiente paso.

## Comandos

```sh
uv sync --locked              # entorno en .venv con las versiones fijadas
uv run ruff check .
uv run pytest
scripts/install-hooks.sh      # gitleaks en .tools/ y hook de pre-commit
uv run python -m pitch_to_balance_sheet download          # cuentas de Companies House
uv run python -m pitch_to_balance_sheet download-web      # PDFs de la web de los clubes
uv run python -m pitch_to_balance_sheet register-manual   # PDFs manuales al manifiesto
uv run python -m pitch_to_balance_sheet text-layer        # capa de texto de los PDFs locales
uv run python -m pitch_to_balance_sheet ocr --club X      # rehace el OCR de un club (macOS)
uv run python -m pitch_to_balance_sheet extract [--club X]  # cifras, cuadres y recortes
```
