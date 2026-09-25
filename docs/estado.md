# Estado del proyecto

Actualizado: 25/09/2026

## Fase 0: cerrada

Cerrada el 25/09/2026 con el OK del usuario. El plan aprobado, con las decisiones incorporadas, está en [`plan.md`](plan.md).

## Decisiones

1. **Carpeta de trabajo:** `~/football-club-finance`.
2. **Universo por etapas:** primero los 8 cotizados y los 6 ingleses no cotizados (Arsenal, Chelsea, Liverpool, Manchester City, Tottenham y Newcastle). Real Madrid, Barça y Atlético entran cuando el pipeline funcione con los ingleses, con descarga manual. La valoración de Real Madrid y Barça va marcada como teórica.
3. **PDFs escaneados:** primero se mide. En la fase 2 se descarga un PDF de cuentas por club inglés y se mide cuánto texto saca pdfplumber. Si 3 o más de los 6 son imagen, se propone OCR solo para esos; si no, quedan como hueco.
4. **Dependencias:** se añaden `python-dotenv` y `PyYAML` al stack.
5. **La fase 1 se hace en Claude Code, en el Mac.**

## Pendientes

| Pendiente | Para cuándo | Detalle |
| --- | --- | --- |
| Clave de la API de Companies House | Antes de la fase 2 | Gratuita, de una aplicación real: la Document API no funciona en el sandbox. Va solo en `.env`. Si no está configurada, el trabajo se para y se pide |
| URLs de los PDFs de Juventus, Celtic y Lazio | Fase 2 | Sus webs no tienen los enlaces en el HTML. Se fijan a mano en `config/sources.yaml` |
| Fuentes de FC Porto | Fase 2 | fcporto.pt devolvió 403 a la descarga automática. Alternativa a comprobar: los registros de la CMVM |

El resto de comprobaciones de la fase 2 está en la sección 7.1 y en los riesgos de `plan.md`.

## Siguiente paso: fase 1 en Claude Code, en el Mac

1. Comprobar `python3 --version`: hace falta 3.11 o superior.
2. Crear `src/`, `tests/`, `data/raw`, `data/processed`, `app/` y `config/`.
3. `pyproject.toml` con versiones fijadas (incluye `python-dotenv` y `PyYAML`), `.env.example` sin valores y `.gitignore`.
4. `.pre-commit-config.yaml` con gitleaks y ruff, con la caché de pre-commit dentro del proyecto.
5. `.github/workflows/ci.yml` con ruff y pytest en cada push y PR.
6. Un test que falle a propósito para ver el CI en rojo cuando el usuario haga push. Después se quita.
7. Un commit de prueba con una clave falsa tipo `AKIA...` que gitleaks tiene que bloquear.
8. Pegar la salida real de `ruff check .` y `pytest`, y parar hasta el OK.
