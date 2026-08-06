    # ============================================================
# config/settings.py
# Configurações centralizadas do Projeto 23 — Mapa São Paulo
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
GITHUB_REPO  = os.getenv("GITHUB_REPO", "Fugini-FIC/fugini-mapa-sp")

# ============================================================
# CRM
# ============================================================
# URL do CRM (Next.js na Vercel). Usada nos popups para levar o vendedor
# a agenda com o cliente ja preenchido. O mapa NAO chama a API de
# agendamentos direto: quem cria a visita e o CRM, atras do login.
CRM_BASE_URL = os.getenv("CRM_BASE_URL", "https://fugini-checkin-api.vercel.app")

# ============================================================
# REGIÃO — São Paulo e Grande São Paulo
# Lista validada via API do IBGE a partir dos cod-ibge reais
# encontrados na carteira (CARTEIRA_VD_SP.xlsx). Cobre os 30
# municípios com clientes na carteira atual. Se novos municípios
# aparecerem em atualizações futuras do Excel, vão cair como
# "Desconhecida" no popup — não bloqueia o pipeline, só cosmético.
# ============================================================
IBGE_ALVO = [
    3550308, 3518800, 3534401, 3548708, 3530607, 3529401, 3547809,
    3548807, 3505708, 3513009, 3522505, 3523107, 3552502, 3510609,
    3522208, 3513801, 3539806, 3543303, 3525003, 3516408, 3552809,
    3509205, 3547304, 3515707, 3515004, 3556453, 3503901, 3515103,
    3544103, 3549953,
]

IBGE_CIDADE = {
    3550308: "São Paulo",
    3518800: "Guarulhos",
    3534401: "Osasco",
    3548708: "São Bernardo do Campo",
    3530607: "Mogi das Cruzes",
    3529401: "Mauá",
    3547809: "Santo André",
    3548807: "São Caetano do Sul",
    3505708: "Barueri",
    3513009: "Cotia",
    3522505: "Itapevi",
    3523107: "Itaquaquecetuba",
    3552502: "Suzano",
    3510609: "Carapicuíba",
    3522208: "Itapecerica da Serra",
    3513801: "Diadema",
    3539806: "Poá",
    3543303: "Ribeirão Pires",
    3525003: "Jandira",
    3516408: "Franco da Rocha",
    3552809: "Taboão da Serra",
    3509205: "Cajamar",
    3547304: "Santana de Parnaíba",
    3515707: "Ferraz de Vasconcelos",
    3515004: "Embu das Artes",
    3556453: "Vargem Grande Paulista",
    3503901: "Arujá",
    3515103: "Embu-Guaçu",
    3544103: "Rio Grande da Serra",
    3549953: "São Lourenço da Serra",
}

NOME_REGIAO = "São Paulo e Região"

# ============================================================
# FONTE DE DADOS
# ============================================================
# TOTVS continua sendo a fonte de coordenada confiável (join por
# cod_cliente) — o Excel abaixo só define a carteira (VENDEDOR_FINAL).
TOTVS_CLIENTE_CSV = r"\\192.168.0.226\pdi\in\full\totvs_cliente.csv"
CARTEIRA_SP_XLSX  = r"C:\Users\accrisci\Desktop\CARTEIRA_VD_SP.xlsx"

# ============================================================
# USUÁRIOS DO MAPA
# Senhas conforme cadastrado em mapa_senha no Supabase.
# ============================================================
USUARIOS_MAPA = {
    "master_sp":     {"senha": "fugini@master_sp", "arquivo": "master_sp.html"},
    "vendedor_sp01": {"senha": "fugini@sp1",        "arquivo": "vendedor_sp01.html"},
    "vendedor_sp02": {"senha": "fugini@sp2",        "arquivo": "vendedor_sp02.html"},
    "vendedor_sp03": {"senha": "fugini@sp3",        "arquivo": "vendedor_sp03.html"},
    "vendedor_sp04": {"senha": "fugini@sp4",        "arquivo": "vendedor_sp04.html"},
}

# Mapeia cada chave de USUARIOS_MAPA para o cod_vendedor correspondente
# na carteira (usado por exportar_mapas() para filtrar o df por vendedor).
# "master_sp" não filtra — vê a carteira completa dos 4.
USUARIO_PARA_COD_VENDEDOR = {
    "vendedor_sp01": "SP01",
    "vendedor_sp02": "SP02",
    "vendedor_sp03": "SP03",
    "vendedor_sp04": "SP04",
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

# Bounding box do Brasil (validação ampla — genérica, igual ao SC)
GEO_LAT_MIN = -33.75
GEO_LAT_MAX =  5.27
GEO_LNG_MIN = -73.99
GEO_LNG_MAX = -28.84
