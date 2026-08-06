# ============================================================
# pipeline.py
# Projeto 23 — Mapa de Clientes São Paulo e Região
#
# Uso:
#   python pipeline.py              -> completo com criptografia e publicacao
#   python pipeline.py --no-crypt   -> sem criptografia (teste local)
#   python pipeline.py --no-publish -> sem publicar no GitHub
#
# ATUALIZADO: prospects religados. Só mostra prospects com
# geo_refinada=TRUE (ver prospects.py) — hoje isso é o subconjunto
# priorizado por rating da SISP (602 registros, rating A). O restante
# dos ~28 mil prospects segue sem coordenada confiável e fora do mapa
# até serem refinados em lotes futuros (ver refinar_prospects_sp.py).
# ============================================================

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from src.ingestion.loader         import carregar_clientes
from src.geocoding.geocoder       import geocodificar
from src.enrichment.historico     import enriquecer_com_historico
from src.enrichment.prospects     import carregar_prospects
from src.enrichment.prospect_ownership import atribuir_prospects_por_territorio
from src.mapping.builder          import exportar_mapas
from src.publishing.github_pages  import publicar


def run(criptografar: bool = True, publicar_github: bool = True):
    logger.info("=" * 60)
    logger.info("PIPELINE INICIADO — São Paulo e Região")
    logger.info("=" * 60)

    # 1. Carrega carteira do TOTVS (por cod-erc)
    logger.info("\n[1/6] Carregando carteira (TOTVS por cod-erc)...")
    df = carregar_clientes()

    # 2. Geocodificação dos sem coordenada TOTVS
    logger.info("\n[2/6] Geocodificando clientes sem coordenada...")
    df = geocodificar(df)

    # 3. Enriquecimento com faturamento NF (status ativo/inativo/nunca_comprou)
    logger.info("\n[3/6] Enriquecendo com histórico de faturamento...")
    df = enriquecer_com_historico(df)

    # 4. Carrega prospects refinados (só geo_refinada=TRUE)
    logger.info("\n[4/6] Carregando prospects refinados...")
    df_prospects = carregar_prospects()

    # 5. Atribui cada prospect ao vendedor territorialmente mais próximo
    # (recalculado sempre — se a carteira mudar, a atribuição se ajusta)
    logger.info("\n[5/6] Atribuindo prospects por território...")
    df_prospects = atribuir_prospects_por_territorio(df, df_prospects)

    # 6. Geração dos mapas
    logger.info(f"\n[6/6] Gerando HTMLs (criptografar={criptografar})...")
    arquivos = exportar_mapas(df, criptografar=criptografar, df_prospects=df_prospects)

    if publicar_github:
        logger.info("\nPublicando no GitHub Pages...")
        url = publicar()
        logger.info(f"🌐 {url}")
    else:
        logger.info("\nPublicação pulada (--no-publish).")
        url = None

    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE CONCLUÍDO")
    logger.info("=" * 60)

    return df, arquivos, url


if __name__ == "__main__":
    criptografar    = "--no-crypt"    not in sys.argv
    publicar_github = "--no-publish"  not in sys.argv
    run(criptografar=criptografar, publicar_github=publicar_github)
