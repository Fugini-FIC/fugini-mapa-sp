# ============================================================
# src/enrichment/historico.py
# Enriquece clientes com faturamento NF do banco fugini_dw.
# Calcula dias_sem_compra e status_compra para colorização no mapa.
# ============================================================

import logging
import pandas as pd
import psycopg2
from datetime import date

logger = logging.getLogger(__name__)

PG_ERP = dict(
    host="192.168.0.242",
    port=5432,
    dbname="fugini_dw",
    user="postgres",
    password="Postgres2025",
)

# Limiar em dias para considerar cliente inativo
DIAS_INATIVO = 60


def carregar_historico() -> pd.DataFrame:
    query = """
    WITH resumo AS (
        SELECT
            cod_cliente,
            MAX(data_emissao)              AS ultima_compra,
            SUM(vl_bru_it)                 AS total_faturado,
            COUNT(DISTINCT nr_nota_fiscal) AS nr_notas
        FROM bronze.faturamento_nf
        GROUP BY cod_cliente
    ),
    ultimo_item AS (
        SELECT DISTINCT ON (f.cod_cliente)
            f.cod_cliente,
            f.cod_item   AS cod_ultimo_produto,
            f.qt_cxs_nf  AS ultima_qt_pedida
        FROM bronze.faturamento_nf f
        INNER JOIN resumo r
            ON f.cod_cliente   = r.cod_cliente
            AND f.data_emissao = r.ultima_compra
        ORDER BY f.cod_cliente, f.vl_bru_it DESC
    )
    SELECT
        r.cod_cliente,
        r.ultima_compra,
        r.total_faturado,
        r.nr_notas,
        TRIM(COALESCE(it.descricao_1, '') || COALESCE(it.descricao_2, '')) AS ultimo_produto,
        u.ultima_qt_pedida
    FROM resumo r
    LEFT JOIN ultimo_item u ON r.cod_cliente = u.cod_cliente
    LEFT JOIN bronze.item it ON u.cod_ultimo_produto = it.it_codigo
    """

    conn = psycopg2.connect(**PG_ERP)
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        logger.info(f"Faturamento NF carregado: {len(df):,} clientes.")
        return df
    except Exception as e:
        logger.warning(f"Não foi possível carregar faturamento NF: {e}")
        return pd.DataFrame(columns=[
            "cod_cliente", "ultima_compra", "total_faturado",
            "nr_notas", "ultimo_produto", "ultima_qt_pedida"
        ])
    finally:
        conn.close()


def calcular_status_compra(df: pd.DataFrame) -> pd.DataFrame:
    hoje = pd.Timestamp(date.today())

    df["ultima_compra"] = pd.to_datetime(df["ultima_compra"], errors="coerce")
    df["dias_sem_compra"] = (hoje - df["ultima_compra"]).dt.days

    def _status(row):
        if pd.isna(row["ultima_compra"]):
            return "nunca_comprou"
        if row["dias_sem_compra"] <= DIAS_INATIVO:
            return "ativo"
        return "inativo"

    df["status_compra"] = df.apply(_status, axis=1)

    ativos   = (df["status_compra"] == "ativo").sum()
    inativos = (df["status_compra"] == "inativo").sum()
    nunca    = (df["status_compra"] == "nunca_comprou").sum()
    logger.info(f"Status compra — ativos: {ativos} | inativos {DIAS_INATIVO}+d: {inativos} | nunca compraram: {nunca}")

    return df


def enriquecer_com_historico(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cod_cliente_int"] = pd.to_numeric(df["cod_cliente"], errors="coerce")

    historico = carregar_historico()

    if historico.empty:
        for col in ["ultima_compra", "total_faturado", "nr_notas",
                    "ultimo_produto", "ultima_qt_pedida"]:
            df[col] = None
    else:
        historico["cod_cliente"] = pd.to_numeric(historico["cod_cliente"], errors="coerce")
        df = df.merge(
            historico.rename(columns={"cod_cliente": "cod_cliente_int"}),
            on="cod_cliente_int",
            how="left",
        )

    com_historico = df["ultima_compra"].notna().sum() if "ultima_compra" in df.columns else 0
    sem_historico = len(df) - com_historico
    logger.info(f"Enriquecimento: {com_historico} com faturamento | {sem_historico} sem faturamento")

    if "tipo_cliente" in df.columns:
        mask_com_dono = df["tipo_cliente"] != "disponivel"

        df_com_dono = calcular_status_compra(df[mask_com_dono].copy())
        df_disp     = df[~mask_com_dono].copy()
        df_disp["status_compra"]   = "disponivel"
        df_disp["dias_sem_compra"] = None

        df = pd.concat([df_com_dono, df_disp], ignore_index=True)
    else:
        df = calcular_status_compra(df)

    df = df.drop(columns=["cod_cliente_int"], errors="ignore")
    return df