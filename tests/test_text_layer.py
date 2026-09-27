"""Medición de la capa de texto con los fixtures sintéticos de una página."""

from pathlib import Path

import pytest

from pitch_to_balance_sheet.extract.text_layer import classify, measure

FIXTURES = Path(__file__).parent / "fixtures"


def test_pagina_con_capa_de_texto():
    layer = measure(FIXTURES / "pagina_texto.pdf")
    assert layer.pages == 1
    assert layer.chars_per_page[0] >= 200
    assert layer.classification == "texto"
    assert layer.keywords_found("ingresos") == ("turnover",)
    assert layer.keywords_found("personal") == ("staff costs", "wages")
    assert layer.keyword_pages["turnover"] == (1,)


def test_pagina_escaneada_sin_capa_de_texto():
    layer = measure(FIXTURES / "pagina_imagen.pdf")
    assert layer.pages == 1
    assert layer.chars_per_page == (0,)
    assert layer.classification == "imagen"
    assert layer.keywords_found("ingresos") == ()
    assert layer.keywords_found("personal") == ()


@pytest.mark.parametrize(
    ("chars_per_page", "expected"),
    [
        ([200] * 8 + [0] * 2, "texto"),  # 80 %: límite inferior de texto
        ([200] * 7 + [0] * 3, "mixto"),
        ([200] * 2 + [0] * 8, "mixto"),  # 20 %: límite inferior de mixto
        ([200] * 1 + [0] * 9, "imagen"),
        ([199] * 10, "imagen"),  # con menos de 200 caracteres no es página con texto
    ],
)
def test_clasificacion_en_los_limites(chars_per_page, expected):
    assert classify(chars_per_page) == expected


def test_si_pdfplumber_no_puede_abrirlo_se_abre_con_pypdfium2(monkeypatch):
    from pitch_to_balance_sheet.extract import text_layer

    def falla(path):
        raise RuntimeError("PSEOF('Unexpected EOF')")

    monkeypatch.setattr(text_layer, "_page_texts_pdfplumber", falla)
    layer = measure(FIXTURES / "pagina_texto.pdf")
    assert layer.engine == "pypdfium2"
    assert layer.classification == "texto"
    assert layer.keywords_found("personal") == ("staff costs", "wages")


def test_pdf_sin_paginas_es_error():
    with pytest.raises(ValueError, match="no tiene páginas"):
        classify([])


def test_palabras_clave_en_cinco_idiomas_sin_distinguir_acentos(monkeypatch):
    from pitch_to_balance_sheet.extract import text_layer

    pages = [
        "KONZERNGESAMTERGEBNISRECHNUNG\nKonzernumsatzerlo\u0308se 526.019\nPersonalaufwand",
        "Totale ricavi e proventi 529.630\nPersonale tesserato",
        "Netto-omzet 178.129\nPersoneelskosten",
        "Rendimentos operacionais 230.618\nGastos com\npessoal",
        "Group turnover\nStaff costs",
    ]
    monkeypatch.setattr(text_layer, "_page_texts_pdfplumber", lambda path: pages)
    layer = measure(Path("no-se-abre.pdf"))
    assert {term: layer.keyword_pages[term] for term in layer.keyword_pages
            if layer.keyword_pages[term]} == {
        "umsatzerlöse": (1,), "personalaufwand": (1,),
        "ricavi": (2,), "personale": (2,),
        "omzet": (3,), "personeelskosten": (3,),
        "rendimentos": (4,), "gastos com pessoal": (4,),
        "turnover": (5,), "staff costs": (5,),
    }
    assert text_layer.column_name("umsatzerlöse") == "umsatzerlose"
    assert text_layer.column_name("gastos com pessoal") == "gastos_com_pessoal"
