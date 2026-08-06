# ============================================================
# src/publishing/github_pages.py
# Publica os HTMLs no GitHub Pages via git push direto.
# ============================================================

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from config.settings import GITHUB_TOKEN, GITHUB_REPO, USUARIOS_MAPA

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/output")

# Fonte dos HTMLs ESTÁTICOS — os que não são gerados pelo exportar_mapas().
# `data/output/` está no .gitignore (é saída de build), então um arquivo
# estático morando lá não tem histórico: some se a máquina for trocada e só
# pode ser editado por remendo. Por isso o checkin.html passou a morar aqui,
# versionado, e daqui é publicado.
#
# ⚠️ Até esta mudança este repo NÃO tinha o checkin.html localmente, então o
# pipeline pulava esse arquivo com warning e quem publicava o formulário de SP
# era um commit manual na gh-pages. Agora o pipeline publica de verdade — o
# conteúdo é o mesmo de São Carlos (blob idêntico), mantido em sincronia à mão
# entre os dois repos enquanto a duplicação 19/23 não for resolvida.
WEB_DIR   = Path("src/web")
ESTATICOS = ["checkin.html"]

# Lista dos mapas derivada de USUARIOS_MAPA (settings.py) em vez de hardcoded —
# cobre os 5 HTMLs de SP (master_sp + 4 vendedores) automaticamente.
ARQUIVOS = [dados["arquivo"] for dados in USUARIOS_MAPA.values()] + ESTATICOS


def _origem(nome: str) -> Path:
    """De onde sai cada arquivo: estático = fonte versionada, resto = build."""
    return (WEB_DIR if nome in ESTATICOS else OUTPUT_DIR) / nome


def publicar(apenas: list[str] | None = None) -> str:
    """Publica os HTMLs na gh-pages.

    `apenas` limita a publicação a alguns arquivos — usado pelo
    publicar_checkin.py para subir só o formulário, sem rodar o pipeline
    inteiro por causa de uma mudança de HTML. O clone é da gh-pages e só os
    arquivos listados são sobrescritos, então os mapas não são tocados.
    """
    arquivos = apenas if apenas else ARQUIVOS
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
        for nome in arquivos:
            src = _origem(nome)
            if not src.exists():
                logger.warning(f"  Arquivo não encontrado: {src}")
                continue
            shutil.copy2(src, tmp / nome)
            logger.info(f"  Copiado: {nome} ({src.stat().st_size / 1024:.1f} KB)")

        # Commit e push
        subprocess.run(["git", "config", "user.email", "fuginific@gmail.com"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.name",  "Fugini Pipeline"],     cwd=tmp, check=True)
        subprocess.run(["git", "add", "."],                                     cwd=tmp, check=True)

        # Só commita e faz push se houver mudanças
        status = subprocess.run(["git", "status", "--porcelain"], cwd=tmp, capture_output=True, text=True)
        if status.stdout.strip():
            subprocess.run(["git", "commit", "-m", "update: mapas São Paulo"], cwd=tmp, check=True)
            result = subprocess.run(
                ["git", "push", "origin", "gh-pages"],
                cwd=tmp, capture_output=True, text=True
            )
            if result.returncode != 0:
                logger.error(f"Push falhou:\n{result.stderr}")
                raise RuntimeError(f"git push falhou: {result.stderr}")
        else:
            logger.info("  Sem alterações — nada a publicar.")

    # URL derivada de GITHUB_REPO em vez de hardcoded
    repo_nome = GITHUB_REPO.split("/")[-1]
    url = f"https://fugini-fic.github.io/{repo_nome}/"
    logger.info(f"\n🌐 Publicado em: {url}")
    return url
