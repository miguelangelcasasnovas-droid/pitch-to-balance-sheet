"""Genera los fixtures de una página de tests/test_text_layer.py y tests/test_ocr.py.

Son sintéticos, sin datos de ningún club:
- pagina_texto.pdf: una página con capa de texto y rótulos contables genéricos, sin cifras.
- pagina_imagen.pdf: la misma página convertida en imagen, como un escaneo, sin capa de texto.
- pagina_ocr.pdf: una cuenta de resultados inventada, solo imagen, para probar imagen -> OCR ->
  cifra. Las cifras son inventadas y cuadran: 123,456 - 23,456 = 100,000, etc.
- tabla_texto.pdf: otra cuenta de resultados inventada, con capa de texto (Courier), para probar
  el motor de extracción sin OCR: cuadres, guiones y paréntesis.

Uso: .venv/bin/python tests/fixtures/generar_fixtures.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
LINES = [
    "Fixture sintetico para tests: rotulos genericos, sin cifras de ningun club.",
    "Consolidated profit and loss account",
    "Turnover",
    "Operating expenses",
    "Staff costs",
    "Wages and salaries",
    "Social security costs",
    "Amortisation of player registrations",
    "Profit on disposal of player registrations",
    "Interest payable and similar charges",
    "Consolidated balance sheet",
    "Cash at bank and in hand",
    "Borrowings",
]


def pdf_bytes(stream: bytes, font: str = "Helvetica") -> bytes:
    """PDF mínimo de una página A4 con el contenido dado y una fuente Type1 estándar."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /%s >>" % font.encode("ascii"),
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def text_pdf(lines: list[str]) -> bytes:
    """Una página con el texto en Helvetica, una línea debajo de otra."""
    text = " T* ".join(f"({line}) Tj" for line in lines)
    return pdf_bytes(f"BT /F1 11 Tf 14 TL 50 790 Td {text} ET".encode("ascii"))


# Rótulo y cifras 2025 y 2024 de una cuenta de resultados inventada, con capa de texto.
TEXT_PNL = [
    ("Turnover", "1,000", "900"),
    ("Cost of sales", "(400)", "(300)"),
    ("Gross profit", "600", "600"),
    ("Other income", "-", "100"),
    ("Profit for the year", "600", "700"),
]


def table_pdf() -> bytes:
    """Tabla con las cifras alineadas a la derecha de sus columnas. En Courier cada carácter
    mide 0,6 veces el cuerpo, así que el borde derecho de cada cifra se calcula exacto."""
    size, columns = 10, (400, 500)
    items = [(50, 780, "EJEMPLO FC LIMITED (fixture sintetico, cifras inventadas)")]
    for x, year in zip(columns, ("2025", "2024"), strict=True):
        items += [(x - 0.6 * size * len(year), 740, year),
                  (x - 0.6 * size * len("£'000"), 726, "£'000")]
    for row, (label, current, previous) in enumerate(TEXT_PNL):
        y = 700 - 18 * row
        items.append((50, y, label))
        for x, value in zip(columns, (current, previous), strict=True):
            items.append((x - 0.6 * size * len(value), y, value))
    stream = " ".join(
        f"BT /F1 {size} Tf {x:.1f} {y} Td ({text.replace('£', chr(0xA3))}) Tj ET"
        for x, y, text in items
    )
    return pdf_bytes(stream.encode("latin-1"), font="Courier")


def image_pdf(lines: list[str], path: Path) -> None:
    """La misma página dibujada como imagen: el texto son píxeles, no caracteres."""
    image = Image.new("L", (595, 842), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=11)
    for row, line in enumerate(lines):
        draw.text((50, 52 + 14 * row), line, fill=0, font=font)
    image.save(path, "PDF", resolution=72)


# Rótulo, nota y cifras 2025 y 2024 de una cuenta de resultados inventada.
PNL = [
    ("Turnover", "3", "123,456", "100,000"),
    ("Cost of sales", "", "(23,456)", "(20,000)"),
    ("Gross profit", "", "100,000", "80,000"),
    ("Administrative expenses", "", "(104,321)", "(81,234)"),
    ("Other operating income", "", "-", "500"),
    ("Loss for the financial year", "", "(4,321)", "(734)"),
]


def ocr_pdf(path: Path) -> None:
    """Cuenta de resultados de una página, solo imagen a 150 ppp, con las cifras alineadas a la
    derecha de sus columnas como en unas cuentas reales.

    Usa Arial de macOS: la fuente por defecto de Pillow no tiene el símbolo £.
    """
    image = Image.new("L", (1240, 1754), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(ARIAL, 26)
    draw.text((120, 120), "EJEMPLO FC LIMITED (fixture sintetico, cifras inventadas)", fill=0,
              font=font)
    draw.text((120, 170), "PROFIT AND LOSS ACCOUNT", fill=0, font=font)
    columns = (900, 1120)  # borde derecho de cada columna

    def right(text: str, x: int, y: int) -> None:
        draw.text((x - draw.textlength(text, font=font), y), text, fill=0, font=font)

    for x, year in zip(columns, ("2025", "2024"), strict=True):
        right(year, x, 280)
        right("£'000", x, 320)
    right("Notes", 640, 320)
    for row, (label, note, current, previous) in enumerate(PNL):
        y = 400 + 60 * row
        draw.text((120, y), label, fill=0, font=font)
        if note:
            right(note, 640, y)
        right(current, columns[0], y)
        right(previous, columns[1], y)
    image.save(path, "PDF", resolution=150)


if __name__ == "__main__":
    (HERE / "pagina_texto.pdf").write_bytes(text_pdf(LINES))
    image_pdf(LINES, HERE / "pagina_imagen.pdf")
    ocr_pdf(HERE / "pagina_ocr.pdf")
    (HERE / "tabla_texto.pdf").write_bytes(table_pdf())
