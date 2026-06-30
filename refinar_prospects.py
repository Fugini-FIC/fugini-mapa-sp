# ============================================================
# refinar_prospects.py
# Reprocessa coordenadas dos prospects via Google Maps API.
# Roda UMA VEZ — atualiza lat_final, lng_final, geo_refinada
# na tabela prospects do banco mapa_clientes.
#
# Uso:
#   python refinar_prospects.py
#   python refinar_prospects.py --dry-run  (só mostra quantos seriam processados)
# ============================================================

import sys
import time
import logging
import requests
import psycopg2
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("refinar_prospects.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
from config.settings import GOOGLE_API_KEY

PG_MAPA = dict(
    host="192.168.0.242",
    port=5432,
    dbname="mapa_clientes",
    user="postgres",
    password="Postgres2025",
)

MUNICIPIOS_SC = ['SAO CARLOS', 'ARARAQUARA', 'IBATE', 'ITIRAPINA', 'SÃO CARLOS']
CAPITAL_MINIMO        = 10_000
DATA_LIMITE           = '2024-06-16'
REGIAO_LAT_MIN, REGIAO_LAT_MAX = -22.6, -21.4
REGIAO_LNG_MIN, REGIAO_LNG_MAX = -49.2, -47.4
MAX_WORKERS           = 5
SLEEP_ENTRE_BATCHES   = 1.0
BATCH_SIZE            = 50

# ============================================================
# FUNÇÕES
# ============================================================

def carregar_prospects_para_refinar(conn) -> list:
    query = f"""
    SELECT cnpj, logradouro, numero, bairro, municipio, cep
    FROM prospects
    WHERE geo_refinada = FALSE
      AND lat_final IS NOT NULL
      AND lat_final BETWEEN {REGIAO_LAT_MIN} AND {REGIAO_LAT_MAX}
      AND lng_final BETWEEN {REGIAO_LNG_MIN} AND {REGIAO_LNG_MAX}
      AND identificador_matriz_filial = '1'
      AND capital_social >= {CAPITAL_MINIMO}
      AND data_inicio_atividade <= '{DATA_LIMITE}'
      AND UPPER(municipio) = ANY(ARRAY{MUNICIPIOS_SC!r})
    ORDER BY cnpj
    """
    with conn.cursor() as cur:
        cur.execute(query)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def montar_endereco(row: dict) -> str:
    partes = []
    if row.get('logradouro') and str(row['logradouro']).strip():
        partes.append(str(row['logradouro']).strip())
    if row.get('numero') and str(row['numero']).strip() not in ('', 'S/N', 'SN'):
        partes.append(str(row['numero']).strip())
    if row.get('bairro') and str(row['bairro']).strip():
        partes.append(str(row['bairro']).strip())
    if row.get('municipio') and str(row['municipio']).strip():
        partes.append(str(row['municipio']).strip())
    partes.append('SP, Brasil')
    return ', '.join(partes)


def geocodificar_google(endereco: str) -> tuple:
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": endereco,
        "key": GOOGLE_API_KEY,
        "region": "br",
        "language": "pt-BR"
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if data["status"] == "OK":
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"], "OK"
        elif data["status"] == "OVER_QUERY_LIMIT":
            time.sleep(2)
            return None, None, "OVER_QUERY_LIMIT"
        else:
            return None, None, data["status"]
    except Exception as e:
        return None, None, str(e)


def dentro_da_regiao(lat, lng) -> bool:
    try:
        return (REGIAO_LAT_MIN <= float(lat) <= REGIAO_LAT_MAX and
                REGIAO_LNG_MIN <= float(lng) <= REGIAO_LNG_MAX)
    except:
        return False


def processar_prospect(row: dict) -> dict:
    endereco = montar_endereco(row)
    lat, lng, status = geocodificar_google(endereco)
    valido = (status == "OK" and lat is not None and dentro_da_regiao(lat, lng))
    return {
        "cnpj":   row["cnpj"],
        "lat":    lat if valido else None,
        "lng":    lng if valido else None,
        "status": status,
        "valido": valido,
    }


def atualizar_banco(conn, resultados: list):
    ok      = [r for r in resultados if r["valido"]]
    nao_ok  = [r for r in resultados if not r["valido"]]

    with conn.cursor() as cur:
        # Atualiza lat_refined/lng_refined (lat_final é coluna gerada: COALESCE(lat_refined, lat_cep))
        for r in ok:
            cur.execute("""
                UPDATE prospects
                SET lat_refined = %s, lng_refined = %s, geo_refinada = TRUE
                WHERE cnpj = %s
            """, (r["lat"], r["lng"], r["cnpj"]))

        # Marca geo_refinada = TRUE mesmo para os sem resultado (evita reprocessar sempre)
        for r in nao_ok:
            cur.execute("""
                UPDATE prospects
                SET geo_refinada = TRUE
                WHERE cnpj = %s
            """, (r["cnpj"],))

    conn.commit()
    return len(ok), len(nao_ok)


# ============================================================
# MAIN
# ============================================================

def main():
    dry_run = "--dry-run" in sys.argv

    logger.info("=" * 60)
    logger.info("REFINAMENTO DE PROSPECTS — Google Maps API")
    logger.info("=" * 60)

    conn = psycopg2.connect(**PG_MAPA)
    try:
        prospects = carregar_prospects_para_refinar(conn)
        logger.info(f"Prospects para refinar: {len(prospects):,}")

        if dry_run:
            logger.info("DRY RUN — nenhuma alteração feita.")
            return

        if len(prospects) == 0:
            logger.info("Nenhum prospect para refinar. Encerrando.")
            return

        total      = len(prospects)
        total_ok   = 0
        total_nok  = 0
        inicio     = time.time()

        batches = [prospects[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

        for idx, batch in enumerate(batches):
            resultados = []

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(processar_prospect, row): row for row in batch}
                for future in as_completed(futures):
                    try:
                        resultados.append(future.result())
                    except Exception as e:
                        logger.warning(f"Erro: {e}")

            ok, nok = atualizar_banco(conn, resultados)
            total_ok  += ok
            total_nok += nok

            processados = (idx + 1) * BATCH_SIZE
            elapsed     = time.time() - inicio
            velocidade  = processados / elapsed if elapsed > 0 else 1
            eta         = (total - processados) / velocidade if velocidade > 0 else 0
            logger.info(f"  Batch {idx+1}/{len(batches)} | OK: {total_ok} | Sem resultado: {total_nok} | ETA: {eta/60:.1f}min")

            if idx < len(batches) - 1:
                time.sleep(SLEEP_ENTRE_BATCHES)

        logger.info("=" * 60)
        logger.info(f"CONCLUÍDO — {total_ok} refinados | {total_nok} sem resultado")
        logger.info("=" * 60)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
