# Fugini CRM — Documentação Completa
**Última atualização:** Junho 2026  
**Desenvolvedor:** Artur Crisci (accrisci@fugini.com.br)  
**Versão atual:** v1.2-prospects

---

## 1. Visão Geral do Sistema

O Fugini CRM é um sistema interno para a força de vendas em campo da Fugini Alimentos, região de São Carlos e entorno. É composto por dois projetos independentes que se comunicam via URLs:

| Projeto | Tecnologia | Função |
|---------|-----------|--------|
| **fugini-crm** | Next.js 16 + Supabase | Login, painel, agenda, check-in |
| **Projeto_19_Mapa_Clientes_Sao_Carlos** | Python + Folium | Geração dos mapas interativos |

---

## 2. Arquitetura

```
[TOTVS ERP] ──CSV──► [Pipeline Python] ──► [Mapas HTML criptografados] ──► [GitHub Pages]
                            │
                            └──► [Supabase PostgreSQL] ◄──► [CRM Next.js] ──► [Vercel]
                                                                    │
                                                             [Johnny / Master]
```

### Fluxo do usuário
1. Johnny acessa `fugini-checkin-api.vercel.app` e faz login
2. No painel, clica em "Mapa de Clientes" — abre mapa do GitHub Pages com auto-login via hash da URL
3. No mapa, gera roteiro e inclui clientes na agenda
4. Na agenda, vê visitas do dia e faz check-in de cada cliente
5. Check-in registra localização GPS e atualiza status do agendamento

---

## 3. Projeto CRM (fugini-crm)

### 3.1 Localização
```
C:\Users\accrisci\Desktop\Artur\Projetos\fugini-checkin-api\
```

### 3.2 Repositório GitHub
- **URL:** https://github.com/Fugini-FIC/fugini-crm
- **Branch principal:** master
- **Visibilidade:** Público (⚠️ senhas dos mapas estão no código — ver pendências)
- **Deploy:** Vercel, automático a cada push no master

### 3.3 Domínio em produção
- **URL correta:** https://fugini-checkin-api.vercel.app
- ⚠️ `fugini-crm.vercel.app` também existe mas é um projeto antigo — não usar

### 3.4 Estrutura de arquivos
```
fugini-checkin-api/
├── pages/
│   ├── _app.tsx              # App wrapper padrão Next.js
│   ├── _document.tsx         # Document wrapper padrão Next.js
│   ├── index.tsx             # Redireciona para /painel
│   ├── login.tsx             # Tela de login com Supabase Auth
│   ├── painel.tsx            # Painel principal do vendedor
│   ├── agenda.tsx            # Calendário + lista de visitas + modal
│   └── api/
│       ├── agendamentos.ts   # GET/POST/PATCH/DELETE de agendamentos
│       ├── checkin.ts        # POST/GET de check-ins
│       └── ping-interno.ts   # Health check
├── lib/
│   └── supabase.ts           # Cliente Supabase (anon key)
├── proxy.ts                  # Middleware Next.js 16 (proteção de rotas)
├── .env.local                # Variáveis de ambiente (não commitado)
├── package.json
└── next.config.ts
```

### 3.5 Variáveis de ambiente (.env.local)
```
NEXT_PUBLIC_SUPABASE_URL=https://pyiybinbsnouxdtnfcpe.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGci...H8Cw
SUPABASE_URL=https://pyiybinbsnouxdtnfcpe.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...ULi0
```
⚠️ A `SERVICE_ROLE_KEY` tem acesso total ao banco — nunca expor publicamente.

### 3.6 Configurar variáveis no Vercel
Acesse: `vercel.com/fic-fugini/fugini-crm/settings/environment-variables`

### 3.7 Páginas e funcionalidades

#### /login
- Autenticação via Supabase Auth (email + senha)
- Após login, redireciona para /painel via `router.push('/painel')`
- Proteção: proxy.ts verifica sessão

#### /painel
- Busca dados do vendedor logado na tabela `vendedores` (cruzando por email)
- Salva `cod_vendedor` no `localStorage` para uso nas outras páginas
- Exibe botões: Mapa de Clientes, Agenda, Check-in
- URL do mapa: `mapa_url#mapa_senha` (senha no hash = auto-login sem digitar)

#### /agenda
- Calendário mensal com marcadores coloridos por status
- Lista de visitas do dia selecionado
- Modal para criar nova visita (cod_cliente, nome, data, hora, observação)
- Botão 📍 Check-in nos agendamentos pendentes
- Botão 🗑️ Excluir em todos os agendamentos
- Endereço e número do roteiro aparecem em cada card

#### API /api/agendamentos
- `GET ?cod_vendedor=SC01&mes=2026-06` — lista agendamentos do mês
- `POST` — cria agendamento (ignora duplicata cod_cliente+data+vendedor)
- `PATCH ?id=UUID` — atualiza status e checkin_id
- `DELETE ?id=UUID` — remove agendamento
- Campos: `cod_cliente, nome_cliente, cod_vendedor, data_visita, hora_visita, observacao, endereco, ordem_roteiro, status, checkin_id`

#### API /api/checkin
- `POST` — registra check-in com geolocalização
- `GET ?cod_vendedor=SC01` — lista check-ins

### 3.8 Como fazer deploy
```cmd
cd C:\Users\accrisci\Desktop\Artur\Projetos\fugini-checkin-api
git add .
git commit -m "descrição"
git push origin master
```
O Vercel detecta o push e faz deploy automático em ~30 segundos.

### 3.9 Como rodar localmente
```cmd
cd C:\Users\accrisci\Desktop\Artur\Projetos\fugini-checkin-api
npm run dev
```
Acesse: http://localhost:3000

---

## 4. Projeto Mapa (Projeto_19_Mapa_Clientes_Sao_Carlos)

### 4.1 Localização
```
C:\Users\accrisci\Desktop\Artur\Projetos\Projeto_19_Mapa_Clientes_Sao_Carlos\
```

### 4.2 Repositório GitHub
- **URL:** https://github.com/Fugini-FIC/fugini-mapa-sc
- **Branch principal:** main
- **Branch de publicação:** gh-pages (GitHub Pages)
- **URL pública:** https://fugini-fic.github.io/fugini-mapa-sc/

### 4.3 Estrutura de arquivos
```
Projeto_19_Mapa_Clientes_Sao_Carlos/
├── pipeline.py                    # Orquestrador principal
├── refinar_prospects.py           # Script one-time: geocodifica prospects via Google
├── sync_supabase.py               # Sincroniza dados com Supabase
├── config/
│   └── settings.py                # Configurações centralizadas (regiões, APIs, etc)
├── src/
│   ├── ingestion/
│   │   └── loader.py              # Carrega clientes do CSV TOTVS
│   ├── geocoding/
│   │   └── geocoder.py            # Geocodifica clientes via Google Maps API
│   ├── enrichment/
│   │   ├── historico.py           # Enriquece com faturamento NF (fugini_dw)
│   │   └── prospects.py           # Carrega prospects da Receita Federal
│   ├── mapping/
│   │   ├── builder.py             # Gera o HTML do mapa com Folium
│   │   ├── roteamento.py          # Painel de roteirização (JS + algoritmo)
│   │   └── crypto.py              # Criptografia AES-256-CBC dos HTMLs
│   └── publishing/
│       └── github_pages.py        # Publica HTMLs no gh-pages via git push
├── data/
│   └── output/                    # HTMLs gerados pelo pipeline
│       ├── master_sc.html         # Mapa do master (criptografado)
│       ├── vendedor_sc.html       # Mapa do Johnny (criptografado)
│       └── checkin.html           # Página de check-in (estático)
└── .env                           # Credenciais (não commitado)
```

### 4.4 Variáveis de ambiente (.env)
```
GITHUB_TOKEN=ghp_...              # Token GitHub para push no gh-pages
SUPABASE_SERVICE_ROLE_KEY=eyJ...  # Chave Supabase (usada pelo sync_supabase.py)
GOOGLE_API_KEY=AIzaSy...          # Chave Google Maps (Geocoding API)
```

### 4.5 Como rodar o pipeline
```cmd
cd C:\Users\accrisci\Desktop\Artur\Projetos\Projeto_19_Mapa_Clientes_Sao_Carlos
.venv\Scripts\activate
python pipeline.py
```

**Opções:**
```cmd
python pipeline.py --no-crypt     # Sem criptografia (teste local)
python pipeline.py --no-publish   # Sem publicar no GitHub Pages
```

### 4.6 O que o pipeline faz (em ordem)
1. **[1/5] Carrega clientes** do CSV TOTVS (`\\192.168.0.226\pdi\in\full\totvs_cliente.csv`)
   - Carteira do Johnny: filtra por `cod-erc = 6003`
   - Disponíveis (sem representante): loga os códigos mas não plota no mapa
2. **[2/5] Geocodifica** clientes sem coordenada válida via Google Maps API
   - Checkpoint no banco `mapa_clientes.geocodificacao_checkpoint`
   - Clientes já processados não são reprocessados
3. **[3/5] Enriquece** com histórico de faturamento
   - Conecta em `fugini_dw` (schema `bronze`) — tabelas `faturamento_nf` e `item`
   - Calcula `ultima_compra`, `dias_sem_compra`, `status_compra`
4. **[4/5] Carrega prospects** da Receita Federal
   - Conecta em `mapa_clientes.prospects`
   - Filtros: região SP, capital mínimo R$10k, ativo há mais de 1 ano
5. **[5/5] Gera e publica HTMLs**
   - `vendedor_sc.html` — perfil vendedor (só carteira do Johnny)
   - `master_sc.html` — perfil master (visão completa)
   - Ambos criptografados com AES-256-CBC
   - Publicados no GitHub Pages via git push

### 4.7 Algoritmo de roteirização
- **Tipo:** heurística radial gulosa (não é TSP ótimo)
- **Fundamento:** mTSP com depósito único + Nearest Neighbor + Haversine
- **Funcionamento:**
  - Todo dia parte de casa e volta para casa (ciclo fechado)
  - A cada dia, pega N clientes + M prospects mais próximos de casa ainda não usados
  - Dentro do dia, ordena as paradas por Nearest Neighbor
  - Dias sucessivos avançam radialmente (os mais próximos já foram usados)
- **Configuração:** campos "Clientes/dia" e "Prospects/dia" no painel Roteiro do mapa

### 4.8 Criptografia dos mapas
- **Algoritmo:** AES-256-CBC com PBKDF2-SHA256 (100k iterações)
- **Senhas:**
  - Johnny: `fugini@sc1`
  - Master: `fugini@master_sc`
- **Auto-login:** a senha é passada no hash da URL (`#fugini@sc1`)
  - O JS do mapa lê `window.location.hash` e descriptografa automaticamente
  - Quem não tem a URL completa precisa digitar a senha manualmente

### 4.9 Geocodificação de prospects
Os prospects da Receita Federal foram geocodificados via Nominatim (gratuito mas impreciso). Para refinar com Google Maps API:
```cmd
python refinar_prospects.py --dry-run   # Ver quantos serão processados
python refinar_prospects.py             # Processar de verdade
```
⚠️ Só rodar uma vez — o script marca `geo_refined = TRUE` após processar.  
Se precisar resetar e reprocessar:
```sql
-- No banco mapa_clientes, tabela prospects:
UPDATE prospects SET geo_refinada = FALSE
WHERE [condições desejadas];
```

---

## 5. Banco de Dados

### 5.1 Supabase (dados do CRM)
- **Projeto:** fugini-crm
- **Região:** São Paulo
- **URL:** https://pyiybinbsnouxdtnfcpe.supabase.co
- **Dashboard:** https://supabase.com/dashboard/project/pyiybinbsnouxdtnfcpe

#### Tabela: vendedores
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| cod_vendedor | text | PK — ex: SC01, MASTER |
| nome | text | Nome do vendedor |
| role | text | vendedor ou master |
| email | text | Email do Supabase Auth (para cruzamento) |
| mapa_url | text | URL do mapa do vendedor |
| mapa_senha | text | Senha do mapa (hash da URL) |

**RLS:** desabilitado (necessário para a anon key conseguir ler)

**Dados atuais:**
- `SC01` — Johnny, vendedor, sao_carlos, johnny@fugini.internal
- `MASTER` — Master, master, todas, master@fugini.internal

#### Tabela: agendamentos
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | uuid | PK gerado automaticamente |
| cod_cliente | text | Código do cliente no TOTVS |
| nome_cliente | text | Nome do cliente |
| cod_vendedor | text | FK para vendedores |
| data_visita | date | Data da visita |
| hora_visita | time | Hora (opcional) |
| observacao | text | Observação (opcional) |
| endereco | text | Endereço completo (preenchido pelo roteiro) |
| ordem_roteiro | integer | Posição na rota do dia (1, 2, 3...) |
| status | text | pendente, realizada, ausente, reagendada |
| checkin_id | uuid | FK para checkins (preenchido no check-in) |
| timestamp_criacao | timestamptz | Criado automaticamente |

**Constraint única:** `cod_cliente + data_visita + cod_vendedor` (sem duplicata)

#### Tabela: checkins
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | uuid | PK |
| cod_cliente | text | Código do cliente |
| nome_cliente | text | Nome do cliente |
| cod_vendedor | text | Código do vendedor |
| lat_vendedor | float | Latitude GPS no momento do check-in |
| lng_vendedor | float | Longitude GPS no momento do check-in |
| status_visita | text | realizada, ausente, reagendada |
| observacao | text | Opcional |
| timestamp | timestamptz | Horário UTC (converter para BRT: -3h) |

⚠️ O `timestamp` está em UTC — para exibir no horário de Brasília, subtrair 3 horas.

### 5.2 PostgreSQL interno (192.168.0.242)
- **Usuário:** postgres
- **Senha:** Postgres2025
- **Porta:** 5432

| Banco | Uso |
|-------|-----|
| `mapa_clientes` | Prospects da Receita Federal, checkpoint de geocodificação |
| `fugini_dw` | Data warehouse — faturamento NF, itens, pedidos (schema: `bronze`) |
| `cnpj_db` | Base da Receita Federal |
| `erp_progress` | Apenas ETL logs (tabelas `etl_checkpoint` e `etl_log`) |

#### Tabelas importantes no fugini_dw (schema bronze)
- `bronze.faturamento_nf` — histórico de notas fiscais
- `bronze.item` — cadastro de itens/produtos

#### Tabelas importantes no mapa_clientes
- `prospects` — empresas da Receita Federal para prospecção
  - `lat_final` e `lng_final` são colunas **geradas**: `COALESCE(lat_refined, lat_cep)`
  - Para atualizar coordenadas, usar `lat_refined` e `lng_refined`
  - `geo_refinada = TRUE` significa que já passou pelo Google Maps API
- `geocodificacao_checkpoint` — clientes já geocodificados via Google

### 5.3 CSV do TOTVS
- **Caminho:** `\\192.168.0.226\pdi\in\full\totvs_cliente.csv`
- **Encoding:** latin-1
- **Separador:** `;`
- **Campos relevantes:** `cod-cliente`, `nome-cliente`, `cod-erc`, `NomERC`, `status-cliente`, `cod-ibge`, `lat-cliente`, `long-cliente`, `endereco`, `bairro`, `cep`, `limite-disp`
- **Carteira do Johnny:** `cod-erc = 6003`
- **Disponíveis (sem representante):** `NomERC = "DISPONIVEL - FS"` ou vazio

---

## 6. Usuários e Credenciais

### 6.1 Supabase Auth
| Email | Senha | Perfil |
|-------|-------|--------|
| johnny@fugini.internal | Johnny@2026 | vendedor (SC01) |
| master@fugini.internal | (definida no setup) | master (MASTER) |

### 6.2 Senhas dos mapas
| Mapa | Senha | URL completa |
|------|-------|-------------|
| Vendedor (Johnny) | `fugini@sc1` | https://fugini-fic.github.io/fugini-mapa-sc/vendedor_sc.html#fugini@sc1 |
| Master | `fugini@master_sc` | https://fugini-fic.github.io/fugini-mapa-sc/master_sc.html#fugini@master_sc |

### 6.3 Google Cloud
- **Projeto:** voice-calendar-bot (falarcomartur-org)
- **Chave usada:** `fugini-mapa` (restrição de referenciador removida para uso em scripts)
- **API habilitada:** Geocoding API
- **Onde configurar:** console.cloud.google.com → APIs & Services → Credentials

### 6.4 GitHub
- **Organização:** Fugini-FIC
- **Token:** no `.env` do Projeto 19 (`GITHUB_TOKEN`)
- ⚠️ Token clássico (não fine-grained) — necessário para repos da org

---

## 7. Operações Comuns (SQL)

### Limpar todos os agendamentos de teste
```sql
DELETE FROM agendamentos;
```

### Limpar agendamentos de um vendedor específico
```sql
DELETE FROM agendamentos WHERE cod_vendedor = 'SC01';
```

### Ver últimos check-ins
```sql
SELECT * FROM checkins ORDER BY timestamp DESC LIMIT 20;
```

### Ver agendamentos de um dia
```sql
SELECT * FROM agendamentos WHERE data_visita = '2026-06-16' ORDER BY ordem_roteiro;
```

### Ver dados dos vendedores
```sql
SELECT * FROM vendedores;
```

### Atualizar mapa de um vendedor
```sql
UPDATE vendedores 
SET mapa_url = 'https://...', mapa_senha = 'nova_senha'
WHERE cod_vendedor = 'SC01';
```

### Adicionar novo vendedor
```sql
INSERT INTO vendedores (cod_vendedor, nome, role, email, mapa_url, mapa_senha)
VALUES ('SC02', 'Nome Vendedor', 'vendedor', 'email@fugini.internal', 'https://...', 'senha_mapa');
```

### Resetar geocodificação de prospects para reprocessar
```sql
-- No banco mapa_clientes:
UPDATE prospects SET geo_refinada = FALSE
WHERE lat_final IS NOT NULL
  AND lat_final BETWEEN -22.6 AND -21.4
  AND lng_final BETWEEN -49.2 AND -47.4
  AND identificador_matriz_filial = '1'
  AND capital_social >= 10000
  AND UPPER(municipio) = ANY(ARRAY['SAO CARLOS','ARARAQUARA','IBATE','ITIRAPINA','SÃO CARLOS']);
```

---

## 8. Pendências e Dívidas Técnicas

### Alta prioridade (segurança)
1. **Repo público:** `fugini-crm` está público no GitHub. Mover senhas dos mapas (`fugini@sc1`, `fugini@master_sc`) para variáveis de ambiente no Vercel e tornar repo privado
2. **APIs sem validação:** qualquer usuário logado pode criar agendamentos para qualquer vendedor (não valida `cod_vendedor`)
3. **checkin.html sem autenticação:** qualquer pessoa com a URL pode registrar check-ins

### Média prioridade (funcionalidade)
4. **Campo "Cód. Vendedor" na roteirização:** aparece vazio — deveria vir pré-preenchido do `localStorage`
5. **Mapa do master sem disponíveis:** o loader removeu disponíveis do df; master precisa receber disponíveis separadamente via segundo df no `montar_mapa`
6. **Visão Master da agenda:** selecionar vendedor, gerenciar agenda de outros, limpar mês — ficou para Phase 2

### Baixa prioridade (melhoria)
7. **`roteamento.py` hospeda navbar:** código de UI que não pertence ao módulo de roteirização
8. **Algoritmo de roteirização:** poderia evoluir para clustering geográfico (K-Means) para melhor otimização de deslocamento
9. **Token GitHub no histórico git:** verificar se algum token foi commitado acidentalmente e revogar

---

## 9. Versões (Tags Git)

| Tag | Repos | Descrição |
|-----|-------|-----------|
| v1.0-funcional | fugini-crm | Login, painel, agenda, checkin, mapa funcionais |
| v1.1-roteiro | fugini-crm | Roteirização com prospects, ciclo fechado |
| v1.2-prospects | fugini-crm + fugini-mapa-sc | Prospects geocodificados Google API, painel unificado |

---

## 10. Arquitetura de Segurança dos Mapas

O mapa usa criptografia de ponta a ponta:
1. O HTML do mapa é criptografado em Python com AES-256-CBC + PBKDF2-SHA256
2. O arquivo criptografado é publicado no GitHub Pages
3. O CRM passa a senha no hash da URL (`#fugini@sc1`)
4. O JS no browser lê o hash, deriva a chave com PBKDF2, e descriptografa o conteúdo
5. O servidor do GitHub **nunca** vê a senha (hash não é enviado ao servidor)

Quem não tem a URL completa com o `#senha` vê apenas uma tela pedindo senha.

---

## 11. Contatos e Acessos

| Sistema | Acesso |
|---------|--------|
| Supabase | supabase.com → projeto pyiybinbsnouxdtnfcpe |
| Vercel | vercel.com → organização FIC |
| GitHub | github.com/Fugini-FIC |
| Google Cloud | console.cloud.google.com → falarcomartur-org → voice-calendar-bot |
| DBeaver | 192.168.0.242:5432 (usuário: postgres / senha: Postgres2025) |
| TOTVS CSV | \\192.168.0.226\pdi\in\full\ |
| Progress ERP API | 192.168.0.223:8180 (Cleber) |

---

*Documentação gerada em Junho 2026. Para atualizar, editar este arquivo e commitar nos repos relevantes.*
