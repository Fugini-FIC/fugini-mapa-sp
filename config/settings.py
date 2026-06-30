# ============================================================
# config/settings.py
# Configurações centralizadas do Projeto 19 — Mapa São Carlos
# ============================================================

import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env", override=False)

# ============================================================
# GOOGLE MAPS
# ============================================================
GOOGLE_API_KEY          = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MAPS_FRONTEND_KEY = os.getenv("GOOGLE_MAPS_FRONTEND_KEY", "")

# ============================================================
# POSTGRESQL — banco mapa_clientes
# ============================================================
PG_HOST     = os.getenv("PG_HOST",     "192.168.0.242")
PG_PORT     = int(os.getenv("PG_PORT", "5432"))
PG_DBNAME   = os.getenv("PG_DBNAME",   "mapa_clientes")
PG_USER     = os.getenv("PG_USER",     "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "Postgres2025")

# ============================================================
# GITHUB
# ============================================================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO  = os.getenv("GITHUB_REPO", "Fugini-FIC/fugini-mapa-sc")

# ============================================================
# REGIÃO — São Carlos e entorno
# ============================================================
IBGE_ALVO = [
    3548906,  # São Carlos
    3503208,  # Araraquara
    3519055,  # Ibaté
    3523404,  # Itirapina
]

IBGE_CIDADE = {
    3548906: "São Carlos",
    3503208: "Araraquara",
    3519055: "Ibaté",
    3523404: "Itirapina",
}

NOME_REGIAO = "São Carlos e Região"

# ============================================================
# FONTE DE DADOS — CSV do TOTVS
# ============================================================
TOTVS_CLIENTE_CSV = r"\\192.168.0.226\pdi\in\full\totvs_cliente.csv"

# ============================================================
# USUÁRIOS DO MAPA
# ============================================================
USUARIOS_MAPA = {
    "master_sc":   {"senha": "fugini@master_sc", "arquivo": "master_sc.html"},
    "vendedor_sc": {"senha": "fugini@sc1",        "arquivo": "vendedor_sc.html"},
}

# ============================================================
# COR DO MAPA — área única
# ============================================================
COR_AREA = {
    "marker": "#e74c3c",
    "fill":   "#e74c3c",
}

# ============================================================
# GEOCODIFICAÇÃO
# ============================================================
GEOCODING_BATCH_SIZE              = 50
GEOCODING_MAX_WORKERS             = 5
GEOCODING_SLEEP_BETWEEN_BATCHES   = 1.0

# Bounding box do Brasil
GEO_LAT_MIN = -33.75
GEO_LAT_MAX =  5.27
GEO_LNG_MIN = -73.99
GEO_LNG_MAX = -28.84