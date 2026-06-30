# ============================================================
# src/enrichment/prospects.py
# Carrega prospects da Receita Federal para a região de São Carlos.
# Filtra do banco mapa_clientes.prospects pelos municípios alvo.
# ============================================================

import logging
import pandas as pd
import psycopg2
from datetime import date

logger = logging.getLogger(__name__)

PG_MAPA = dict(
    host="192.168.0.242",
    port=5432,
    dbname="mapa_clientes",
    user="postgres",
    password="Postgres2025",
)

MUNICIPIOS_SC = (
    "SAO CARLOS", "ARARAQUARA", "IBATE", "ITIRAPINA",
    "SÃO CARLOS",  # variações com acento
)

CAPITAL_MINIMO        = 10_000
ANOS_MINIMO_ATIVIDADE = 1
DATA_LIMITE           = str(date.today().replace(year=date.today().year - ANOS_MINIMO_ATIVIDADE))


def carregar_prospects() -> pd.DataFrame:
    query = f"""
    SELECT
        cnpj,
        razao_social,
        nome_fantasia,
        cnae,
        descricao_cnae,
        logradouro,
        numero,
        bairro,
        municipio,
        uf,
        cep,
        capital_social,
        data_inicio_atividade,
        geo_refinada,
        lat_final,
        lng_final
    FROM prospects
    WHERE lat_final IS NOT NULL
      AND lng_final IS NOT NULL
      AND lat_final BETWEEN -22.6 AND -21.4
      AND lng_final BETWEEN -49.2 AND -47.4
      AND identificador_matriz_filial = '1'
      AND capital_social >= {CAPITAL_MINIMO}
      AND data_inicio_atividade <= '{DATA_LIMITE}'
      AND UPPER(municipio) = ANY(ARRAY{list(MUNICIPIOS_SC)!r})
    """

    conn = psycopg2.connect(**PG_MAPA)
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        logger.info(f"Prospects São Carlos: {len(df):,} com coordenada")
        return df
    except Exception as e:
        logger.warning(f"Não foi possível carregar prospects: {e}")
        return pd.DataFrame()
    finally:
        conn.close()