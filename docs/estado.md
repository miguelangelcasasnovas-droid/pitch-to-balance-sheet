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

## Fase 2a: medición de la capa de texto (cerrada)

Cuentas 2024/25 de los 6 clubes ingleses, descargadas con la API de Companies House (sección 7.1 del plan). Hecha el 26/09/2026 y cerrada ese mismo día con el OK del usuario al OCR.

**Criterio de clasificación, fijado el 26/09/2026 antes de medir:**

- **Caracteres de una página:** caracteres no blancos del texto que devuelve `pdfplumber` (`page.extract_text()`).
- **Página con texto:** 200 caracteres o más. Una página de cuentas con capa de texto tiene cientos o miles de caracteres. Por debajo de 200 solo caben un encabezado, un número de página o un sello.
- **Clasificación del PDF,** según la proporción de páginas con texto:
  - **texto:** 80% o más;
  - **imagen:** menos del 20%;
  - **mixto:** entre el 20% y el 80%.
- **Palabras clave,** sin distinguir mayúsculas: "Turnover" o "Revenue", y "Staff costs" o "Wages". Se informan aparte y no cambian la clasificación. Si un PDF de texto no las contiene, se marca para revisarlo.
- **Regla de la decisión 3:** solo cuentan los PDFs de imagen. Con 3 o más de 6, se propone OCR para esos; con menos, quedan como hueco.
- **Añadido el 26/09/2026 por decisión del usuario, después de la primera medición:** si pdfplumber no puede abrir un PDF, se abre con pypdfium2, y los caracteres de una página son los no blancos de su texto (`get_text_range()`). Así se miden Liverpool y Tottenham de Companies House. El OCR también renderiza las páginas con pypdfium2.

**Descarga** (`python -m pitch_to_balance_sheet download`): 6 de 6, sin errores y con una sola presentación de cuentas por club. Las páginas y la fecha de depósito coinciden con la sección 7.1 del plan. Los 6 documentos están solo en PDF, sin XHTML, y Companies House los marca como presentados en papel (`paper_filed: true`). URL, fecha y sha256 están en `data/raw/manifest.csv`, y los datos de cada presentación en `data/processed/companies_house_filings_2024_25.csv`.

**Medición** (`python -m pitch_to_balance_sheet text-layer`). La primera pasada salió con exit 1 porque pdfplumber no pudo abrir Liverpool ni Tottenham. Con la regla de pypdfium2 sale con exit 0:

| Club | Formato | Motor | Páginas | Págs. con texto | Caracteres por página | Palabras clave | Clasificación |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Arsenal | PDF | pdfplumber | 45 | 0 | 0 en todas | ninguna | imagen |
| Chelsea | PDF | pdfplumber | 46 | 0 | 0 en todas | ninguna | imagen |
| Liverpool | PDF | pypdfium2 | 38 | 0 | 0 en todas | ninguna | imagen |
| Manchester City | PDF | pdfplumber | 39 | 0 | 0 en todas | ninguna | imagen |
| Tottenham Hotspur | PDF | pypdfium2 | 65 | 0 | 0 en todas | ninguna | imagen |
| Newcastle United | PDF | pdfplumber | 47 | 0 | 0 en todas | ninguna | imagen |

El detalle por página está en `data/processed/text_layer_2024_25.csv`, que ahora incluye también el PDF manual de Man City (fase 2b).

- **Liverpool y Tottenham:** pdfplumber falla con `PdfminerException(PSEOF('Unexpected EOF'))`. El `startxref` del PDF no apunta a la tabla xref: en Liverpool apunta al byte 22.887 y la tabla está en el 1.743.426; en Tottenham, al 39.118 y la tabla está en el 2.641.632. Arsenal tiene el mismo defecto (27.097 frente a 2.026.252), pero ahí pdfminer lo recupera. pypdfium2 abre los dos.
- **Regla de la decisión 3:** en la primera medición salieron 4 de 6 de imagen, así que se propuso OCR. Con la regla de pypdfium2 son 6 de 6.

**Propuesta de OCR, aceptada el 26/09/2026** con Apple Vision (ocrmac 1.0.1). rapidocr queda de reserva, sin instalar:

1. **Cómo:** renderizar cada página con pypdfium2, que ya viene con pdfplumber y abre también Liverpool y Tottenham, y pasarla por OCR. El texto de cada página se guarda con el sha256 del PDF de origen, para que la extracción y los tests no dependan de volver a hacer OCR.
2. **Motor recomendado:** Apple Vision, a través de `ocrmac` 1.0.1 (licencia MIT, publicado el 08/01/2026) sobre `pyobjc-framework-Vision` 12.2.2. Se instala con uv en `.venv`, sin descargar modelos y sin nada global. En contra: solo funciona en macOS, así que el OCR se hace en el Mac y el CI trabaja con el texto ya guardado.
3. **Alternativa multiplataforma:** `rapidocr` 3.9.2 (Apache-2.0, basado en ONNX). Pesa más (opencv, onnxruntime) y falta comprobar dónde guarda sus modelos.
4. **Descartadas:** Tesseract, porque su binario se instala con brew, es decir, de forma global; y easyocr, porque depende de PyTorch.
5. **Alcance:** los 6 PDFs de 2024/25. A los 4 de imagen se suman Liverpool y Tottenham, que pdfium ve como imagen. Las temporadas anteriores están sin medir.
6. **Controles:** un piloto con una sola cuenta de resultados antes de ampliar. Después, cada cifra que salga del OCR se revisa contra la imagen de la página, se marca como obtenida por OCR y tiene que cuadrar con sus subtotales (sección 5 del plan).
7. **Alternativa sin OCR, comprobada el 26/09/2026:** solo sirve para Manchester City (ver fase 2b). Liverpool, Tottenham y Newcastle publican en su web un PDF que tampoco tiene texto, y Arsenal y Chelsea no publican ninguno.

## Fuentes alternativas: investigación del 26/09/2026

Hecha en Cowork. El detalle, con URLs, páginas, robots.txt y sha256, está en [`fuentes-pendientes.md`](fuentes-pendientes.md). Las decisiones que salieron de ella están en la fase 2b.

| Club | PDF 2024/25 en su web | Texto en la cuenta de resultados | Misma entidad y cierre que en el plan | Descarga automática |
| --- | --- | --- | --- | --- |
| Arsenal | No encontrado | — | — | — |
| Chelsea | No encontrado | — | — | — |
| Liverpool | Sí | No: texto como trazos vectoriales, sin fuentes. Es un render limpio, no un escaneo | Sí | Permitida |
| Manchester City | Sí | Sí, comprobado con WebFetch | Sí | robots.txt la permite, pero Cloudflare devuelve 403 a curl: descarga manual |
| Tottenham Hotspur | Sí | No: escaneo a 400 ppp | Sí | Permitida |
| Newcastle United | Sí | No: imagen, con 5 de 47 páginas con algo de texto | Sí | Permitida |
| Juventus | Sí, en italiano y en inglés | Sí (99% de páginas con texto) | Grupo, 30/06/2025 | Permitida |
| Celtic | Sí | Sí (91%) | Grupo, 30/06/2025 | Permitida |
| Lazio | Sí, "copia di cortesia" | No: escaneo de 208 páginas. El ESEF oficial está en 1info y no se ha localizado | Separado y consolidado, 30/06/2025 | Permitida, con `Crawl-delay: 10` |
| FC Porto | Solo el comunicado de resultados, de 8 páginas | Sí | SAD, consolidado. Confirma el cierre a 30/06 | Permitida. La CMVM está en mantenimiento hasta el 27/09/2026 a las 18:00 |

**Qué cambia para la propuesta de OCR:**

- Si se usa el PDF del club, Man City no necesita OCR. Hay que descargarlo a mano a `data/raw/manual/`.
- Liverpool sigue necesitando OCR, pero el PDF de su web es un render limpio y es mejor base que el escaneo de Companies House.
- Lazio también es imagen. Antes de pasar sus 208 páginas por OCR, conviene buscar el ESEF.

## Fase 2b: fuentes fijadas y piloto de OCR con Chelsea (hecha, a falta del OK)

Hecha el 26/09/2026. Solo se han extraído las tres cifras del piloto.

**Fuentes 2024/25, decididas por el usuario el 26/09/2026** y fijadas en `config/sources.yaml`:

| Club | Fuente principal | Control |
| --- | --- | --- |
| Arsenal | Companies House. `data/raw/manual/arsenal_2024-25.pdf` no existe; si aparece, pasa a ser la fuente principal | — |
| Chelsea, Tottenham, Newcastle | Companies House | — |
| Liverpool | PDF de su web, con descarga automática permitida. Todavía sin descargar | Companies House |
| Manchester City | PDF manual, `data/raw/manual/mancity_2024-25.pdf` | Companies House |
| Juventus | PDF en italiano, la versión que prevalece | PDF en inglés |
| Celtic | PDF de su web. Todavía sin descargar | — |
| Lazio y FC Porto | Pendientes, sin fuente fijada | — |

**PDF manual de Man City:**

- Registrado con `python -m pitch_to_balance_sheet register-manual`: 7.149.096 bytes, sha256 `844c584cbc7ef36bba732546a01d79da90e2b64ede180264a019e928f92a3875`. Como fecha se usa la de modificación del archivo, 26/09/2026 a las 12:59:21 UTC. macOS no guardó la URL de origen, pero la marca de cuarentena de Chrome da la misma hora.
- Es la variante enlazada, no la otra que hay en el servidor: en la pág. 24, la fila "As at 30 June 2023" cuadra (1,339,575 + 45,008 − 594,170 = 790,413) y la reserva de cobertura no repite 45,008.
- El pipeline comprueba su sha256 antes de usarlo. Si falta o ha cambiado, sale con error y dice de qué URL descargarlo.
- Medido con el criterio: 54 páginas, 44 con texto (81%): **texto**. "Revenue" aparece en las págs. 7, 8, 18 y otras, y "Wages" en la 37; "Staff costs" no aparece. La página de la cuenta de resultados está sin localizar.

**Piloto de OCR con Chelsea** (escaneo de Companies House):

1. **Páginas**, localizadas mirando el render y fijadas en `config/sources.yaml`: la 17 (Group profit and loss account, pág. 14 impresa) y la 34 (nota 8, Employees, pág. 31 impresa). Solo esas dos pasan por OCR (`python -m pitch_to_balance_sheet ocr --club chelsea`), a 300 ppp. El resultado está en `data/interim/ocr/0244bb79215351ca2b2bf40d2ab5939627d59566ace59d0ca4a199645e846dc1/`, fuera de git.
2. **Cifras** (`python -m pitch_to_balance_sheet extract --club chelsea`), en miles de libras:

   | Concepto | Cifra | Página | Fila del PDF | Columna |
   | --- | --- | --- | --- | --- |
   | Ingresos totales | 490,857 | 17 | Turnover | Total 30 June 2025 |
   | Gastos de personal | 359,265 | 34 | Total sin rótulo de "Their aggregate remuneration comprised" | 2025 |
   | Resultado neto | (262,647) | 17 | (Loss)/profit for the financial year | Total 30 June 2025 |

   Las tres las leyó el OCR de la página tal cual, sin ninguna corrección y con confianza 1,0. El resultado neto coincide con el del informe estratégico (pág. 4): "The loss for the year, after taxation, was £262.6m".
3. **Cuadres:** 35 de 35, todos con diferencia 0 (tolerancia ±1).
   - Pág. 17, en las cuatro columnas: margen bruto, pérdida de explotación, resultado antes de impuestos y resultado del ejercicio.
   - Pág. 17, fila a fila: operaciones + jugadores = total 2025.
   - Pág. 34: la suma de la remuneración agregada (2025 y 2024) y la de los consejeros (nota 9).
   - El detalle está en `data/interim/piloto_chelsea_2024_25_cuadres.csv`.
4. **Recortes** de cada línea extraída, en `data/interim/recortes/`:
   - `chelsea_2024_25_revenue_total_p17.png`
   - `chelsea_2024_25_staff_costs_p34.png`
   - `chelsea_2024_25_net_result_p17.png`
5. **Errores de OCR vistos:**
   - **£ leído como €:** 3 de 4 cabeceras "£'000" en la pág. 17 y 6 de 8 en la 34. En el fixture sintético, también como "f'000". Por eso la moneda no se toma del OCR: la fija el extractor de cada club, y se exige que al menos una cabecera de la página diga £.
   - **Guiones perdidos:** 11 guiones de la pág. 17 no salieron en el OCR de la página. Se detectan mirando la imagen de la celda.
   - **Una cifra perdida:** el (2,985) de "(Loss)/profit on disposal of fixed assets", en la columna de operaciones. Se recuperó con una segunda pasada solo sobre la celda, y la fila cuadra.
   - **Una nota perdida:** el "11" de "Interest payable".
   - **Restos del escaneo leídos como texto:** "•Wages and salaries" y texto corrido con errores ("ENil", "£190. 1m", primeras letras cortadas).
   - **Sin errores de coma ni de paréntesis** en las cifras de estas dos páginas: todas las comas de miles y todos los paréntesis de negativos se leyeron bien. `parse_amount` corrige y anota el punto en lugar de la coma, el paréntesis sin pareja y las letras por dígitos, pero aquí no hizo falta.
6. **Rareza del propio documento:** en la pág. 17, la fila que va antes del impuesto se llama "(Loss)/profit after taxation". El extractor la trata como resultado antes de impuestos, y así cuadra.
7. **Test:** `tests/fixtures/pagina_ocr.pdf` es una página inventada, solo imagen, con una cuenta de resultados que cuadra, un guion y paréntesis. `test_imagen_ocr_cifra` cubre imagen → OCR → cifra → cuadre. Usa Apple Vision, así que solo corre en macOS; en el CI, que es Linux, se salta. El resto de tests de OCR no hacen OCR y corren en todas partes.

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

Tomadas por el usuario el 26/09/2026:

10. **Fuentes 2024/25** como en la tabla de la fase 2b.
11. **OCR con Apple Vision** (`ocrmac==1.0.1`, solo en macOS, instalado con uv en `.venv`). rapidocr queda de reserva, sin instalar.
12. **pypdfium2 para lo que pdfplumber no puede abrir**, anotado en el criterio de la fase 2a.

Tomadas en la fase 2b, a falta del OK del usuario:

13. **Celdas que el OCR deja vacías:** se mira la imagen de la celda. Sin tinta, queda vacía; un trazo corto es un guion, es decir, cero; cualquier otra cosa pasa a una segunda pasada de OCR solo sobre la celda, y si tampoco se lee, error. Cada cifra corregida así queda anotada.
14. **La moneda no sale del OCR,** que confunde £ con € y con f. La fija el extractor de cada club.
15. **Fecha de descarga de un PDF manual:** la de modificación del archivo.
16. **`pypdfium2==5.13.0` y `pillow==12.3.0` fijadas en `pyproject.toml`,** con la versión que ya tenía `uv.lock`, porque el código las importa directamente.

## Pendientes

| Pendiente | Para cuándo | Detalle |
| --- | --- | --- |
| OK al piloto de Chelsea | Antes de ampliar el OCR | Cifras, cuadres, recortes y el tratamiento de las celdas vacías (decisión 13) |
| Descargar los PDFs de la web de Liverpool, Juventus y Celtic | Fase 2 | Las URLs están en `config/sources.yaml`. `text-layer` los marca como "sin medir" hasta que se descarguen |
| Página de la cuenta de resultados de Man City | Antes de extraer sus cifras | El PDF manual tiene texto, pero la página no se ha localizado |
| PDF manual de Arsenal | Opcional | Si el usuario lo deja en `data/raw/manual/arsenal_2024-25.pdf`, pasa a ser la fuente principal. Hay que añadirlo a `sources.yaml` con su URL y registrarlo |
| ESEF de Lazio 2024/25 | Antes de decidir OCR para Lazio | El club dice que está en el portal 1info, pero la dirección que da devuelve 404 |
| Informe anual 2024/25 completo de FC Porto | Fase 2 | La CMVM vuelve después del 27/09/2026 a las 18:00. Mientras tanto solo hay el comunicado de resultados, que no trae notas. fcporto.pt respondió 200 el 26/09/2026, pero no tiene enlaces en el HTML |
| Hooks y OCR fuera del Mac | Si se trabaja desde la VM Linux | El hook apunta al `.venv` del Mac y el binario de gitleaks es de macOS arm64: desde la VM, `git commit` fallaría. El OCR tampoco funciona fuera de macOS |

El resto de comprobaciones de la fase 2 está en la sección 7.1 y en los riesgos de `plan.md`.

## Siguiente paso

1. El usuario revisa el piloto de Chelsea: las tres cifras, los cuadres, los recortes y los errores de OCR.
2. Con el OK: descargar los PDFs de la web (Liverpool, Juventus y Celtic) y extender el OCR, página a página, a Arsenal, Liverpool, Tottenham y Newcastle.
3. Después del 27/09/2026 a las 18:00, volver a la CMVM para buscar el informe anual 2024/25 de FC Porto.
