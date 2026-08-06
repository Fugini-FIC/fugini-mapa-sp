# ============================================================
# src/geocoding/geocoder.py
# Geocodifica clientes via Google Maps API.
# Checkpoint salvo no PostgreSQL — nunca reprocessa o que já foi.
# Reutiliza a tabela geocodificacao_checkpoint do banco mapa_clientes.
# ============================================================

import logging
import time
import requests
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.settings import (
    GOOGLE_API_KEY,
    GEOCODING_BATCH_SIZE,
    GEOCODING_MAX_WORKERS,
    GEOCODING_SLEEP_BETWEEN_BATCHES,
    GEO_LAT_MIN, GEO_LAT_MAX,
    GEO_LNG_MIN, GEO_LNG_MAX,
)
from src.database.connection import get_connection

logger = logging.getLogger(__name__)

# Bounding box da Grande São Paulo (RMSP)
# Clientes com coordenada TOTVS fora dessa area sao tratados como invalidos
# e regeocidificados pelo Google Maps API
# Margem de seguranca para nao cortar cliente de borda dos municipios validados
# (cobre de Vargem Grande Paulista/oeste ate Suzano-Mogi/leste,
#  Mairipora/norte ate Sao Lourenco da Serra/sul)
REGIAO_LAT_MIN = -24.3
REGIAO_LAT_MAX = -22.9
REGIAO_LNG_MIN = -47.3
REGIAO_LNG_MAX = -45.8


def coordenada_valida(lat, lng) -> bool:
    try:
        lat, lng = float(lat), float(lng)
        return (
            pd.notna(lat) and pd.notna(lng)
            and lat != 0 and lng != 0
            and GEO_LAT_MIN <= lat <= GEO_LAT_MAX
            and GEO_LNG_MIN <= lng <= GEO_LNG_MAX
        )
    except (TypeError, ValueError):
        return False


def coordenada_na_regiao(lat, lng) -> bool:
    """Verifica se a coordenada está dentro do bounding box da região de São Paulo."""
    try:
        lat, lng = float(lat), float(lng)
        return (
            REGIAO_LAT_MIN <= lat <= REGIAO_LAT_MAX
            and REGIAO_LNG_MIN <= lng <= REGIAO_LNG_MAX
        )
    except (TypeError, ValueError):
        return False


def montar_endereco(row: dict) -> tuple:
    endereco = row.get("endereco")
    bairro   = row.get("bairro")
    cep      = row.get("cep")
    cod_ibge = row.get("cod_ibge")

    cep_limpo = None
    if pd.notna(cep) and str(cep).strip():
        c = str(cep).replace(".", "").replace("-", "").strip()
        if len(c) == 8:
            cep_limpo = f"{c[:5]}-{c[5:]}"

    def tem(val):
        return pd.notna(val) and str(val).strip() != ""

    if tem(endereco) and cep_limpo:
        partes = [str(endereco).strip()]
        if tem(bairro): partes.append(str(bairro).strip())
        partes += [cep_limpo, "Brasil"]
        return ", ".join(partes), 1
    elif cep_limpo:
        return f"{cep_limpo}, Brasil", 2
    elif tem(endereco):
        partes = [str(endereco).strip()]
        if tem(bairro): partes.append(str(bairro).strip())
        partes.append("Brasil")
        return ", ".join(partes), 3

    return None, None


def geocodificar_google(endereco: str) -> tuple:
    if not endereco or not endereco.strip():
        return None, None, "endereco_vazio", "SKIP"

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": endereco, "key": GOOGLE_API_KEY, "region": "br", "language": "pt-BR"}

    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if data["status"] == "OK":
            result   = data["results"][0]
            location = result["geometry"]["location"]
            tipo     = result["geometry"]["location_type"]
            return location["lat"], location["lng"], tipo, "OK"
        elif data["status"] == "ZERO_RESULTS":
            return None, None, "nao_encontrado", "ZERO_RESULTS"
        elif data["status"] == "OVER_QUERY_LIMIT":
            time.sleep(1)
            return None, None, "limite_excedido", "OVER_QUERY_LIMIT"
        else:
            return None, None, "erro", data["status"]
    except Exception as e:
        return None, None, "exception", str(e)


def carregar_checkpoint() -> set:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cod_cliente FROM geocodificacao_checkpoint")
            return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def salvar_checkpoint(resultados: list):
    if not resultados:
        return
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO geocodificacao_checkpoint
                        (cod_cliente, lat_google, lng_google, tipo_localizacao, status, valido, nivel)
                    VALUES (%(cod_cliente)s, %(lat_google)s, %(lng_google)s,
                            %(tipo_localizacao)s, %(status)s, %(valido)s, %(nivel)s)
                    ON CONFLICT (cod_cliente) DO NOTHING
                    """,
                    resultados,
                )
    finally:
        conn.close()


def carregar_resultados_checkpoint() -> pd.DataFrame:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cod_cliente, lat_google, lng_google, valido FROM geocodificacao_checkpoint"
            )
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(rows, columns=cols)
    finally:
        conn.close()


def processar_cliente(row: dict) -> dict:
    endereco_montado, nivel = montar_endereco(row)
    if endereco_montado:
        lat, lng, tipo, status = geocodificar_google(endereco_montado)
        valido = status == "OK" and lat is not None and coordenada_valida(lat, lng)
    else:
        lat, lng, tipo, status, valido, nivel = None, None, "sem_dados", "SKIP", False, None

    return {
        "cod_cliente":      str(row["cod_cliente"]),
        "lat_google":       lat,
        "lng_google":       lng,
        "tipo_localizacao": tipo,
        "status":           status,
        "valido":           valido,
        "nivel":            nivel,
    }


def geocodificar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Valida coordenadas do TOTVS — só aceita se estiver na região de São Paulo
    df["geo_valida_totvs"] = df.apply(
        lambda r: coordenada_valida(r.get("lat_totvs"), r.get("lng_totvs"))
                  and coordenada_na_regiao(r.get("lat_totvs"), r.get("lng_totvs")),
        axis=1
    )

    n_totvs   = df["geo_valida_totvs"].sum()
    n_sem_geo = (~df["geo_valida_totvs"]).sum()
    logger.info(f"Coordenada TOTVS válida na região: {n_totvs:,} | Precisam geocodificar: {n_sem_geo:,}")

    ja_processados = carregar_checkpoint()
    df_sem_geo     = df[~df["geo_valida_totvs"]].copy()
    df_a_processar = df_sem_geo[~df_sem_geo["cod_cliente"].astype(str).isin(ja_processados)]

    logger.info(f"Já no checkpoint: {len(ja_processados):,} | Novos para API: {len(df_a_processar):,}")

    if len(df_a_processar) > 0:
        total         = len(df_a_processar)
        total_batches = (total + GEOCODING_BATCH_SIZE - 1) // GEOCODING_BATCH_SIZE
        inicio        = time.time()
        novos         = 0

        for i in range(total_batches):
            batch = df_a_processar.iloc[i * GEOCODING_BATCH_SIZE:(i + 1) * GEOCODING_BATCH_SIZE]
            rows  = batch.to_dict("records")
            resultados = []

            with ThreadPoolExecutor(max_workers=GEOCODING_MAX_WORKERS) as executor:
                futures = {executor.submit(processar_cliente, row): row for row in rows}
                for future in as_completed(futures):
                    try:
                        resultados.append(future.result())
                    except Exception as e:
                        logger.warning(f"Erro em cliente: {e}")

            salvar_checkpoint(resultados)
            novos += len(resultados)

            elapsed   = time.time() - inicio
            velocidade = novos / elapsed if elapsed > 0 else 1
            eta        = (total - novos) / velocidade if velocidade > 0 else 0
            logger.info(f"  Progresso: {novos}/{total} | ETA: {eta/60:.1f}min")

            if i < total_batches - 1:
                time.sleep(GEOCODING_SLEEP_BETWEEN_BATCHES)

    df_checkpoint = carregar_resultados_checkpoint()
    df = df.merge(
        df_checkpoint[["cod_cliente", "lat_google", "lng_google", "valido"]],
        on="cod_cliente", how="left",
    )

    df["lat_final"] = np.where(
        df["geo_valida_totvs"],
        pd.to_numeric(df["lat_totvs"], errors="coerce"),
        pd.to_numeric(df["lat_google"], errors="coerce"),
    )
    df["lng_final"] = np.where(
        df["geo_valida_totvs"],
        pd.to_numeric(df["lng_totvs"], errors="coerce"),
        pd.to_numeric(df["lng_google"], errors="coerce"),
    )
    df["geo_valida_final"] = df["geo_valida_totvs"] | (df["valido"] == True)

    # Remove clientes com coordenada final fora da região
    fora = df["geo_valida_final"] & ~df.apply(
        lambda r: coordenada_na_regiao(r.get("lat_final"), r.get("lng_final")),
        axis=1
    )
    if fora.sum() > 0:
        logger.warning(
            f"Removidos {fora.sum()} clientes com coordenada fora da região: "
            f"{df[fora]['cod_cliente'].tolist()}"
        )
        df.loc[fora, ["lat_final", "lng_final", "geo_valida_final"]] = [None, None, False]

    cobertura = df["geo_valida_final"].sum()
    logger.info(f"Cobertura final: {cobertura:,}/{len(df):,} ({cobertura/len(df)*100:.1f}%)")

    return df
