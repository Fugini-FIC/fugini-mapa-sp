# ============================================================
# src/enrichment/prospect_ownership.py
# Atribui cada prospect ao vendedor cujo território (centro
# geográfico da carteira ATUAL dele) está mais próximo.
#
# Recalculado a cada execução do pipeline — não depende de endereço
# de vendedor hardcoded em lugar nenhum. Se a carteira mudar (ex:
# redistribuição feita pelo admin no TOTVS), a atribuição de
# prospect se ajusta sozinha na próxima rodada.
#
# Sem restrição de capacidade: não há necessidade de "cota justa"
# de prospects por vendedor — é simplesmente "o mais perto fica com
# aquele", evitando que dois vendedores prospectem a mesma empresa
# sem saber.
# ============================================================

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _projetar_local(lat: np.ndarray, lng: np.ndarray, lat_media_rad: float) -> np.ndarray:
    R = 6371.0
    x = np.radians(lng) * np.cos(lat_media_rad) * R
    y = np.radians(lat) * R
    return np.column_stack([x, y])


def atribuir_prospects_por_territorio(df_clientes: pd.DataFrame, df_prospects: pd.DataFrame) -> pd.DataFrame:
    """
    df_clientes precisa ter: cod_vendedor, lat_final, lng_final
    df_prospects precisa ter: lat_final, lng_final

    Retorna df_prospects com uma coluna nova 'cod_vendedor' —
    o dono territorial de cada prospect.
    """
    if df_prospects.empty:
        df_prospects = df_prospects.copy()
        df_prospects["cod_vendedor"] = None
        return df_prospects

    # Colunas numeric do Postgres vêm como decimal.Decimal via psycopg2,
    # não float — precisa converter explicitamente antes de qualquer
    # operação numpy, senão dá TypeError ao misturar com float puro.
    df_prospects = df_prospects.copy()
    df_prospects["lat_final"] = pd.to_numeric(df_prospects["lat_final"], errors="coerce")
    df_prospects["lng_final"] = pd.to_numeric(df_prospects["lng_final"], errors="coerce")

    df_clientes_validos = df_clientes.dropna(subset=["lat_final", "lng_final"]).copy()
    df_clientes_validos["lat_final"] = pd.to_numeric(df_clientes_validos["lat_final"], errors="coerce")
    df_clientes_validos["lng_final"] = pd.to_numeric(df_clientes_validos["lng_final"], errors="coerce")
    if df_clientes_validos.empty:
        logger.warning("  Sem clientes com coordenada válida — não é possível calcular território. "
                        "Prospects ficarão sem cod_vendedor atribuído.")
        df_prospects = df_prospects.copy()
        df_prospects["cod_vendedor"] = None
        return df_prospects

    # Centro geográfico da carteira atual de cada vendedor
    centroides = df_clientes_validos.groupby("cod_vendedor")[["lat_final", "lng_final"]].mean()
    vendedores = centroides.index.tolist()

    if len(vendedores) == 0:
        df_prospects = df_prospects.copy()
        df_prospects["cod_vendedor"] = None
        return df_prospects

    # Projeção local para distância mais precisa (mesma técnica usada
    # na ferramenta de redistribuição de carteira)
    todas_lat = np.concatenate([
        df_clientes_validos["lat_final"].values,
        df_prospects["lat_final"].dropna().values,
    ])
    lat_media_rad = np.radians(todas_lat.mean())

    centroides_xy = _projetar_local(
        centroides["lat_final"].values, centroides["lng_final"].values, lat_media_rad
    )

    df_prospects = df_prospects.copy()
    tem_coord = df_prospects["lat_final"].notna() & df_prospects["lng_final"].notna()

    prospects_xy = _projetar_local(
        df_prospects.loc[tem_coord, "lat_final"].values,
        df_prospects.loc[tem_coord, "lng_final"].values,
        lat_media_rad,
    )

    # Distância de cada prospect a cada centroide de vendedor -> pega o mais perto
    dist_matrix = np.linalg.norm(prospects_xy[:, None, :] - centroides_xy[None, :, :], axis=2)
    indices_mais_perto = np.argmin(dist_matrix, axis=1)

    df_prospects["cod_vendedor"] = None
    df_prospects.loc[tem_coord, "cod_vendedor"] = [vendedores[i] for i in indices_mais_perto]

    logger.info(f"  Prospects atribuídos por território:")
    for v, n in df_prospects["cod_vendedor"].value_counts().sort_index().items():
        logger.info(f"    {v}: {n}")

    sem_atribuicao = df_prospects["cod_vendedor"].isna().sum()
    if sem_atribuicao > 0:
        logger.warning(f"  {sem_atribuicao} prospects sem coordenada — ficaram sem vendedor atribuído.")

    return df_prospects