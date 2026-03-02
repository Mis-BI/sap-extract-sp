# SAP Extract SP

Projeto hibrido com dois modos de execucao:

1. `API FastAPI` para automacao SAP GUI (login, ZUCRM_039, regra de negocio de notas, IW59 e exportacoes).
2. `Pipeline ETL legado` para processar arquivos Excel ja exportados e carregar no SQL Server.

## Visao Geral

### Fluxo da API (automacao SAP)

1. Recebe periodo (`start_date`, `end_date`) no endpoint `POST /api/v1/sap/run`.
2. Conecta no SAP GUI via COM (`win32com`) e tenta abrir a conexao configurada.
3. Se `OpenConnection` falhar, faz fallback de UI no SAP Logon (`pywinauto`):
   - seleciona o server na arvore (ex.: `00 SAP ERP`)
   - da duplo clique na conexao da grade (ex.: `H181 RP1 ENEL SP CCS Producao (without SSO)`).
4. Faz login com credenciais do `.env`.
5. Executa `ZUCRM_039`, exporta para pasta da transacao (`downloads/zucrm039` por padrao).
6. Le a planilha ZUCRM e aplica regra de negocio na coluna `Nº Nota/Medida`:
   - remove linhas com `/000`
   - remove zeros a esquerda (converte para numero)
   - deduplica as notas.
7. Retorna com F3 (3 a 4 vezes) para preparar proxima transacao.
8. Executa `IW59`, cola notas no multi-selecao e exporta para `downloads/iw59`.
9. Cria uma copia completa do arquivo IW59 com nome `iw59_copia_completa_YYYYMMDD_HHMMSS.xlsx`.
10. Retorna caminhos dos arquivos e quantidade de notas usadas.

### Fluxo ETL legado (arquivos locais)

1. Localiza arquivos `sap_gov_sp_*.XLSX` (e `brs_sap_gov_sp_*.XLSX` correspondentes).
2. Faz merge SAP/BRS por numero da nota.
3. Transforma, normaliza colunas e datas.
4. Remove registros antigos no banco por `data_inicio_zucrm`.
5. Insere os registros novos no SQL Server.

## Estrutura do Projeto

```text
enel-sap-sp/
├── app/                      # API FastAPI + automacao SAP
│   ├── main.py
│   ├── api/routes/
│   ├── core/
│   └── sap/
├── config/                   # Config do ETL legado (DB + file_history)
├── database/                 # SQLAlchemy (conexao + modelo)
├── etl/                      # Extract / Transform / Load legado
├── docs/
│   └── MODULES.md            # Documentacao detalhada modulo a modulo
├── downloads/                # Pasta base de exportacoes SAP
│   ├── zucrm039/
│   └── iw59/
├── file_history/             # Historico de planilhas para ETL legado
├── pipeline.py               # CLI do ETL legado
├── .env.example
└── requirements.txt
```

## Requisitos

- Python 3.10+
- Windows com SAP GUI instalado para usar a API de automacao
- SAP GUI Scripting habilitado (cliente + servidor SAP)
- SQL Server acessivel para o ETL legado

Dependencias principais:

- `fastapi`, `uvicorn`
- `pywin32` (COM SAP + clipboard)
- `pywinauto` (fallback de clique no SAP Logon)
- `pandas`, `openpyxl`
- `sqlalchemy`, `pyodbc`

## Configuracao

1. Criar `.env` a partir de `.env.example`:

```bash
cp .env.example .env
```

2. Preencher variaveis SAP e banco conforme ambiente.

### Variaveis SAP (API)

| Variavel | Descricao | Default |
|---|---|---|
| `SAP_USERNAME` | Usuario SAP | vazio |
| `SAP_PASSWORD` | Senha SAP | vazio |
| `SAP_CLIENT` | Mandante SAP (opcional) | vazio |
| `SAP_LANGUAGE` | Idioma login SAP | `PT` |
| `SAP_SERVER_NAME` | Nome do server no SAP Logon | `00 SAP ERP` |
| `SAP_CONNECTION_NAME` | Nome da conexao no SAP Logon | `H181 RP1 ENEL SP CCS Producao (without SSO)` |
| `SAP_LOGON_EXECUTABLE` | Caminho do `saplogon.exe` | caminho padrao SAP GUI |
| `SAP_EXPORT_DIR` | Pasta base de exportacoes | `downloads` |
| `SAP_ZUCRM_EXPORT_DIR` | Pasta da exportacao ZUCRM | `downloads/zucrm039` |
| `SAP_IW59_EXPORT_DIR` | Pasta da exportacao IW59 | `downloads/iw59` |
| `SAP_ZUCRM_EXPORT_GLOB` | Padrao de arquivo ZUCRM | `export*.XLSX` |
| `SAP_IW59_EXPORT_GLOB` | Padrao de arquivo IW59 | `brs_sap_gov_sp*.XLSX` |
| `SAP_EXPORT_TIMEOUT_SECONDS` | Timeout para detectar exportacao | `180` |
| `SAP_F3_MAX_PRESSES` | Limite maximo para retorno com F3 | `20` |
| `SAP_QMART` | Campo da ZUCRM_039 | `ov` |
| `SAP_VARIATION` | Variacao da ZUCRM_039 | `/abap ov2` |
| `SAP_TRANSACTION_ZUCRM` | Codigo da transacao ZUCRM | `zucrm_039` |
| `SAP_TRANSACTION_IW59` | Codigo da transacao IW59 | `iw59` |

### Variaveis de logging

| Variavel | Descricao | Default |
|---|---|---|
| `LOG_LEVEL` | Nivel do logger root | `INFO` |
| `LOG_FILE` | Arquivo de log rotativo | `logs/sap_automation.log` |

### Variaveis de banco (ETL legado)

| Variavel | Descricao | Default |
|---|---|---|
| `DB_DRIVER` | Driver ODBC SQL Server | `ODBC Driver 18 for SQL Server` |
| `DB_SERVER` | Servidor SQL | vazio |
| `DB_DATABASE` | Database alvo | `ENEL` |
| `DB_USER` | Usuario SQL | vazio |
| `DB_PASSWORD` | Senha SQL | vazio |
| `FILE_HISTORY_DIR` | Pasta de entrada do ETL legado | `file_history` |

## Execucao

### 1) API FastAPI (automacao SAP)

Subir API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Healthcheck:

```bash
curl http://localhost:8000/health
```

Chamada da automacao (Windows, uma linha):

```bash
curl -X POST "http://localhost:8000/api/v1/sap/run" -H "Content-Type: application/json" -d "{\"start_date\":\"2026-01-19\",\"end_date\":\"2026-02-19\"}"
```

JSON aceito no payload:

- `start_date`/`end_date` ou `startDate`/`endDate`
- formatos: `YYYY-MM-DD`, `DD.MM.YYYY`, `DD/MM/YYYY`

Resposta de sucesso:

```json
{
  "status": "success",
  "zucrm_export_file": ".../downloads/zucrm039/export123.xlsx",
  "iw59_export_file": ".../downloads/iw59/iw59_copia_completa_20260227_163500.xlsx",
  "notes_count": 123
}
```

### 2) ETL legado (pipeline.py)

Processar arquivo especifico:

```bash
python pipeline.py --file file_history/sap_gov_sp_202501.XLSX
```

Processar periodo:

```bash
python pipeline.py --period 202501
```

Processar todos:

```bash
python pipeline.py --all
```

## Regras de Negocio Importantes

### Regra de notas para IW59 (API)

- Coluna alvo: `Nº Nota/Medida` (com normalizacao de variacao de nome/acento).
- Remove linhas com `/000`.
- Mantem apenas digitos.
- Converte para inteiro e volta para string (remove zeros a esquerda).
- Remove duplicatas preservando ordem.

### Regra de protocolo GOV (ETL)

No `transform.py`, quando `protocolo_gov_zucrm` esta invalido e origem e GOV, pode haver reconstrucao com base em:

- `data_inicio_zucrm` (`YYYYMM`)
- ultimos 11 digitos de `numero_sgo_zucrm`

## Logging e Observabilidade

- Middleware gera `X-Request-ID` por requisicao HTTP.
- Todos os logs da API carregam `request_id`.
- Saida em console + arquivo rotativo (`RotatingFileHandler`).

## Erros Comuns

- `SAP Logon connection entry not found`: nome da conexao no `.env` nao bate com SAP Logon.
- `Elemento SAP nao encontrado`: tela nao estava no estado esperado (timing/navegacao/variante de layout).
- Timeout de exportacao: arquivo nao foi salvo no diretorio monitorado ou padrao de nome (`glob`) nao corresponde.

## Documentacao Detalhada

- Consulte [docs/MODULES.md](docs/MODULES.md) para referencia completa de cada modulo, classe e funcao principal.

