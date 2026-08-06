# ============================================================
# src/ingestion/loader.py
# Carrega clientes da carteira de São Paulo diretamente do
# totvs_cliente.csv (\\192.168.0.226\pdi\in\full\), mesmo padrão
# usado no Projeto_19 (São Carlos) para o Jhony (cod-erc=6003).
#
# Cada vendedor de SP tem seu próprio cod-erc:
#   SP01 (Joao)   -> cod-erc 6007
#   SP02 (Robson) -> cod-erc 6005
#   SP03 (Simone) -> cod-erc 6004
#   SP04 (Wesley) -> cod-erc 6006
#
# Substitui a versão anterior que lia CARTEIRA_VD_SP.xlsx — essa
# mudança elimina os problemas de corrupção de coordenada e CEP
# que existiam no Excel, já que agora lemos direto da fonte
# confiável (TOTVS), igual ao fluxo do SC.
#
# Não existe conceito de "disponível" (sem dono) em SP — todo
# cliente filtrado por um dos 4 cod-erc já pertence a um vendedor.
# ============================================================

import logging
import pandas as pd
from config.settings import TOTVS_CLIENTE_CSV, IBGE_CIDADE

logger = logging.getLogger(__name__)

MAPEAMENTO = {
    "cod-cliente":   "cod_cliente",
    "nome-cliente":  "nome_cliente",
    "limite-disp":   "limite_disp",
    "lat-cliente":   "lat_totvs",
    "long-cliente":  "lng_totvs",
    "endereco":      "endereco",
    "bairro":        "bairro",
    "cep":           "cep",
    "cod-ibge":      "cod_ibge",
    "telefone":      "telefone",
    "cnpj":          "cnpj",
    "NomERC":        "representante",
}

# NomERC que indicam categorias internas do TOTVS — excluir do mapa
# (mesmo critério usado no SC)
NOMERC_EXCLUIDOS = {"EXPORTAÇÃO", "CLIENTE PLATAFORMA"}

# cod-erc de cada vendedor de SP no TOTVS
COD_ERC_SP = {
    "6007": "SP01",  # Joao
    "6005": "SP02",  # Robson
    "6004": "SP03",  # Simone
    "6006": "SP04",  # Wesley
}


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=MAPEAMENTO)
    for col in ["lat_totvs", "lng_totvs", "limite_disp"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["cod_ibge"]      = pd.to_numeric(df["cod_ibge"], errors="coerce")
    df["cod_cliente"]   = df["cod_cliente"].astype(str).str.strip()
    df["representante"] = df["representante"].fillna("").str.strip()
    df["cidade"] = df["cod_ibge"].map(IBGE_CIDADE).fillna("Desconhecida")
    return df


def carregar_clientes() -> pd.DataFrame:
    """
    Retorna DataFrame com a carteira completa de São Paulo (4 vendedores),
    filtrada diretamente por cod-erc no TOTVS — mesmo padrão do SC.

    Sem restrição de IBGE — o cod-erc já define a carteira correta,
    igual ao comentário original do loader.py do SC.
    """
    logger.info(f"Lendo CSV: {TOTVS_CLIENTE_CSV}")
    df_raw = pd.read_csv(TOTVS_CLIENTE_CSV, encoding="latin1", sep=";", dtype=str)
    logger.info(f"  {len(df_raw):,} clientes no CSV total.")

    mask_ativo     = df_raw["status-cliente"].str.strip() == "Ativo"
    mask_excluidos = df_raw["NomERC"].fillna("").str.strip().isin(NOMERC_EXCLUIDOS)
    cod_erc_limpo  = df_raw["cod-erc"].fillna("").str.strip()
    mask_erc_sp    = cod_erc_limpo.isin(COD_ERC_SP.keys())

    df_todos = df_raw[mask_ativo & mask_erc_sp & ~mask_excluidos].copy()
    df_todos = _normalizar(df_todos)

    # Mapeia cod-erc -> cod_vendedor (precisa ser feito ANTES do _normalizar
    # renomear as colunas, então recupera do df_raw filtrado na mesma ordem)
    cod_erc_filtrado = cod_erc_limpo[mask_ativo & mask_erc_sp & ~mask_excluidos]
    df_todos["cod_vendedor"] = cod_erc_filtrado.map(COD_ERC_SP).values

    df_todos["tipo_cliente"] = "carteira"
    df_todos["fonte"]        = "sao_paulo"

    for vendedor, qtd in df_todos["cod_vendedor"].value_counts().sort_index().items():
        logger.info(f"  {vendedor}: {qtd:,} clientes")

    colunas = (
        [c for c in MAPEAMENTO.values() if c in df_todos.columns]
        + ["cidade", "cod_vendedor", "tipo_cliente", "fonte"]
    )
    df = df_todos[[c for c in colunas if c in df_todos.columns]].copy()
    df = df.drop_duplicates(subset="cod_cliente", keep="first")
    logger.info(f"  Total carregado: {len(df):,} clientes")
    return df