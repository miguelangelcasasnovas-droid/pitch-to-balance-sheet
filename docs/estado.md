# Estado del proyecto

Actualizado: 26/09/2026

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
| Git | Repo en GitHub, [`miguelangelcasasnovas-droid/pitch-to-balance-sheet`](https://github.com/miguelangelcasasnovas-droid/pitch-to-balance-sheet), creado por el usuario. Solo queda la rama `main`: `ci-check` (`e9f42c7`, con el test que falla a propósito) se borró el 26/09/2026 en local y en origin. La identidad del autor está solo en `.git/config` |

Comprobaciones hechas (la salida real está en el cierre de la fase):

1. `python --version` dentro de `.venv`: 3.11.15.
2. `ruff check .`: "All checks passed!". `pytest`: 4 passed.
3. Commit con una clave falsa `AKIA...`: gitleaks lo bloquea (regla `aws-access-token`, exit 1). El archivo de prueba se eliminó.
4. En `ci-check`, `pytest` da 1 failed y 4 passed, con exit 1. `main` sigue en verde.
5. CI en GitHub Actions, tras el push del usuario: `main` en verde y `ci-check` en rojo, según comprobó el usuario el 26/09/2026.

## Fase 2a: medición de la capa de texto (hecha, a falta del OK)

Cuentas 2024/25 de los 6 clubes ingleses, descargadas con la API de Companies House (sección 7.1 del plan). Hecha el 26/09/2026. No se ha extraído ninguna cifra.

**Criterio de clasificación, fijado el 26/09/2026 antes de medir:**

- **Caracteres de una página:** caracteres no blancos del texto que devuelve `pdfplumber` (`page.extract_text()`).
- **Página con texto:** 200 caracteres o más. Una página de cuentas con capa de texto tiene cientos o miles de caracteres. Por debajo de 200 solo caben un encabezado, un número de página o un sello.
- **Clasificación del PDF,** según la proporción de páginas con texto:
  - **texto:** 80% o más;
  - **imagen:** menos del 20%;
  - **mixto:** entre el 20% y el 80%.
- **Palabras clave,** sin distinguir mayúsculas: "Turnover" o "Revenue", y "Staff costs" o "Wages". Se informan aparte y no cambian la clasificación. Si un PDF de texto no las contiene, se marca para revisarlo.
- **Regla de la decisión 3:** solo cuentan los PDFs de imagen. Con 3 o más de 6, se propone OCR para esos; con menos, quedan como hueco.

**Descarga** (`python -m pitch_to_balance_sheet download`): 6 de 6, sin errores y con una sola presentación de cuentas por club. Las páginas y la fecha de depósito coinciden con la sección 7.1 del plan. Los 6 documentos están solo en PDF, sin XHTML, y Companies House los marca como presentados en papel (`paper_filed: true`). URL, fecha y sha256 están en `data/raw/manifest.csv`, y los datos de cada presentación en `data/processed/companies_house_filings_2024_25.csv`.

**Medición** (`python -m pitch_to_balance_sheet text-layer`, sale con exit 1 por los dos ilegibles):

| Club | Formato | Páginas | Págs. con texto | Caracteres por página | Palabras clave | Clasificación |
| --- | --- | --- | --- | --- | --- | --- |
| Arsenal | PDF | 45 | 0 | 0 en todas | ninguna | imagen |
| Chelsea | PDF | 46 | 0 | 0 en todas | ninguna | imagen |
| Liverpool | PDF | 38 según la API | — | — | — | ilegible con pdfplumber |
| Manchester City | PDF | 39 | 0 | 0 en todas | ninguna | imagen |
| Tottenham Hotspur | PDF | 65 según la API | — | — | — | ilegible con pdfplumber |
| Newcastle United | PDF | 47 | 0 | 0 en todas | ninguna | imagen |

El detalle por página está en `data/processed/text_layer_2024_25.csv`.

- **Liverpool y Tottenham:** pdfplumber falla con `PdfminerException(PSEOF('Unexpected EOF'))`. El `startxref` del PDF no apunta a la tabla xref: en Liverpool apunta al byte 22.887 y la tabla está en el 1.743.426; en Tottenham, al 39.118 y la tabla está en el 2.641.632. Arsenal tiene el mismo defecto (27.097 frente a 2.026.252), pero ahí pdfminer lo recupera. Como diagnóstico aparte del criterio, pypdfium2 abre los dos: 38 y 65 páginas, todas con imagen y 0 caracteres.
- **Regla de la decisión 3:** 4 de 6 son imagen, así que se propone OCR.

**Propuesta de OCR, a falta del OK del usuario:**

1. **Cómo:** renderizar cada página con pypdfium2, que ya viene con pdfplumber y abre también Liverpool y Tottenham, y pasarla por OCR. El texto de cada página se guarda con el sha256 del PDF de origen, para que la extracción y los tests no dependan de volver a hacer OCR.
2. **Motor recomendado:** Apple Vision, a través de `ocrmac` 1.0.1 (licencia MIT, publicado el 08/01/2026) sobre `pyobjc-framework-Vision` 12.2.2. Se instala con uv en `.venv`, sin descargar modelos y sin nada global. En contra: solo funciona en macOS, así que el OCR se hace en el Mac y el CI trabaja con el texto ya guardado.
3. **Alternativa multiplataforma:** `rapidocr` 3.9.2 (Apache-2.0, basado en ONNX). Pesa más (opencv, onnxruntime) y falta comprobar dónde guarda sus modelos.
4. **Descartadas:** Tesseract, porque su binario se instala con brew, es decir, de forma global; y easyocr, porque depende de PyTorch.
5. **Alcance:** los 6 PDFs de 2024/25. A los 4 de imagen se suman Liverpool y Tottenham, que pdfium ve como imagen. Las temporadas anteriores están sin medir.
6. **Controles:** un piloto con una sola cuenta de resultados antes de ampliar. Después, cada cifra que salga del OCR se revisa contra la imagen de la página, se marca como obtenida por OCR y tiene que cuadrar con sus subtotales (sección 5 del plan).
7. **Alternativa sin OCR, sin comprobar:** usar el informe anual que algunos clubes publican en su web, si es un PDF digital. Sería otra fuente, con su propio robots.txt.

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
| OK a la propuesta de OCR | Antes de extraer cifras de los ingleses | Motor (Apple Vision o rapidocr), alcance (los 6 o solo los 4 de imagen) y piloto. Sin OK no se instala nada |
| URLs de los PDFs de Juventus, Celtic y Lazio | Fase 2 | Sus webs no tienen los enlaces en el HTML. Se fijan a mano en `config/sources.yaml` |
| Fuentes de FC Porto | Fase 2 | fcporto.pt devolvió 403 a la descarga automática. Alternativa a comprobar: los registros de la CMVM |
| Hooks fuera del Mac | Si se trabaja desde la VM Linux | El hook apunta al `.venv` del Mac y el binario de gitleaks es de macOS arm64. Desde la VM, `git commit` fallaría |

El resto de comprobaciones de la fase 2 está en la sección 7.1 y en los riesgos de `plan.md`.

## Siguiente paso

1. El usuario decide sobre la propuesta de OCR: motor y alcance.
2. Con el OK, piloto de OCR sobre una cuenta de resultados, y parar para revisarlo antes de extraer cifras.
