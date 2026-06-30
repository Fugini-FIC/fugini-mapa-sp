# ============================================================
# pipeline.py
# Projeto 19 — Mapa de Clientes São Carlos e Região
#
# Uso:
#   python pipeline.py              → completo com criptografia e publicação
#   python pipeline.py --no-crypt  → sem criptografia (teste local)
#   python pipeline.py --no-publish → sem publicar no GitHub
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
from src.mapping.builder          import exportar_mapas
from src.publishing.github_pages  import publicar


def run(criptografar: bool = True, publicar_github: bool = True):
    logger.info("=" * 60)
    logger.info("PIPELINE INICIADO — São Carlos e Região")
    logger.info("=" * 60)

    # 1. Carrega clientes do TOTVS
    logger.info("\n[1/5] Carregando clientes do TOTVS...")
    df = carregar_clientes()

    # 2. Geocodificação
    logger.info("\n[2/5] Geocodificando clientes...")
    df = geocodificar(df)

    # 3. Enriquecimento com faturamento NF
    logger.info("\n[3/5] Enriquecendo com histórico de faturamento...")
    df = enriquecer_com_historico(df)

    # 4. Carrega prospects
    logger.info("\n[4/5] Carregando prospects da Receita Federal...")
    df_prospects = carregar_prospects()

    # 5. Geração dos mapas
    logger.info(f"\n[5/5] Gerando HTMLs (criptografar={criptografar})...")
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
