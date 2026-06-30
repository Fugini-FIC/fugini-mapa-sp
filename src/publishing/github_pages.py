# ============================================================
# src/publishing/github_pages.py
# Publica os HTMLs no GitHub Pages via git push direto.
# ============================================================

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from config.settings import GITHUB_TOKEN, GITHUB_REPO

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/output")
ARQUIVOS   = ["master_sc.html", "vendedor_sc.html", "checkin.html"]


def publicar() -> str:
    logger.info(f"Publicando via git push: {GITHUB_REPO}")

    repo_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Clona só o branch gh-pages (shallow)
        subprocess.run(
            ["git", "clone", "--branch", "gh-pages", "--single-branch", "--depth", "1", repo_url, str(tmp)],
            check=True, capture_output=True
        )

        # Copia os HTMLs para o clone
        for nome in ARQUIVOS:
            src = OUTPUT_DIR / nome
            if not src.exists():
                logger.warning(f"  Arquivo não encontrado: {nome}")
                continue
            shutil.copy2(src, tmp / nome)
            logger.info(f"  Copiado: {nome} ({src.stat().st_size / 1024:.1f} KB)")

        # Commit e push
        subprocess.run(["git", "config", "user.email", "pipeline@fugini.com.br"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.name",  "Fugini Pipeline"],         cwd=tmp, check=True)
        subprocess.run(["git", "add", "."],                                         cwd=tmp, check=True)

        # Só commita e faz push se houver mudanças
        status = subprocess.run(["git", "status", "--porcelain"], cwd=tmp, capture_output=True, text=True)
        if status.stdout.strip():
            subprocess.run(["git", "commit", "-m", "update: mapas São Carlos"], cwd=tmp, check=True)
            result = subprocess.run(
                ["git", "push", "origin", "gh-pages"],
                cwd=tmp, capture_output=True, text=True
            )
            if result.returncode != 0:
                logger.error(f"Push falhou:\n{result.stderr}")
                raise RuntimeError(f"git push falhou: {result.stderr}")
        else:
            logger.info("  Sem alterações — nada a publicar.")

    url = f"https://fugini-fic.github.io/fugini-mapa-sc/"
    logger.info(f"\n🌐 Publicado em: {url}")
    return url