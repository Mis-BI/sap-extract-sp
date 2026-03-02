# Module Reference

Este documento descreve cada modulo principal do projeto, responsabilidades, dependencias e pontos de extensao.

## 1. API e Bootstrapping

### `app/main.py`

Responsabilidades:

- Inicializa `FastAPI`.
- Carrega `Settings` e configura logging global.
- Registra rotas em `app.api.routes.sap_automation`.
- Adiciona middleware de `request_id` (`X-Request-ID`) para rastreabilidade fim a fim.
- Expoe healthcheck em `GET /health`.

Dependencias diretas:

- `app.core.settings.get_settings`
- `app.core.logging_config.configure_logging`
- `app.api.routes.sap_automation.router`

### `app/api/routes/sap_automation.py`

Responsabilidades:

- Define contrato HTTP da automacao SAP (`POST /api/v1/sap/run`).
- Valida payload com Pydantic:
  - aliases: `start_date`/`startDate`, `end_date`/`endDate`
  - formatos de data aceitos: `YYYY-MM-DD`, `DD.MM.YYYY`, `DD/MM/YYYY`
- Cria `SapRunCommand` e delega para `SapAutomationOrchestrator`.
- Traduz erros de dominio em `HTTPException`.

Modelos:

- `SapAutomationRequest`
- `SapAutomationResponse`

## 2. Configuracao e Logging

### `app/core/settings.py`

Responsabilidades:

- Carrega variaveis do `.env` (`python-dotenv`).
- Resolve caminhos relativos para raiz do projeto.
- Monta defaults operacionais para API SAP.
- Separa diretorios por transacao:
  - `sap_zucrm_export_dir` (`downloads/zucrm039`)
  - `sap_iw59_export_dir` (`downloads/iw59`)
- Valida credenciais obrigatorias (`SAP_USERNAME`, `SAP_PASSWORD`).
- Expoe singleton cacheado via `get_settings()`.

Observacoes:

- `sap_export_dir` e mantido como pasta base para derivar subpastas por transacao.
- Variaveis `SAP_ZUCRM_EXPORT_DIR` e `SAP_IW59_EXPORT_DIR` podem sobrescrever os defaults.

### `app/core/logging_config.py`

Responsabilidades:

- Configura logger root uma unica vez.
- Injeta `request_id` em todos os registros via `ContextVar` + `logging.Filter`.
- Escreve logs em console e arquivo rotativo:
  - `maxBytes=5_000_000`
  - `backupCount=5`

APIs publicas:

- `configure_logging(settings)`
- `set_request_id(value)`
- `reset_request_id(token)`
- `get_request_id()`

## 3. Dominio SAP (Automacao)

### `app/sap/models.py`

Modelos imutaveis de comando e retorno:

- `SapRunCommand(start_date, end_date)`
- `SapRunResult(zucrm_export_file, iw59_export_file, notes_count)`

### `app/sap/exceptions.py`

Hierarquia de excecoes de dominio:

- `SapAutomationError`
- `SapExportTimeoutError`

### `app/sap/dependencies.py`

Composicao de dependencias (DIP):

- Cria watchers separados por transacao.
- Injeta implementacoes concretas no `SapAutomationOrchestrator`.
- Centraliza a montagem dos servicos usados pela rota.

### `app/sap/orchestrator.py`

Orquestracao de alto nivel (use case principal):

1. Valida periodo e credenciais.
2. Conecta + loga no SAP.
3. Executa ZUCRM e captura planilha.
4. Extrai notas com regra de negocio.
5. Retorna navegação com F3.
6. Executa IW59 com notas.
7. Devolve caminhos e metrica de quantidade de notas.

### `app/sap/gui_client.py`

Responsabilidades:

- Adaptador de sessao `SapSessionFacade` para encapsular `findById`, `press`, `set_text`, `send_vkey`, etc.
- Conexao com SAP GUI scripting via COM (`win32com.client`).
- Abertura de SAP Logon quando necessario.
- Estrategia de conexao:
  1. reutilizar conexao existente por descricao
  2. tentar `OpenConnection(...)` com candidatos
  3. fallback de UI automation no SAP Logon (`SapLogonUiAutomation`)
- Login automatico quando tela de credenciais esta ativa.

Pontos sensiveis:

- Requer Windows (`os.name == "nt"`).
- Falhas de layout/ID do SAP levantam `SapAutomationError` com ID de controle.

### `app/sap/logon_ui.py`

Fallback de automacao de interface (pywinauto):

- Conecta na janela `SAP Logon*`.
- Seleciona server na arvore esquerda.
- Encontra melhor linha de conexao por score textual na grade da direita.
- Executa duplo clique para abrir sessao.

Estrategia de matching:

- Normalizacao de acentos e simbolos.
- Score por igualdade, substring e tokens comuns.

### `app/sap/transactions.py`

Contem implementacao das transacoes SAP e utilitarios de exportacao.

#### `SapExportDialogService`

- Controla popup de exportacao SAP.
- Seta `DY_PATH` para o diretorio da transacao.
- Confirma salvar (inclui tratamento de overwrite quando popup existe).

#### `Zucrm039TransactionRunner`

Fluxo:

1. Entra na transacao (`okcd`).
2. Preenche filtros (`PC_QMART`, datas, `SC_QMCOD-LOW`, `PC_VARIA`).
3. Executa (`btn[8]`), abre menu de exportacao e salva no diretorio ZUCRM.
4. Detecta arquivo exportado pelo watcher.
5. Se timeout no glob principal, fallback para `export*.xlsx` no diretorio ZUCRM.

#### `SapNavigationService`

- Pressiona `F3` para retorno de tela antes da IW59.
- Politica atual: minimo 3 pressionamentos, maximo 4 (respeitando limite configurado).

#### `Iw59TransactionRunner`

Fluxo:

1. Entra em `iw59`.
2. Aguarda botao de multi-selecao de nota.
3. Cola notas via clipboard (`btn[24]`) e confirma.
4. Executa relatorio.
5. Exporta para diretorio IW59.
6. Gera copia completa com nome `iw59_copia_completa_<timestamp>.xlsx`.

### `app/sap/excel_rules.py`

Regra de negocio para alimentar IW59:

- Detecta coluna equivalente a `Nº Nota/Medida` por normalizacao.
- Filtra `/000`.
- Extrai somente digitos.
- Remove zeros a esquerda via conversao numerica.
- Deduplica mantendo ordem.

### `app/sap/file_watcher.py`

Watcher por diretorio + glob:

- `snapshot()`: baseline de arquivos/mtime.
- `wait_for_export(...)`: aguarda arquivo novo/atualizado apos inicio da exportacao.

### `app/sap/clipboard.py`

- Escreve lista de notas na area de transferencia do Windows (`win32clipboard`).
- Payload formatado em linhas CRLF para colagem no multi-selecao SAP.

## 4. ETL Legado

### `pipeline.py`

Entrada CLI do ETL antigo:

- Descobre arquivos SAP (`sap_gov_sp_*.XLSX`).
- Extrai SAP + BRS (`etl.extract`).
- Faz merge por nota.
- Transforma (`etl.transform`).
- Carrega banco (`etl.load`).

Modos:

- `--file`
- `--period`
- `--all`

### `etl/extract/extract.py`

- Le planilhas com `openpyxl` e `dtype=str`.
- Remove linhas totalmente vazias e limpa nomes de coluna.
- Remove apostrofo inicial de celulas textuais (`'valor`).
- Resolve arquivo BRS correspondente por nome (`YYYYMM` ou `atual`).

### `etl/transform/transform.py`

Responsabilidades centrais:

- Parse de datas e composicao data+hora.
- Filtro de medidas (`/000`) e normalizacao de notas numericas.
- Reconstrucao opcional de `protocolo_gov_zucrm` quando invalido.
- Renomeacao de colunas com mappings em `utils/contants.py`.
- Manutencao apenas das colunas esperadas pelo modelo.
- Limpeza final de valores vazios/nulos.

### `etl/load/load.py`

- Garante existencia de tabela (`create_tables`).
- Remove registros antigos por `data_inicio_zucrm` antes de inserir.
- Insercao em lote com `to_sql(method='multi')`.

## 5. Banco e Modelo

### `config/config.py`

- Configuracao do ETL legado (DB + `FILE_HISTORY_DIR`).
- Carrega `.env` diretamente.

### `database/connection.py`

- Monta connection string ODBC SQL Server.
- Cria `engine` com `fast_executemany`.
- Executa ajuste de schema para `protocolo_gov_zucrm` como texto (`NVARCHAR`).

### `database/model.py`

Modelo `SapGovSP` (`ouvidoria_sap_sp`) com:

- campos de ZUCRM (`*_zucrm`)
- campos de IW59 (`*_iw59`)
- indice em `data_inicio_zucrm`

## 6. Utilitarios

### `utils/contants.py`

- Dicionarios de mapeamento de colunas originais para nomes padronizados (`COLUMN_MAPPING_ZUCRM`, `COLUMN_MAPPING_IW59`).
- Caminhos utilitarios (`PROJECT_ROOT`).

## 7. Scripts de Teste/Inspecao

Pasta `test/` contem scripts manuais de validacao/inspecao (nao sao testes automatizados com framework):

- `extract_protocolos.py`
- `inspect_xlsx.py`
- `inspect_gov_column.py`

## 8. Pontos de Extensao Recomendados

- Adicionar retries e esperas parametrizaveis por etapa SAP em `transactions.py`.
- Isolar IDs de tela SAP em mapeamento externo para facilitar manutencao por mudanca de layout.
- Cobertura de testes automatizados para regras de negocio (`excel_rules.py`, `transform.py`).
- Criar endpoint de dry-run para validar configuracao SAP sem executar transacao completa.
