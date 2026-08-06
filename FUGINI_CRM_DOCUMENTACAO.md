# ⚠️ Documentação movida

Este arquivo era uma **cópia de junho/2026** da documentação do CRM e ficou
defasado. A documentação viva está centralizada no repo **privado**
`FIC-Fugini/fugini-crm`, em **`docs/`** (`docs/README.md` é o índice).

## O essencial DESTE repo (mapa São Paulo)

- **Pipeline diário:** roda no servidor **SRVFGN027** às 06:00 (tarefa
  `Pipeline_Mapa_Clientes_SP`, pasta `C:\projetos\Projeto_23_...`).
  ⚠️ O servidor **não faz git pull** — mudou código aqui, copiar os arquivos
  para lá via `\\192.168.0.242\c$\projetos\...`.
- **Este repo nasceu como clone do Projeto_19 (SC)** e já divergiu em partes
  (ex.: `prospect_ownership.py`, 4 vendedores + master). Feature de mapa
  normalmente precisa ser aplicada nos dois.
- **`src/web/checkin.html`** é a FONTE do formulário de check-in (versionada).
  Publicar só ele, sem rodar o pipeline: `python publicar_checkin.py`
  (tem `--dry-run`). O mesmo arquivo existe no Projeto_19 (SC) — manter os
  dois em sincronia.
- **Ordem de deploy ao apertar validação de campo:** formulário primeiro
  (CDN do GitHub Pages leva ~10 min), API do CRM depois. Receita completa em
  `fugini-crm/docs/README.md`.
- **Popups do mapa:** botões 📍 Check-in e 📅 Agendar (este abre a `/agenda`
  do CRM — o mapa não chama a API de agendamentos). URL do CRM em
  `config/settings.py` (`CRM_BASE_URL`).
- **Crédito no heatmap** é deduplicado por matriz
  (`_df_credito_sem_duplicata_matriz` no `builder.py`) — característica geral
  do ERP (não só de SP): carteiras SP inflavam entre 1,00x e 3,06x.
