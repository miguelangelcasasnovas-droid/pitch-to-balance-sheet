# Estado del proyecto

Actualizado: 25/09/2026

## Fase 0: cerrada

Cerrada el 25/09/2026 con el OK del usuario. El plan aprobado, con las decisiones incorporadas, está en [`plan.md`](plan.md).

## Fase 1: cerrada

Hecha el 25/09/2026 en Claude Code, en el Mac, y cerrada ese mismo día con el OK del usuario.

| Qué | Resultado |
| --- | --- |
| Python | El del sistema es 3.9.6 y no se ha tocado. `uv python install 3.11` instaló la 3.11.15 en `~/.local/share/uv/python` y dejó el enlace `~/.local/bin/python3.11`. `.venv` usa la 3.11.15 |
| Dependencias | Versiones de la sección 11 del plan fijadas en `pyproject.toml`, más `python-dotenv==1.2.3` y `PyYAML==6.0.3` (las últimas en PyPI a 25/09/2026). `uv.lock` fija también las transitivas: 80 paquetes |
| Cachés | uv en `.cache/uv`, ruff en `.cache/ruff`, pytest en `.cache/pytest` y pre-commit en `.cache/pre-commit`. Fuera del proyecto solo se escribió en la carpeta de uv |
| pre-commit | Hooks locales: gitleaks 8.30.1 en `.tools/`, con el sha256 comprobado, y el ruff de `.venv`. Se instalan con `scripts/install-hooks.sh`, que fija `PRE_COMMIT_HOME` dentro del hook. Si se lanza `pre-commit run` a mano, hay que anteponer `PRE_COMMIT_HOME=.cache/pre-commit` |
| CI | `.github/workflows/ci.yml`: `uv sync --locked`, `ruff check .` y `pytest` en cada push y PR, con las acciones fijadas por SHA. Los tests no usan la red: `tests/conftest.py` bloquea cualquier conexión |
| Git | `main` con el primer commit (`27dc502`). Rama `ci-check` con un test que falla a propósito (`e9f42c7`). La identidad del autor está solo en `.git/config` |

Comprobaciones hechas (la salida real está en el cierre de la fase):

1. `python --version` dentro de `.venv`: 3.11.15.
2. `ruff check .`: "All checks passed!". `pytest`: 4 passed.
3. Commit con una clave falsa `AKIA...`: gitleaks lo bloquea (regla `aws-access-token`, exit 1). El archivo de prueba se eliminó.
4. En `ci-check`, `pytest` da 1 failed y 4 passed, con exit 1. `main` sigue en verde.

## Decisiones

1. **Carpeta de trabajo:** `~/football-club-finance`.
2. **Universo por etapas:** primero los 8 cotizados y los 6 ingleses no cotizados (Arsenal, Chelsea, Liverpool, Manchester City, Tottenham y Newcastle). Real Madrid, Barça y Atlético entran cuando el pipeline funcione con los ingleses, con descarga manual. La valoración de Real Madrid y Barça va marcada como teórica.
3. **PDFs escaneados:** primero se mide. En la fase 2 se descarga un PDF de cuentas por club inglés y se mide cuánto texto saca pdfplumber. Si 3 o más de los 6 son imagen, se propone OCR solo para esos; si no, quedan como hueco.
4. **Dependencias:** se añaden `python-dotenv` y `PyYAML` al stack.
5. **La fase 1 se hace en Claude Code, en el Mac.**

Tomadas en la fase 1 y aceptadas con su OK:

6. **Hooks locales en lugar del hook oficial de gitleaks.** El oficial compila gitleaks con Go (329 MB de caché en la fase 0), y Go escribe fuera del proyecto: en `~/Library/Caches/go-build` y en su telemetría. Se aplica la mitigación de la sección 10 del plan, con el binario fijado en `.tools/`. ruff usa el de `.venv`, así su versión se fija en un solo sitio.
7. **gitleaks 8.30.1**, la última publicada (21/03/2026), en lugar de la 8.28.0 que se probó en la fase 0.
8. **`uv.lock` en git**, para que el CI instale exactamente lo mismo que el Mac.
9. **yfinance 1.7.0** (26/08/2026) en lugar de la 0.2.66 (17/09/2025), que daba avisos de funciones obsoletas con pandas 3. Decidido por el usuario el 25/09/2026, con la sección 11 del plan ya corregida.

## Pendientes

| Pendiente | Para cuándo | Detalle |
| --- | --- | --- |
| Push de `main` y `ci-check` | Antes de la fase 2 | Lo hace el usuario. `main` tiene que salir en verde y `ci-check` en rojo; después se borra `ci-check`, en local y en GitHub. El CI todavía no se ha ejecutado en GitHub: solo se validó el YAML |
| Clave de la API de Companies House | Antes de la fase 2 | Gratuita, de una aplicación real: la Document API no funciona en el sandbox. Va solo en `.env`. Si no está configurada, el trabajo se para y se pide |
| URLs de los PDFs de Juventus, Celtic y Lazio | Fase 2 | Sus webs no tienen los enlaces en el HTML. Se fijan a mano en `config/sources.yaml` |
| Fuentes de FC Porto | Fase 2 | fcporto.pt devolvió 403 a la descarga automática. Alternativa a comprobar: los registros de la CMVM |
| `data/raw/` en git | Fase 2 | Existe en local, pero git no la guarda hasta que haya `data/raw/manifest.csv` |
| Hooks fuera del Mac | Si se trabaja desde la VM Linux | El hook apunta al `.venv` del Mac y el binario de gitleaks es de macOS arm64. Desde la VM, `git commit` fallaría |

El resto de comprobaciones de la fase 2 está en la sección 7.1 y en los riesgos de `plan.md`.

## Siguiente paso

1. Push de `main` y `ci-check` por parte del usuario, para ver el CI en verde y en rojo. Después se borra `ci-check`.
2. Guardar la clave de Companies House en `.env`.
3. Fase 2: medir la capa de texto de los 6 PDFs ingleses (sección 7.1 del plan).
