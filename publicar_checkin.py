# ============================================================
# publicar_checkin.py
# Publica APENAS o formulário de check-in (src/web/checkin.html) na
# gh-pages, sem rodar o pipeline inteiro.
#
# Por que existe: o checkin.html é estático (não é gerado pelo pipeline),
# mas era publicado só junto com os mapas. Isso obrigava a rodar
# geocodificação + DW + geração de ~3 MB de HTML só para corrigir um campo
# do formulário — e, na prática, levava a commitar direto na gh-pages, que
# é a branch de publicação. Este script torna a via correta a mais fácil.
#
# Uso:
#   python publicar_checkin.py --dry-run   # mostra o que mudaria
#   python publicar_checkin.py             # publica
#
# ⚠️ ORDEM DE DEPLOY. O formulário é servido pelo GitHub Pages e pode estar
# em cache no celular do vendedor. Se uma validação for apertada na API do
# CRM (pages/api/checkin.ts) ANTES do formulário novo circular, o payload
# antigo passa a ser recusado e o check-in falha em campo. Publique o
# formulário primeiro, confirme que está no ar, e só então aperte a API.
# ============================================================

import argparse
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import GITHUB_TOKEN, GITHUB_REPO
from src.publishing.github_pages import publicar, WEB_DIR

ARQUIVO = "checkin.html"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def diferenca_para_publicado() -> bool:
    """Compara a fonte local com o que está na gh-pages. True se difere."""
    local = WEB_DIR / ARQUIVO
    if not local.exists():
        logger.error(f"[ERRO] Fonte não encontrada: {local}")
        return False

    hash_local = subprocess.run(
        ["git", "hash-object", "--no-filters", str(local)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            ["git", "clone", "--branch", "gh-pages", "--single-branch", "--depth", "1",
             f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git", tmpdir],
            check=True, capture_output=True,
        )
        publicado = subprocess.run(
            ["git", "rev-parse", f"HEAD:{ARQUIVO}"],
            cwd=tmpdir, capture_output=True, text=True,
        )
        hash_remoto = publicado.stdout.strip() if publicado.returncode == 0 else "(nao existe)"

    logger.info(f"  fonte local     : {hash_local}")
    logger.info(f"  publicado       : {hash_remoto}")
    if hash_local == hash_remoto:
        logger.info("  -> IDENTICOS, nada a publicar.")
        return False
    logger.info("  -> DIFEREM, ha o que publicar.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Publica só o checkin.html na gh-pages (sem rodar o pipeline)."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Só compara a fonte com o publicado, sem enviar.")
    args = parser.parse_args()

    logger.info(f"Comparando {WEB_DIR / ARQUIVO} com o publicado em {GITHUB_REPO}...")
    difere = diferenca_para_publicado()

    if args.dry_run:
        logger.info("\n--dry-run: nada foi publicado.")
        return

    if not difere:
        logger.info("\nNada a fazer.")
        return

    url = publicar(apenas=[ARQUIVO])
    logger.info(f"\n[OK] Formulario publicado. Confirme no ar antes de apertar a API: {url}{ARQUIVO}")


if __name__ == "__main__":
    main()
