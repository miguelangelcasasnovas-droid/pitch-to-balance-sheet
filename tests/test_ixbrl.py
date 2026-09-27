"""Lector de iXBRL con un paquete ESEF sintético (tests/fixtures/esef_sintetico), sin red."""

import unicodedata
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

from pitch_to_balance_sheet.extract.ixbrl import IxbrlError, read_report, transform
from pitch_to_balance_sheet.extract.statements import (
    Calc,
    ExtractionError,
    FigureSpec,
    IxbrlDocumentSpec,
    Part,
    read_document,
)

FIXTURE = Path(__file__).parent / "fixtures" / "esef_sintetico"
LEI = "SINTETICO0000000000X1"
CURRENT, PREVIOUS = "2030-07-01/2031-06-30", "2029-07-01/2030-06-30"


@pytest.fixture
def package(tmp_path) -> Path:
    """El fixture empaquetado como un ZIP ESEF: <paquete>/reports/ y el linkbase de cálculo."""
    path = tmp_path / "esef.zip"
    with zipfile.ZipFile(path, "w") as zipped:
        for file in FIXTURE.rglob("*.x*ml"):
            zipped.write(file, f"SINTETICO-2031-06-30/{file.relative_to(FIXTURE)}")
    return path


def test_lee_los_hechos_con_contexto_unidad_escala_y_signo(package):
    report = read_report(package)
    assert report.name == "SINTETICO-2031-06-30/reports/informe.xhtml"
    assert len(report.facts) == 17
    revenue = report.find("ifrs-full:Revenue", LEI, CURRENT)
    assert (revenue.value, revenue.raw, revenue.unit, revenue.decimals) == (
        Decimal(1234567), "1.234.567", "iso4217:EUR", "0")
    assert (revenue.page, revenue.label, revenue.id) == (2, "Totale ricavi", "f3")
    assert report.find("ifrs-full:Revenue", LEI, PREVIOUS).value == 1000000  # num-dot-decimal
    loss = report.find("ifrs-full:ProfitLoss", LEI, PREVIOUS)
    assert (loss.value, loss.sign) == (-550000, "-")  # sign="-": el texto no lleva el signo
    assert report.find("ifrs-full:OtherExpenseByNature", LEI, CURRENT).value == 0  # fixed-zero
    eps = report.find("ifrs-full:BasicEarningsLossPerShare", LEI, CURRENT)
    assert (eps.value, eps.unit) == (Decimal("0.25"), "iso4217:EUR/xbrli:shares")


def test_el_perimetro_sin_dimensiones_es_el_consolidado(package):
    report = read_report(package)
    assert report.find("ifrs-full:Revenue", LEI, CURRENT).value == 1234567
    separate = (("ifrs-full:ConsolidatedAndSeparateFinancialStatementsAxis",
                 "ifrs-full:SeparateMember"),)
    assert report.find("ifrs-full:Revenue", LEI, CURRENT, separate).value == 999


def test_la_escala_multiplica_el_valor(package):
    inventories = [f for f in read_report(package).facts if f.id == "f15"][0]
    assert (inventories.scale, inventories.value) == (3, 1234000)


def test_duplicados_iguales_valen_y_distintos_son_error(package):
    report = read_report(package)
    assert report.find("ifrs-full:ProfitLoss", LEI, CURRENT).value == 744567  # f11 y f13
    with pytest.raises(IxbrlError, match="valores distintos"):
        report.find("ifrs-full:Inventories", LEI, "2031-06-30")
    with pytest.raises(IxbrlError, match="no hay ningún hecho"):
        report.find("ifrs-full:Assets", LEI, CURRENT)


def test_el_nombre_del_concepto_se_compara_en_nfc(package):
    report = read_report(package)
    decomposed = unicodedata.normalize("NFD", "ext:RicaviPubblicità")
    assert report.find(decomposed, LEI, CURRENT).value == 234567


def test_lee_los_pesos_del_linkbase_de_calculo(package):
    calculations = read_report(package).calculations
    assert calculations[("ifrs-full:ProfitLoss", "ifrs-full:EmployeeBenefitsExpense")] == -1
    assert calculations[("ifrs-full:ProfitLoss",
                         "ifrs-full:DeferredTaxExpenseIncomeRecognisedInProfitOrLoss")] == 1


def test_un_formato_desconocido_es_error():
    with pytest.raises(IxbrlError, match="formato ixt no previsto"):
        transform("1 234", "ixt:num-space-decimal-inventado")
    with pytest.raises(IxbrlError, match="no es un número"):
        transform("1.234.567", "ixt:num-dot-decimal")


def _spec(deferred_weight: int = 1) -> IxbrlDocumentSpec:
    return IxbrlDocumentSpec(
        entity=LEI,
        periods={"2031": CURRENT, "2030": PREVIOUS},
        unit="iso4217:EUR",
        concepts={"revenue": "ifrs-full:Revenue", "advertising": "ext:RicaviPubblicità",
                  "staff": "ifrs-full:EmployeeBenefitsExpense",
                  "other": "ifrs-full:OtherExpenseByNature",
                  "deferred_tax": "ifrs-full:DeferredTaxExpenseIncomeRecognisedInProfitOrLoss",
                  "net_result": "ifrs-full:ProfitLoss"},
        calcs=(Calc("net_result", (("revenue", 1), ("staff", -1), ("other", -1),
                                   ("deferred_tax", deferred_weight))),),
        figures=(
            FigureSpec("revenue_total_reported", (("ixbrl", "revenue"),), "2031"),
            FigureSpec("revenue_ex_player_trading",
                       (Part("ixbrl", "revenue"), Part("ixbrl", "advertising", sign=-1)), "2031"),
            FigureSpec("net_result", (("ixbrl", "net_result"),), "2031"),
        ),
    )


def test_documento_ixbrl_cifras_en_miles_sin_redondear_y_cuadres_en_euros(package, tmp_path):
    result = read_document("principal", _spec(), package, "sha", tmp_path)
    assert [check.ok for check in result.checks] == [True, True]
    assert (result.checks[0].reported, result.checks[0].computed) == (744567, 744567)
    figures = {figure.concept: figure for figure in result.figures}
    assert figures["revenue_total_reported"].value == Decimal("1234.567")
    assert figures["revenue_ex_player_trading"].value == Decimal("1000.000")
    assert figures["revenue_ex_player_trading"].is_derived
    assert figures["net_result"].value == Decimal("744.567")
    revenue = figures["revenue_total_reported"]
    assert (revenue.page, revenue.label, revenue.method) == (2, "Totale ricavi", "ixbrl")
    assert "ifrs-full:Revenue [contexto c_act, 2030-07-01–2031-06-30" in revenue.sources
    assert revenue.ocr_note.startswith("iXBRL, sin OCR: iso4217:EUR con scale 0 y decimals 0")


def test_un_peso_distinto_del_linkbase_del_emisor_es_error(package, tmp_path):
    # El emisor suma los impuestos diferidos (+1); restarlos contradice su linkbase.
    with pytest.raises(ExtractionError, match="deferred_tax va con peso -1 y el linkbase de "
                                              "cálculo del emisor le da \\+1"):
        read_document("principal", _spec(deferred_weight=-1), package, "sha", tmp_path)


def test_lo_que_no_es_un_zip_es_error(tmp_path):
    path = tmp_path / "x.zip"
    path.write_bytes(b"%PDF-1.7")
    with pytest.raises(IxbrlError, match="no es un ZIP"):
        read_report(path)
