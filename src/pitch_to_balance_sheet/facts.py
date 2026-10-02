"""Tabla larga fact_financials (sección 5 del plan): una fila por club, temporada y concepto.

Sale de las cifras extraídas (data/interim/cifras_<temporada>.csv, que escribe extract) y de los
tipos del BCE (data/raw/ecb/). Cada fila lleva la cifra tal como la da el informe, su conversión
a EUR (fx_rate, fx_method, fx_date y value_eur), su fuente con la URL y la fecha de descarga del
manifiesto, y el motivo si es un hueco. Se valida con pandera y se guarda en
data/processed/fact_financials.parquet y en la tabla fact_financials de football.duckdb.

Si un club de la extracción está en error, si falta un tipo o si la validación falla, no se
escribe nada: sale con error y dice por qué.
"""

import csv
from decimal import Decimal
from pathlib import Path

import duckdb
import pandas as pd
import pandera.pandas as pa

from pitch_to_balance_sheet import fx, manifest
from pitch_to_balance_sheet.concepts import COUNT, FLOW, KINDS, MULTIPLIERS, STOCK
from pitch_to_balance_sheet.config import (
    INTERIM_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    load_clubs,
    season_slug,
)
from pitch_to_balance_sheet.extract import mix

FX_METHODS = {FLOW: {fx.AVERAGE, fx.NO_CONVERSION}, STOCK: {fx.CLOSING, fx.NO_CONVERSION},
              COUNT: {fx.NOT_MONETARY}}
COLUMNS = [
    # Clave
    "club_id", "season", "fiscal_year_end", "concept",
    # Cifra original
    "label_original", "value_reported", "unit_reported", "currency_reported", "value_full",
    # Conversión
    "fx_rate", "fx_method", "fx_date", "value_eur", "fx_source_file", "fx_note",
    # Fuente
    "source_file", "source_page", "source_url", "retrieved_at", "sha256", "components",
    "column", "crop", "extraction_method", "ocr_note",
    # Huecos y definición
    "is_gap", "gap_reason", "is_derived", "included_in_staff_costs", "definition_note",
]
DATABASE = "football.duckdb"


class FactsError(RuntimeError):
    """La tabla no se puede construir o no pasa la validación."""


def facts_path(season: str, directory: Path = PROCESSED_DIR) -> Path:
    """Parquet de una temporada; la de 2024/25 es data/processed/fact_financials.parquet."""
    if season == "2024/25":
        return directory / "fact_financials.parquet"
    return directory / f"fact_financials_{season_slug(season)}.parquet"


def _read_figures(path: Path) -> list[dict]:
    if not path.exists():
        raise FactsError(f"falta {path}: ejecuta antes extract")
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    failed = sorted({row["club_id"] for row in rows if row["status"] != "ok"})
    if failed:
        raise FactsError(f"la extracción de {', '.join(failed)} está en error: arréglala y "
                         "vuelve a ejecutar extract")
    return rows


def _rates(season: str, currencies: set[str], raw_dir: Path, manifest_path: Path):
    rates = {}
    for currency in sorted(currencies - {fx.BASE}):
        file = fx.rates_file(currency, season)
        try:
            manifest.verify(raw_dir, file, manifest_path)
        except manifest.ManifestError as exc:
            raise FactsError(f"{exc}: ejecuta download-fx") from exc
        rates[currency] = (file, fx.load_rates(raw_dir / file, currency))
    return rates


def build(season: str, figures_path: Path | None = None, raw_dir: Path = RAW_DIR,
          manifest_path: Path | None = None) -> pd.DataFrame:
    figures_path = figures_path or INTERIM_DIR / f"cifras_{season_slug(season)}.csv"
    manifest_path = manifest_path or raw_dir / "manifest.csv"
    rows = _read_figures(figures_path)
    unknown = sorted({row["concept"] for row in rows} - set(KINDS))
    if unknown:
        raise FactsError(f"conceptos fuera de la lista cerrada: {', '.join(unknown)}")
    fiscal_year_ends = {club.club_id: club.fiscal_year_end for club in load_clubs()}
    rates = _rates(season, {row["currency_reported"] for row in rows}, raw_dir, manifest_path)
    entries = manifest.read(manifest_path)
    facts = []
    for row in rows:
        kind = KINDS[row["concept"]]
        is_gap = row["is_gap"] == "True"
        entry = entries.get(row["source_file"])
        if entry is None:
            raise FactsError(f"{row['club_id']}: {row['source_file']} no está en el manifiesto")
        if entry["sha256"] != row["sha256"]:
            raise FactsError(f"{row['club_id']}: el sha256 de {row['source_file']} no es el del "
                             "manifiesto; vuelve a ejecutar extract")
        currency = "" if kind == COUNT else row["currency_reported"]
        fact = {
            "club_id": row["club_id"], "season": season,
            "fiscal_year_end": row["fiscal_year_end"], "concept": row["concept"],
            "label_original": row["label_original"],
            "value_reported": None if is_gap else _integer(row["value_reported"], row),
            "unit_reported": row["unit_reported"], "currency_reported": currency,
            "value_full": None if is_gap else _integer(row["value_full"], row),
            "fx_rate": None, "fx_method": "", "fx_date": "", "value_eur": None,
            "fx_source_file": "", "fx_note": "",
            "source_file": row["source_file"],
            "source_page": None if is_gap else int(row["source_page"]),
            "source_url": entry["url"], "retrieved_at": entry["retrieved_at"],
            "sha256": row["sha256"], "components": row["components"],
            "column": row["column"], "crop": row["crop"],
            "extraction_method": row["extraction_method"], "ocr_note": row["ocr_note"],
            "is_gap": is_gap, "gap_reason": row["gap_reason"],
            "is_derived": row["is_derived"] == "True",
            "included_in_staff_costs": row["included_in_staff_costs"],
            "definition_note": row["definition_note"],
        }
        if not is_gap:
            if MULTIPLIERS[fact["unit_reported"]] * fact["value_reported"] != fact["value_full"]:
                raise FactsError(f"{row['club_id']}.{row['concept']}: value_full no es "
                                 "value_reported por su unidad")
            fact.update(_convert(season, kind, currency, fact["value_full"],
                                 fiscal_year_ends[row["club_id"]], rates))
        facts.append(fact)
    frame = pd.DataFrame(facts, columns=COLUMNS).astype({
        "value_reported": "Int64", "value_full": "Int64", "value_eur": "Int64",
        "source_page": "Int64", "fx_rate": "float64", "is_gap": bool, "is_derived": bool})
    return frame.sort_values(["club_id", "concept"], ignore_index=True)


def _integer(text: str, row: dict) -> int:
    value = Decimal(text)
    if value != value.to_integral_value():
        raise FactsError(f"{row['club_id']}.{row['concept']}: {text} no es entero")
    return int(value)


def _convert(season: str, kind: str, currency: str, value_full: int, fiscal_year_end: str,
             rates: dict) -> dict:
    if kind == COUNT:
        return {"fx_method": fx.NOT_MONETARY, "fx_note": "número de acciones: no se convierte"}
    if currency == fx.BASE:
        return {"fx_rate": 1.0, "fx_method": fx.NO_CONVERSION, "value_eur": value_full,
                "fx_note": "la cifra ya está en EUR"}
    file, daily = rates[currency]
    start, end = fx.fiscal_year(season, fiscal_year_end)
    try:
        rate = (fx.average_rate(daily, currency, start, end) if kind == FLOW
                else fx.closing_rate(daily, currency, end))
    except fx.FxError as exc:
        raise FactsError(str(exc)) from exc
    return {"fx_rate": float(rate.rate), "fx_method": rate.method, "fx_date": rate.date,
            "value_eur": fx.to_eur(value_full, rate.rate), "fx_source_file": file,
            "fx_note": rate.note}


# ---------------------------------------------------------------- validación con pandera


def _mix_ok(frame: pd.DataFrame) -> pd.Series:
    """Por club: matchday + broadcasting + commercial + other = revenue_ex_player_trading, en la
    unidad del informe, con la tolerancia de redondeo de la sección 5 del plan (una fila por
    partida de ingresos de config/line_items.yaml). Si alguno de los cinco es hueco, no aplica."""
    ok = pd.Series(True, index=frame.index)
    clubs = mix.load()
    for (club_id, _season), rows in frame.groupby(["club_id", "season"]):
        values = rows.set_index("concept")["value_reported"]
        needed = [*mix.MIX, "revenue_ex_player_trading"]
        if any(concept not in values.index or pd.isna(values[concept]) for concept in needed):
            continue
        tolerance = max(1, clubs[club_id].lines // 2) if club_id in clubs else 1
        gap = sum(int(values[concept]) for concept in mix.MIX) - int(
            values["revenue_ex_player_trading"])
        if abs(gap) > tolerance:
            ok[rows.index] = False
    return ok


def _fx_method_ok(frame: pd.DataFrame) -> pd.Series:
    kinds = frame["concept"].map(KINDS)
    return frame["is_gap"] | pd.Series(
        [method in FX_METHODS.get(kind, set()) for method, kind in
         zip(frame["fx_method"], kinds, strict=True)], index=frame.index)


def _value_eur_ok(frame: pd.DataFrame) -> pd.Series:
    """value_eur es value_full / fx_rate redondeado al euro; vacío si no hay conversión."""
    result = []
    for row in frame.itertuples():
        if row.is_gap or row.fx_method == fx.NOT_MONETARY:
            result.append(pd.isna(row.value_eur) and pd.isna(row.fx_rate))
            continue
        rate = Decimal(str(float(row.fx_rate)))
        result.append(not pd.isna(row.value_eur)
                      and int(row.value_eur) == fx.to_eur(int(row.value_full), rate))
    return pd.Series(result, index=frame.index)


FACTS_SCHEMA = pa.DataFrameSchema(
    {
        "club_id": pa.Column(str),
        "season": pa.Column(str, pa.Check.str_matches(r"^\d{4}/\d{2}$")),
        "fiscal_year_end": pa.Column(str, pa.Check.str_matches(r"^\d{4}-\d{2}-\d{2}$")),
        "concept": pa.Column(str, pa.Check.isin(list(KINDS))),
        "label_original": pa.Column(str),
        "value_reported": pa.Column("Int64", nullable=True),
        "unit_reported": pa.Column(str, pa.Check.isin(list(MULTIPLIERS))),
        "currency_reported": pa.Column(str, pa.Check.isin(["", "EUR", "GBP"])),
        "value_full": pa.Column("Int64", nullable=True),
        "fx_rate": pa.Column(float, pa.Check.gt(0), nullable=True),
        "fx_method": pa.Column(str),
        "fx_date": pa.Column(str),
        "value_eur": pa.Column("Int64", nullable=True),
        "fx_source_file": pa.Column(str),
        "fx_note": pa.Column(str),
        "source_file": pa.Column(str, pa.Check.str_length(min_value=1)),
        "source_page": pa.Column("Int64", nullable=True),
        "source_url": pa.Column(str, pa.Check.str_startswith("http")),
        "retrieved_at": pa.Column(str, pa.Check.str_length(min_value=1)),
        "sha256": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{64}$")),
        "components": pa.Column(str),
        "column": pa.Column(str),
        "crop": pa.Column(str),
        "extraction_method": pa.Column(str),
        "ocr_note": pa.Column(str),
        "is_gap": pa.Column(bool),
        "gap_reason": pa.Column(str),
        "is_derived": pa.Column(bool),
        "included_in_staff_costs": pa.Column(str, pa.Check.isin(["", "true", "false",
                                                                  "dudoso"])),
        "definition_note": pa.Column(str),
    },
    checks=[
        pa.Check(lambda f: ~f.duplicated(["club_id", "season", "concept"]),
                 error="clave repetida: club_id, season y concept tienen que ser únicos"),
        pa.Check(lambda f: f["is_gap"] | (f["value_reported"].notna()
                                          & f["source_page"].notna()
                                          & (f["components"].str.len() > 0)),
                 error="una cifra tiene que llevar su valor y su fuente (página y componentes)"),
        pa.Check(lambda f: ~f["is_gap"] | (f["value_reported"].isna()
                                           & (f["gap_reason"].str.len() > 0)),
                 error="un hueco va sin valor y con su motivo"),
        pa.Check(lambda f: f["is_gap"] | (f["gap_reason"].str.len() == 0),
                 error="una cifra no lleva motivo de hueco"),
        pa.Check(_fx_method_ok, error="fx_method no corresponde al tipo de concepto"),
        pa.Check(_value_eur_ok, error="value_eur no es value_full / fx_rate redondeado al euro"),
        pa.Check(_mix_ok, error="matchday + broadcasting + commercial + other no cuadra con "
                                "revenue_ex_player_trading"),
    ],
    strict=True,
    ordered=True,
)


def validate(frame: pd.DataFrame) -> list[str]:
    """Los errores de la validación, legibles; vacío si pasa."""
    try:
        FACTS_SCHEMA.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        cases = exc.failure_cases
        problems = []
        for (column, check), group in cases.groupby(["column", "check"], dropna=False,
                                                     sort=False):
            where = []
            for index in group["index"].dropna().astype(int).unique()[:5]:
                row = frame.loc[index]
                where.append(f"{row['club_id']}.{row['concept']}")
            problems.append(f"{check if pd.notna(check) else column}"
                            + (f" (columna {column})" if pd.notna(column) else "")
                            + (f": {', '.join(where)}" if where else ""))
        return problems
    return []


def write(frame: pd.DataFrame, season: str, directory: Path = PROCESSED_DIR) -> list[Path]:
    """Parquet y tabla fact_financials de football.duckdb, escritos con DuckDB. En la base, las
    filas de la temporada se sustituyen y las de otras temporadas se conservan."""
    path = facts_path(season, directory)
    database = directory / DATABASE
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect() as con:
        con.register("facts", frame)
        con.execute(f"COPY (SELECT * FROM facts) TO '{path}' (FORMAT parquet)")
    replace_season(database, "fact_financials", frame, season)
    return [path, database]


def replace_season(database: Path, table: str, frame: pd.DataFrame, season: str) -> None:
    """Sustituye en la tabla las filas de la temporada; las de otras temporadas se conservan. Si
    las columnas de la tabla han cambiado y solo tiene esta temporada, se rehace; si tiene otras,
    es un error, para no perderlas."""
    with duckdb.connect(str(database)) as con:
        con.register("rows", frame)
        existing = [row[0] for row in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? "
            "ORDER BY ordinal_position", [table]).fetchall()]
        if existing and existing != list(frame.columns):
            others = con.execute(f"SELECT count(*) FROM {table} WHERE season <> ?",
                                 [season]).fetchone()[0]
            if others:
                raise FactsError(f"{database.name}: la tabla {table} tiene otras columnas y "
                                 f"{others} filas de otras temporadas; no se sustituye")
            con.execute(f"DROP TABLE {table}")
        con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM rows LIMIT 0")
        con.execute(f"DELETE FROM {table} WHERE season = ?", [season])
        con.execute(f"INSERT INTO {table} SELECT * FROM rows")


def replace_table(database: Path, table: str, frame: pd.DataFrame) -> None:
    """Sustituye la tabla entera (una que no va por temporadas, como transactions)."""
    with duckdb.connect(str(database)) as con:
        con.register("rows", frame)
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM rows")


def read_table(database: Path, table: str, season: str | None = None) -> pd.DataFrame:
    """Una tabla de football.duckdb, o sus filas de una temporada. Si no existe, FactsError."""
    if not database.exists():
        raise FactsError(f"falta {database.name}: ejecuta antes facts")
    with duckdb.connect(str(database), read_only=True) as con:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if table not in tables:
            raise FactsError(f"{database.name} no tiene la tabla {table}")
        if season is None:
            return con.execute(f"SELECT * FROM {table}").df()
        return con.execute(f"SELECT * FROM {table} WHERE season = ?", [season]).df()


def read(season: str, directory: Path = PROCESSED_DIR) -> pd.DataFrame:
    """fact_financials de una temporada, desde su parquet."""
    path = facts_path(season, directory)
    if not path.exists():
        raise FactsError(f"falta {path}: ejecuta antes facts")
    with duckdb.connect() as con:
        frame = con.execute(f"SELECT * FROM '{path}'").df()
    return frame.astype({"value_reported": "Int64", "value_full": "Int64", "value_eur": "Int64",
                         "source_page": "Int64", "is_gap": bool, "is_derived": bool})
