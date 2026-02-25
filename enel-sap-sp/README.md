# ETL SAP GOV SP

Pipeline ETL para combinar e carregar dados das transações SAP (ZUCRM_039 e IW59) no banco de dados SQL Server.

## Estrutura do Projeto

```
enel-sap-sp/
├── config/
│   └── config.py           # Configurações (banco de dados, diretórios)
├── database/
│   ├── connection.py       # Conexão com SQL Server
│   └── model.py            # Modelo da tabela (SQLAlchemy)
├── etl/
│   ├── extract/
│   │   └── extractor.py    # Extração e combinação dos arquivos XLSX
│   ├── transform/
│   │   └── transformer.py  # Transformação e mapeamento de colunas
│   └── load/
│       └── loader.py       # Carga no banco de dados
├── file_history/           # Diretório dos arquivos XLSX
├── main.py                 # Script principal
├── requirements.txt        # Dependências Python
└── .env                    # Variáveis de ambiente (criar a partir de .env.example)
```

## Arquivos de Entrada

O ETL espera dois arquivos XLSX para cada período:

1. **sap_gov_sp_YYYYMM.XLSX** - Base principal (transação ZUCRM_039)
2. **brs_sap_gov_sp_YYYYMM.XLSX** - Base secundária (transação IW59)

### Tratativas aplicadas:

- Remove linhas que contêm `/000` na coluna "Nº Nota/Medida" (são medidas, não notas)
- Converte "Nº Nota/Medida" para número inteiro
- Combina as bases pelo número da nota (merge left)
- Combina colunas de data e hora em campos DateTime
- Mapeia colunas para nomes padronizados com sufixo da transação (`_zucrm` ou `_iw59`)

## Configuração

1. Copie o arquivo `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edite o `.env` com suas configurações de banco de dados:
   ```
   DB_DRIVER=ODBC Driver 17 for SQL Server
   DB_SERVER=seu_servidor
   DB_DATABASE=seu_banco
   DB_USER=seu_usuario
   DB_PASSWORD=sua_senha
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## API de Automacao SAP

Foi adicionada uma API FastAPI para executar o fluxo completo no SAP GUI:

1. Conecta no `00 SAP ERP` e abre a conexao `H181 RP1 ENEL SP CCS Pr...`
2. Faz login com `SAP_USERNAME` e `SAP_PASSWORD` do `.env`
3. Executa `ZUCRM_039` com os campos:
   - `PC_QMART = ov`
   - intervalo de datas informado na requisicao
   - `SC_QMCOD-LOW = *`
   - `PC_VARIA = /abap ov2`
4. Captura automaticamente o arquivo Excel exportado
5. Aplica a regra de negocio em `Nº Nota/Medida`:
   - remove valores contendo `/000`
   - converte para numero para remover zeros a esquerda
   - deduplica notas
6. Pressiona `F3` repetidamente para voltar da tela de resultado
7. Executa `IW59` e cola as notas no multiselect
8. Executa exportacao final da IW59

### Executar API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Por padrao, `SAP_EXPORT_DIR=downloads`, ou seja, os arquivos exportados sao lidos/escritos em `enel-sap-sp/downloads`.

### Endpoint

`POST /api/v1/sap/run`

Payload:

```json
{
  "start_date": "2026-01-19",
  "end_date": "2026-02-19"
}
```

Resposta:

```json
{
  "status": "success",
  "zucrm_export_file": "C:\\\\Users\\\\...\\\\sap_gov_sp_atual.XLSX",
  "iw59_export_file": "C:\\\\Users\\\\...\\\\brs_sap_gov_sp_atual.XLSX",
  "notes_count": 123
}
```

## Uso

### Processar um arquivo específico:
```bash
python pipeline.py --file file_history/sap_gov_sp_202501.XLSX
```

### Processar por período:
```bash
python pipeline.py --period 202501
```

### Processar todos os arquivos:
```bash
python pipeline.py --all
```

## Comportamento de Carga

Antes de inserir os dados, o ETL **deleta automaticamente** todos os registros no banco que possuem as mesmas **datas de início (abertura)** presentes no arquivo sendo carregado. Isso garante que reprocessamentos não criem duplicatas.

## Colunas no Banco de Dados

### Transação ZUCRM_039 (sufixo `_zucrm`)
| Coluna Original | Coluna no Banco |
|-----------------|-----------------|
| Nº Nota/Medida | numero_nota_medida_zucrm |
| N.SGO | numero_sgo_zucrm |
| CIP | cip_zucrm |
| Protocolo GOV | protocolo_gov_zucrm |
| Nº Parceiro | numero_parceiro_zucrm |
| Instalação | instalacao_zucrm |
| Motivo | motivo_zucrm |
| Assunto | assunto_zucrm |
| Processo | processo_zucrm |
| Origem | origem_zucrm |
| Meio de Contato | meio_de_contato_zucrm |
| Nota Revisada | nota_revisada_zucrm |
| Status | status_zucrm |
| Providência | providencia_zucrm |
| Status Anterior | status_anterior_zucrm |
| Data SAGE | data_sage_zucrm |
| Data Início | data_inicio_zucrm |
| Data Fim | data_fim_zucrm |
| Data de Encerramento | data_encerramento_zucrm |
| Localidade | localidade_zucrm |
| Regional | regional_zucrm |

### Transação IW59 (sufixo `_iw59`)
| Coluna Original | Coluna no Banco |
|-----------------|-----------------|
| Tipo de nota | tipo_de_nota_iw59 |
| Nota | nota_iw59 |
| Notificador | notificador_iw59 |
| Status usuário | status_usuario_iw59 |
| Modificado por | modificado_por_iw59 |
| Dt.criação | data_criacao_iw59 |
| InícioAvar + HoraInícioAvar | data_hora_inicio_avaria_iw59 |
| Início desejado + Hora iníc.des. | data_hora_inicio_desejado_iw59 |
| Concl.desejada | data_conclusao_desejada_iw59 |
| Fim avaria + Hora fim avaria | data_hora_fim_avaria_iw59 |
| Data encermto. | data_encerramento_iw59 |
| Modificado em | data_modificado_em_iw59 |
| Instalação | instalacao_iw59 |
| Cliente | cliente_iw59 |
| Descrição | descricao_iw59 |
| Cidade | cidade_iw59 |
| Rua | rua_iw59 |
| Bairro | bairro_iw59 |
| Nº endereço | numero_endereco_iw59 |
