# ============================================================
# src/enrichment/prospects.py
# Carrega prospects da Receita Federal para a região de São Paulo.
# Filtra do banco mapa_clientes.prospects pelos municípios alvo.
#
# ATUALIZADO: agora exige geo_refinada = TRUE. Só mostra prospects
# cuja coordenada já passou pelo refinamento via Google API
# (refinar_prospects_sp.py) — evita plotar os que só têm coordenada
# bruta de CEP via Nominatim (sabidamente imprecisa). Hoje isso
# significa mostrar só o subconjunto priorizado (rating A da SISP,
# 602 registros) até mais lotes serem refinados no futuro.
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

# Municípios da Grande São Paulo cobertos pela carteira (mesma lista
# validada via API do IBGE usada em config/settings.py IBGE_CIDADE).
MUNICIPIOS_SP = (
    "SAO PAULO", "GUARULHOS", "OSASCO", "SAO BERNARDO DO CAMPO",
    "SANTO ANDRE", "MOGI DAS CRUZES", "MAUA", "SAO CAETANO DO SUL",
    "BARUERI", "COTIA", "ITAPEVI", "ITAQUAQUECETUBA", "SUZANO",
    "CARAPICUIBA", "ITAPECERICA DA SERRA", "DIADEMA", "POA",
    "RIBEIRAO PIRES", "JANDIRA", "FRANCO DA ROCHA", "TABOAO DA SERRA",
    "CAJAMAR", "SANTANA DE PARNAIBA", "FERRAZ DE VASCONCELOS",
    "EMBU DAS ARTES", "VARGEM GRANDE PAULISTA", "ARUJA", "EMBU-GUACU",
    "RIO GRANDE DA SERRA", "SAO LOURENCO DA SERRA",
)

# Bounding box da Grande São Paulo — mesmo usado em geocoder.py
REGIAO_LAT_MIN = -24.3
REGIAO_LAT_MAX = -22.9
REGIAO_LNG_MIN = -47.3
REGIAO_LNG_MAX = -45.8

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
      AND lat_final BETWEEN {REGIAO_LAT_MIN} AND {REGIAO_LAT_MAX}
      AND lng_final BETWEEN {REGIAO_LNG_MIN} AND {REGIAO_LNG_MAX}
      AND identificador_matriz_filial = '1'
      AND capital_social >= {CAPITAL_MINIMO}
      AND data_inicio_atividade <= '{DATA_LIMITE}'
      AND geo_refinada = TRUE
      AND UPPER(municipio) = ANY(ARRAY{list(MUNICIPIOS_SP)!r})
    """

    conn = psycopg2.connect(**PG_MAPA)
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        logger.info(f"Prospects São Paulo (refinados): {len(df):,} com coordenada validada")
        return df
    except Exception as e:
        logger.warning(f"Não foi possível carregar prospects: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
