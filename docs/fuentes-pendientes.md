# Fuentes pendientes (fase 2)

Consultado el 26/09/2026, entre las 12:00 y las 12:25 UTC. No se ha extraído ninguna cifra ni se ha tocado `config/`, `src/` ni `data/`: los PDFs se descargaron a una carpeta temporal fuera del repo, solo para medirlos.

**Añadido el 27/09/2026:** la sección 6, con el ESEF de Lazio en 1info y el informe anual de FC Porto en la CMVM. Tampoco se ha extraído ninguna cifra ni se ha tocado `config/`, `src/` ni `data/`.

**Cómo se midió la capa de texto.** Con el criterio fijado en [`estado.md`](estado.md): caracteres no blancos por página con `pdfplumber`, página con texto a partir de 200, y PDF de texto (80% o más de páginas con texto), imagen (menos del 20%) o mixto. Se usó pdfplumber 0.11.9, no la 0.11.10 fijada en el proyecto. Para distinguir un escaneo de un PDF sin fuentes se usaron `pdffonts` y `pdfimages` (poppler). La cuenta de resultados de cada PDF se localizó mirando la página renderizada, y su número es la página del PDF empezando en 1.

**robots.txt.** Se leyó el del dominio de la página y el del dominio que sirve el PDF, que casi nunca es el mismo. Si un robots.txt responde 4xx, no hay restricciones; si responde 5xx, hay que suponer que todo está prohibido ([RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.txt), secciones 2.3.1.3 y 2.3.1.4).

## Resumen

- **Ingleses:** 4 de 6 publican las cuentas 2024/25 en su web. Solo la de Manchester City tiene capa de texto. Liverpool, Tottenham y Newcastle suben un PDF sin texto, igual que el de Companies House. Arsenal y Chelsea no enlazan ningún PDF.
- **Juventus y Celtic:** PDF con texto y URL fijada. **Lazio:** el PDF que publica es un escaneo; la versión oficial es la ESEF, localizada el 27/09/2026 en 1info y con texto (sección 6.1).
- **Porto:** el 26/09/2026 la CMVM estaba en mantenimiento. El 27/09/2026 ya respondía y el informe anual 2024/25 está allí, con texto y con cuentas consolidadas e individuales (sección 6.2). El comunicado de resultados queda como fuente parcial.

## 1. Clubes ingleses: cuentas 2024/25 en la web del club

| Club | PDF 2024/25 | Página donde está el enlace | ¿Texto seleccionable en la cuenta de resultados? | ¿Misma entidad y cierre que en Companies House? | robots.txt |
| --- | --- | --- | --- | --- | --- |
| Arsenal | No encontrado | La noticia [Financial results for 2024/25](https://www.arsenal.com/news/financial-results-for-202425-axV959A5jyCF) resume las cuentas y no enlaza ningún PDF. [Financial Results](https://www.arsenal.com/the-club/corporate-info/arsenal-holdings-financial-results) redirige a una página que dice "Latest financial results" sin ningún enlace | — | — | www.arsenal.com: `Allow: /`; solo bloquea perfiles, callbacks y búsquedas |
| Chelsea | No encontrado | La noticia [Financial results for 2024/25](https://www.chelseafc.com/en/news/article/financial-results-for-2024-25) solo resume y remite a Companies House. Las demás páginas de resultados del sitemap son de años anteriores | — | — | www.chelseafc.com: `Allow: /` |
| Liverpool | [2025_Accounts_0b9cd179….pdf](https://backend.liverpoolfc.com/sites/default/files/2026-03/2025_Accounts_0b9cd179492e0f16a4de8edfc027212f.pdf) | [Financial Information](https://www.liverpoolfc.com/corporate/financial-information): "the annual report and consolidated financial statements for the period ended 31 May 2025 – please download to view" | **No.** 38 páginas y ninguna con texto: imagen. No es un escaneo: el texto está dibujado como trazos vectoriales y el PDF no tiene fuentes. Cuenta de resultados en la pág. 14 (12 impresa), con 0 caracteres | **Sí.** The Liverpool Football Club and Athletic Grounds Limited, nº 00035668, cierre 31/05/2025. Tiene 38 páginas, como el de Companies House, pero es otro archivo | www.liverpoolfc.com: `Allow: /`. backend.liverpoolfc.com: robots.txt estándar de Drupal, que no bloquea `/sites/default/files/` |
| Manchester City | [mcfc_financial_report_2025_.pdf](https://www.mancity.com/annualreport2025/wp-content/uploads/2025/11/mcfc_financial_report_2025_.pdf) | [Annual Report 2024-25](https://www.mancity.com/annualreport2025/), apartado "Downloads", enlace "Financial report" | **Sí,** comprobado con WebFetch, que extrae literalmente la línea "Revenue 4 694,094 – 694,094 715,019". Sin medir con pdfplumber, porque no se pudo descargar (ver nota 1) | **Sí.** Manchester City Football Club Limited, nº 00040946, ejercicio cerrado el 30/06/2025 | www.mancity.com: no bloquea `/annualreport2025/`. Pero Cloudflare devuelve 403 a curl, también con un User-Agent propio del proyecto |
| Tottenham Hotspur | [AR-2025.pdf](https://resources.thfc.pulselive.com/thfc/document/2026/04/02/7909b5bc-9c0d-439a-bca9-c2f27b9c9f4d/AR-2025.pdf) | [Annual Reports](https://www.tottenhamhotspur.com/the-club/investor-relations/annual-reports/), enlace "Annual Report 2025" | **No.** 65 páginas y ninguna con texto: imagen, escaneada en blanco y negro a 400 ppp (JBIG2). Cuenta de resultados consolidada en la pág. 23, con 0 caracteres | **Sí.** Tottenham Hotspur Limited, nº 1706358, cierre 30/06/2025. Tiene 65 páginas, como el de Companies House, pero es otro archivo | www.tottenhamhotspur.com: `Allow: /` para todos. resources.thfc.pulselive.com no tiene robots.txt (403 de S3), así que no hay restricciones |
| Newcastle United | [Newcastle_United_Limited_-_2025_-_Signed_Statutory_Financial_Statements.pdf](https://assets.ctfassets.net/9ec6988xevcz/SlmVOQkiENmR88JGWsY3D/2a431370561c3f0006c920edfa512bc9/Newcastle_United_Limited_-_2025_-_Signed_Statutory_Financial_Statements.pdf) | Enlace "here" al final de la noticia [Newcastle United announces record income…](https://www.newcastleunited.com/en/news/newcastle-united-announces-record-income), publicada el 31/03/2026 | **No.** 47 páginas y 5 con texto (11%): imagen. Esas 5 son páginas firmadas y su texto tiene errores de OCR ("TI1e", "accouut"). Cuenta de resultados consolidada en la pág. 19, con 0 caracteres | **Sí.** Newcastle United Limited, nº 02529667, cierre 30/06/2025. Tiene 47 páginas, como el de Companies House | www.newcastleunited.com: `Allow: /`. assets.ctfassets.net: robots.txt da 404, así que no hay restricciones |

**Notas:**

1. **Manchester City:** WebFetch sí abre el PDF. En el mismo directorio hay otro archivo sin el último guion bajo (`mcfc_financial_report_2025.pdf`) que no está enlazado desde la página. Su texto coincide en todo lo comparado salvo una celda del estado de cambios en el patrimonio: la fila a 30/06/2023 repite 45,008 en la reserva de cobertura y no suma. Hay que usar el enlazado. El índice sitúa la cuenta de resultados en la pág. 19 impresa. La página del PDF se medirá cuando el archivo esté descargado a mano. En la misma página hay otro PDF, `mcfc-annual-report-2024-25-.pdf`, que es el informe de actividad y no trae estados financieros.
2. **Qué cambia para el OCR:**
   - Man City deja de necesitarlo si se usa el PDF del club, descargado a mano a `data/raw/manual/`.
   - Liverpool sigue sin texto, pero su PDF es un render limpio, sin ruido de escáner: como base de OCR es mejor que el escaneo de Companies House.
   - En Tottenham y Newcastle no se ha comparado la calidad de imagen con la de Companies House.
   - Arsenal y Chelsea solo están en Companies House.

## 2. Cotizados pendientes: Juventus, Celtic y Lazio

| Club | PDF 2024/25 | Página donde está el enlace | ¿Texto seleccionable en la cuenta de resultados? | Entidad y cierre | robots.txt |
| --- | --- | --- | --- | --- | --- |
| Juventus | En italiano, la versión que prevalece: [e0wkkhbyscbvklpjx5kg.pdf](https://www.juventus.com/images/image/private/fl_attachment/dev/e0wkkhbyscbvklpjx5kg.pdf), "Relazione Finanziaria Annuale al 30 giugno 2025". En inglés: [kxj334yxgnpmidayi3wp.pdf](https://www.juventus.com/images/image/private/fl_attachment/dev/kxj334yxgnpmidayi3wp.pdf), "Annual financial report as at 30 June 2025" | [Bilanci e relazioni](https://www.juventus.com/it/club/investitori/bilanci-prospetti/bilanci-relazioni) y [Reports](https://www.juventus.com/en/club/investor-relations/statements/reports), filtro 2024/25. La lista no está en el HTML: la página la carga de `/it/club/investitori/_libraries/season-2024-25/1/_reports` (y su equivalente en `/en/club/investor-relations/`) | **Sí.** Italiano: 259 páginas, 256 con texto (99%). Inglés: 258 páginas, 255 con texto (99%). Cuenta de resultados consolidada en la pág. 149 de los dos. Esa página tiene dos tablas lado a lado (resultados y resultado global) y pdfplumber mezcla sus líneas: hay que recortar la mitad izquierda | Juventus Football Club S.p.A., consolidado, cierre 30/06/2025. La versión inglesa avisa en la portada de que prevalece la italiana | www.juventus.com: no bloquea `/images/`. `Disallow: /_libraries/*` solo afecta a rutas que empiezan así en la raíz, no a las listas, que cuelgan de `/it/club/…` |
| Celtic | [Celtic_plc_Annual_Report_2025.pdf](https://cdn.celticfc.com/assets/Celtic_plc_Annual_Report_2025.pdf) | [Annual Reports](https://www.celticfc.com/club/celtic-plc-investor-relations/celtic-plc-annual-reports/), bloque "Annual Report 2025". El enlace está en los datos JSON de la página, con las barras escapadas (`https://…`), y por eso no aparecía al buscar `https://…pdf` en la fase 0 | **Sí.** 43 páginas, 39 con texto (91%). Cuenta de resultados consolidada (statement of comprehensive income) en la pág. 26, junto al balance: cada página del PDF son dos del informe y hay que recortar | Celtic plc (SC003487), grupo, cierre 30/06/2025 | www.celticfc.com: permite todo salvo `/newsstory/`, `/newsroom/` y `/stories/`. cdn.celticfc.com no tiene robots.txt (403 de S3), así que no hay restricciones |
| Lazio | [CopiadiCortesiaRelazionefinanziariaSSlazio30_06_25.pdf](https://mediaverse.sslazio.hiway.media/VMFS1/FILES/public/upload/68e56f4d/CopiadiCortesiaRelazionefinanziariaSSlazio30_06_25.pdf), "Relazione finanziaria annuale al 30 giugno 2025", publicada el 07/10/2025 | [Documenti](https://www.sslazio.it/en/investor-relators/documenti). El enlace está en los datos JSON de la página (campo `file_url`) | **No.** 208 páginas y ninguna con texto: imagen, escaneada. Cuenta de resultados consolidada en la pág. 141; la separada va en la parte I, a partir de la pág. 47 | S.S. Lazio S.p.A., cuentas separadas y consolidadas, cierre 30/06/2025 | www.sslazio.it: para `User-agent: *` permite la página y bloquea `/admin/`, `/mobile/` y `/api/`. Bloquea por nombre a los crawlers de IA (GPTBot, ClaudeBot…) y permite expresamente ChatGPT-User y OAI-SearchBot, que el propio archivo describe como peticiones lanzadas por un usuario. mediaverse.sslazio.hiway.media: permite la ruta del PDF, con `Crawl-delay: 10` |

**Notas:**

1. **Lazio:** el nombre del archivo dice "copia di cortesia". Según el [aviso del club](https://mediaverse.sslazio.hiway.media/VMFS1/FILES/public/upload/68e5706e/S.S.LAZIOS.p.A.-LinkreperibilitRelazioneFinanziariaAnnualeESEFal30.06.2025.pdf), la versión oficial en formato ESEF se depositó en el portal 1info. La dirección que da, `https://www.1info.it/PORTALE1INFO`, devuelve una página 404 y el archivo ESEF no se ha localizado. Merece la pena buscarlo antes de pasar 208 páginas por OCR: el ESEF es XHTML con etiquetas iXBRL, que se leen sin OCR. **Localizado el 27/09/2026 (sección 6.1).**
2. **Juventus:** la lista fecha el informe el 10/11/2025, pero los metadatos de los dos PDFs dicen que se crearon el 17/02/2026. Probablemente se sustituyó el archivo sin cambiar la URL, así que el sha256 de la tabla de huellas es el que manda.

## 3. FC Porto: fuente alternativa

| Fuente | URL | Resultado | ¿Texto seleccionable? | robots.txt |
| --- | --- | --- | --- | --- |
| CMVM, portal actual | [cmvm.pt](https://www.cmvm.pt/) | **No verificable hoy.** Devuelve una página de mantenimiento programado: cmvm.pt, bue.cmvm.pt e investidor.cmvm.pt no están disponibles "entre as 09h:00 do dia 26/09/2026 e as 18h:00 do dia 27/09/2026" | — | 404, porque responde la página de mantenimiento |
| CMVM, sistema de difusión antiguo | `https://web3.cmvm.pt/sdi/emitentes/index.cfm` | 502 | — | 502: según la RFC 9309, mientras dure hay que suponer que todo está prohibido |
| Portal de transparencia del club | [ComunicadoDivulgacaoResultados20242025.pdf](https://transparencia.fcporto.pt/assets/uploads/financeira/ComunicadoDivulgacaoResultados20242025.pdf) | Comunicado "Resultados Consolidados 2024/2025" de Futebol Clube do Porto – Futebol, SAD, creado el 01/10/2025. Tiene 8 páginas: resumen de la cuenta de resultados consolidada en la pág. 4 y de la posición financiera en la 7. No trae notas ni el desglose completo, así que no sustituye al informe anual (Relatório e Contas). Se encontró con el buscador: la página del portal que lo enlaza no se localizó, porque el portal carga sus listas desde una API | **Sí,** 8 de 8 páginas | transparencia.fcporto.pt no tiene robots.txt (404), así que no hay restricciones |
| Servidor de archivos del club | `files.app.fcporto.pt/docs/…` | Tiene los informes anuales de 2020/21 a 2023/24 y el semestral de 2024/25, abiertos para comprobar el año. El anual 2024/25 no se encontró | — | Sin robots.txt (404) |

**Notas:**

1. **Cierre de Porto confirmado:** el comunicado compara la posición financiera a 30/06/2024 y a 30/06/2025 (pág. 7). Queda resuelto lo que el plan dejaba "por confirmar" en la sección 6.
2. **fcporto.pt:** hoy `www.fcporto.pt/pt/clube/institucional` responde 200, cuando en la fase 0 dio 403. Es una aplicación JavaScript sin enlaces en el HTML, y su `/robots.txt` devuelve la propia página HTML, no un robots.txt.
3. **27/09/2026:** la CMVM ya responde. El informe anual completo está en la sección 6.2.

## 4. Huellas de los archivos abiertos

Descargados con curl el 26/09/2026 a una carpeta temporal, no a `data/raw/`. Cuando se descarguen de verdad, el manifiesto volverá a calcular el sha256; si no coincide con este, el archivo ha cambiado en el servidor.

| Archivo | Bytes | Páginas | sha256 | Creado (metadatos del PDF) |
| --- | --- | --- | --- | --- |
| Liverpool `2025_Accounts_….pdf` | 11.231.905 | 38 | `1ab49db90f9ed97ef3f8d322e316b97a74d69a1597e304a364193071f1008d04` | 26/09/2025, PDF-XChange |
| Tottenham `AR-2025.pdf` | 6.696.476 | 65 | `80fe4ba4d01a0a6c381560e10ad10d4baa11af9242870d6dd9399a8752c42cc9` | sin fecha |
| Newcastle `…Signed_Statutory_Financial_Statements.pdf` | 8.514.263 | 47 | `044fb3a439655365f29c89c1d4caec21a6e35d1f1cd2a65f993bd4b76e5e7f27` | 09/11/2025, Acrobat Sign |
| Juventus `e0wkkhbyscbvklpjx5kg.pdf` (IT) | 27.706.913 | 259 | `62fbf252cf0c8e5fb9984a88dc09dac7fec6764b9f0ddf382ac9421f61fed5f8` | 17/02/2026, InDesign |
| Juventus `kxj334yxgnpmidayi3wp.pdf` (EN) | 19.119.384 | 258 | `92f61f1283e8132a26014f11d14c5ad927778166b9159ca5a511c277343bae21` | 17/02/2026, InDesign |
| Celtic `Celtic_plc_Annual_Report_2025.pdf` | 3.173.758 | 43 | `27226bdfc5214337d04c6c5a128f0ed1c0668dfb316a3cf01ee182e1d42b9a5d` | 06/10/2025, InDesign |
| Lazio `CopiadiCortesia….pdf` | 13.137.702 | 208 | `d90c12d50956018f4fc2a2a858c08e23c3d18c16514939a048a2fad6613d3ab0` | 07/10/2025, iLovePDF |
| Porto `ComunicadoDivulgacaoResultados20242025.pdf` | 927.572 | 8 | `9503f4217a4537f1c85f13ebff76e1a106bd1f1d8131e85865960679397886b5` | 01/10/2025, Microsoft Print to PDF |

Man City no está en la tabla porque no se pudo descargar con curl.

## 5. Lo que sigue abierto

| Pendiente | Motivo |
| --- | --- |
| Descargar a mano el PDF de Man City y medirlo con pdfplumber | Cloudflare bloquea la descarga automática aunque robots.txt la permite |
| Arsenal y Chelsea | Sin PDF en su web: solo queda Companies House, es decir, OCR |
| ESEF de Lazio 2024/25 | Localizado el 27/09/2026 (sección 6.1). Falta decidir si pasa a ser la fuente y cómo se lee |
| Porto: informe anual 2024/25 completo | Localizado el 27/09/2026 en la CMVM (sección 6.2). No tiene URL de descarga: hay que bajarlo a mano |
| Fijar las URLs en `config/sources.yaml` | Fuera del alcance de esta tarea: `config/` no se ha tocado |

## 6. Lazio y FC Porto: fuentes oficiales (27/09/2026)

Consultado el 27/09/2026, entre las 12:20 y las 12:40 UTC, en Cowork. El ZIP de Lazio se descargó a una carpeta temporal fuera del repo, solo para abrirlo. El PDF de Porto no se descargó: se abrió en el visor de la CMVM y se midió desde el navegador.

### 6.1 Lazio: ESEF 2024/25 en 1info

| Qué | Resultado |
| --- | --- |
| Dónde está | Portal [1info](https://www.1info.it/PORTALE1INFO) (Computershare), que según su propia descripción es el sistema de almacenamiento de información regulada autorizado por CONSOB en 2014. Emisor "S.S. LAZIO", categoría 1.1 "Relazione finanziaria annuale e relazione di revisione annuale" |
| Documento | "Relazione finanziaria annuale separata e consolidata al 30.06.2025", almacenado el 07/10/2025 a las 21:09 UTC, protocolo `159386_oneinfo`. El portal lo marca como balance ESEF oficial. Es el único ESEF de 2024/25; de 2023/24 hay dos, el segundo con ".1" en el título |
| URL del ZIP | [PdfShow.aspx?…file=159386_oneinfo.zip](https://www.1info.it/PdfViewer/PdfShow.aspx?service=&type=documenti&year=2025&file=159386_oneinfo.zip&download=1): `https://www.1info.it/PdfViewer/PdfShow.aspx?service=&type=documenti&year=2025&file=159386_oneinfo.zip&download=1`. Responde 200 a un GET sin cookies ni token, con `content-disposition: attachment; filename="159386_oneinfo.zip"` |
| Tamaño | 2.306.292 bytes, sha256 `e46d5439fd829201233ff19a084ff29086165a529de55131f6b75bd7664405cf`. Descomprimido: 8 archivos y 20.002.312 bytes |
| Contenido | Paquete ESEF `81560036DCCA48CA0F08-2025-06-30-0-it`. El informe es `reports/81560036DCCA48CA0F08-2025-06-30-0-it.html` (11.960.562 bytes): XHTML con iXBRL, aunque la extensión es `.html` y no `.xhtml`. El resto es la taxonomía de la sociedad (`.xsd` y linkbases) y `META-INF` |
| Texto | 208 páginas, las mismas que el PDF de cortesía. Con el umbral de 200 caracteres no blancos, 197 de 208 tienen texto (95%). Las 11 restantes tienen entre 39 y 192 caracteres |
| Cuentas | Separadas desde la pág. 47 y consolidadas con la cuenta de resultados en la pág. 141, como en el PDF de cortesía. Las cifras van "in Euro", en unidades y no en miles |
| Etiquetas iXBRL | 259 cifras (`ix:nonFraction`), todas en las págs. 138, 139, 141, 143 y 145: solo los estados consolidados. Las cuentas separadas son texto sin etiquetas. Entidad: LEI 81560036DCCA48CA0F08 |
| robots.txt | `www.1info.it/robots.txt` responde 404: sin restricciones |

**Cómo se llegó:**

1. `https://www.1info.it/PORTALE1INFO`, que el 26/09/2026 llevaba a una página 404, hoy responde 200. Es una aplicación JavaScript: la lista de documentos sale de un `POST` a `/PORTALE1INFO/API/Documenti` con el filtro de emisor, sin autenticación.
2. El botón de descarga abre `https://www.1info.it/PORTALE1INFO/Pdf/Pdf?pdf=159386_oneinfo.zip&data=2025&filetype=documenti&titolo=&download=1`, una página HTML de 1.475 bytes con un iframe que apunta a la URL del ZIP.
3. El portal ofrece también una versión firmada (`.p7m`), que no se ha abierto.
4. **Borsa Italiana y CONSOB no se han consultado:** 1info es el almacenamiento autorizado y el documento estaba allí.

**Qué cambia:** con el ESEF, Lazio no necesita OCR. Pero el pipeline solo lee PDFs, así que habría que escribir un lector de XHTML (texto de las cuentas separadas) e iXBRL (etiquetas de las consolidadas).

### 6.2 FC Porto: Relatório Anual Integrado 2024/2025 en la CMVM

| Qué | Resultado |
| --- | --- |
| Estado de la CMVM | Fuera de mantenimiento: `www.cmvm.pt` responde 200 |
| Cómo se llega | Sistema de Difusão de Informação → Emitentes → Informação periódica → Relatório e contas → Anuais, con el filtro Entidade "Futebol Clube do Porto - Futebol, SAD" |
| Publicaciones de 2024/25 | Dos, el 01/10/2025: "Relatório Anual Integrado 2024/2025 - versão não ESEF" a las 07:53 y "… - versão ESEF" a las 08:27, según la hora que muestra la CMVM |
| URL del PDF | [PdfViewerInfPriv?Input=EBA43BC8…](https://www.cmvm.pt/PInstitucional/PdfViewerInfPriv?Input=EBA43BC8F4EB22A844F75CC1AC19DCE1954A814A216A036952C6F2AD11B1DA92): `https://www.cmvm.pt/PInstitucional/PdfViewerInfPriv?Input=EBA43BC8F4EB22A844F75CC1AC19DCE1954A814A216A036952C6F2AD11B1DA92`. Es la página del visor, no el archivo. Se abrió también entrando directamente por ella |
| Tamaño y huella | 52.410.765 bytes, sha256 `c4c675ff54a89b0a37c77c6ca52d7e3d8b0f7a8d86ef0dedcc28842b72cda675`, calculados en el navegador sobre los bytes que carga el visor. Creado el 29/09/2025 con Adobe InDesign 20.1 |
| Páginas | 259. Cada página del PDF son dos del informe: la 117 lleva las 232 y 233 impresas, como en Celtic |
| Capa de texto | **Medida con pdf.js en el navegador, no con pdfplumber:** 238 de 259 páginas con 200 caracteres o más (92%), es decir, texto. Por debajo quedan la portada (1), la última (259), 9 páginas con una sola imagen y poco texto (25, 33, 43, 115, 166, 171, 218, 222 y 226, varias de ellas portadas de sección) y 10 escaneadas, con imágenes y solo el número de página como texto: 167 a 170 (certificación legal de las cuentas consolidadas), 219 a 221 (la de las individuales) y 223 a 225 (informe y dictamen del Conselho Fiscal) |
| Consolidadas e individuales | **Las dos.** "B. Demonstrações Financeiras Consolidadas e Anexos" desde la pág. 115, con la posición financiera en la 116 y los resultados por naturalezas en la 117. "C. Demonstrações Financeiras Individuais e Anexos" desde la 171, con la posición en la 172 y los resultados en la 173. Todas en miles de euros y con la columna 30.06.2024 antes que la 30.06.2025 |
| robots.txt | `www.cmvm.pt/robots.txt`: para `User-agent: *` solo bloquea `/PInstitucional/css/extra.css`. El visor está permitido |
| Descarga automática | **No hay URL del archivo.** El visor recibe el PDF en la respuesta de un `POST` a `/PInstitucional/screenservices/PInstitucional/ServiceAPIStatic_Portal2` (la CMVM es una aplicación OutSystems) y lo muestra como `blob:`. Reproducir esa llamada es el mismo caso que Dortmund, así que la vía limpia es la descarga manual desde el visor a `data/raw/manual/` |
| Versión ESEF | [EsefViewer?Input=99BC9C61…](https://www.cmvm.pt/PInstitucional/EsefViewer?Input=99BC9C615DC912777714BCA1822FC54BAC0DA3E65E65E769706697BB0AA377DD): `https://www.cmvm.pt/PInstitucional/EsefViewer?Input=99BC9C615DC912777714BCA1822FC54BAC0DA3E65E65E769706697BB0AA377DD`. Muestra el informe completo, con 422 cifras etiquetadas (`ix:nonFraction`) y la entidad LEI 549300H3W4IIDNIV6I38. El ZIP se baja con el botón "Download ZIP", que llama al servidor y no tiene URL; su tamaño está sin medir. La CMVM avisa en esa sección de que la versión ESEF es la oficial y prevalece sobre el PDF si difieren |

**Qué cambia:** Porto tiene cuentas completas, con notas y con texto, en dos formatos, y los dos se bajan a mano. La capa de texto del PDF hay que volver a medirla con pdfplumber cuando esté en `data/raw/manual/`.
