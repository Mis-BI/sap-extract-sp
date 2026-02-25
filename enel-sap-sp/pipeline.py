"""
Script principal para executar o ETL.
Extrai, transforma e carrega dados das transações SAP para o banco de dados.
"""
import os
import sys
import glob
import logging
import argparse

import pandas as pd

from config.config import Config
from etl.extract.extract import extract_sap_and_brs, extract_multiple_files
from etl.transform.transform import transform_data, get_unique_dates_from_transformed, filter_notas_only, convert_nota_to_number
from etl.load.load import load_dataframe_to_db, get_record_count

logger = logging.getLogger(__name__)


def find_sap_files(directory: str, period: str = None) -> list:
    """
    Encontra arquivos sap_gov_sp no diretório.
    """
    if period:
        pattern = os.path.join(directory, f"sap_gov_sp_{period}.XLSX")
    else:
        pattern = os.path.join(directory, "sap_gov_sp_*.XLSX")

    files = glob.glob(pattern, recursive=False)
    files = [f for f in files if not os.path.basename(f).startswith('brs_')]
    return sorted(files)


def _merge_sap_brs(df_sap: pd.DataFrame, df_brs: pd.DataFrame | None) -> pd.DataFrame:
    """
    Faz o merge entre SAP (ZUCRM) e BRS (IW59) pela coluna Nº Nota/Medida / Nota.
    Prioriza sempre os dados do SAP (ZUCRM) em caso de colunas duplicadas.
    """
    if df_brs is None or df_brs.empty:
        return df_sap

    df_sap = filter_notas_only(df_sap)
    df_sap = convert_nota_to_number(df_sap, 'Nº Nota/Medida' )
    df_brs = convert_nota_to_number(df_brs, 'Nota')
    # Renomeia coluna Instalação do BRS para evitar conflito
    if 'Instalação' in df_brs.columns:
        df_brs = df_brs.rename(columns={'Instalação': 'Instalação_brs'})

    # NOVA SEÇÃO: Força sufixo _brs em TODAS as colunas comuns (exceto coluna de merge)
    merge_col_sap = 'Nº Nota/Medida'
    merge_col_brs = 'Nota'


    common_cols = set(df_sap.columns) & set(df_brs.columns)
    common_cols.discard(merge_col_brs)  # não renomear a coluna de merge

    rename_dict = {col: f"{col}_brs" for col in common_cols}
    if rename_dict:
        df_brs = df_brs.rename(columns=rename_dict)
        logger.info("Colunas BRS renomeadas para evitar conflito: %s", list(rename_dict.keys()))

    if merge_col_sap not in df_sap.columns or merge_col_brs not in df_brs.columns:
        logger.warning("Colunas de merge não encontradas, retornando apenas SAP")
        return df_sap

    df_sap[merge_col_sap] = df_sap[merge_col_sap].astype(str).str.strip()
    df_brs[merge_col_brs] = df_brs[merge_col_brs].astype(str).str.strip()

    df = pd.merge(df_sap, df_brs, left_on=merge_col_sap, right_on=merge_col_brs, how='left', suffixes=('', '_brs'))

    # Remove colunas _brs duplicadas (mantém a original do SAP)
    cols_brs = [c for c in df.columns if c.endswith('_brs') and c != 'Instalação_brs']
    df = df.drop(columns=cols_brs)

    return df

def run_etl(file_path: str = None, period: str = None, all_files: bool = False):
    """
    Executa o pipeline ETL completo.
    """
    logger.info("Iniciando ETL - SAP GOV SP")

    # Determina os arquivos a processar
    if file_path:
        files_to_process = [file_path]
    elif period:
        files_to_process = find_sap_files(Config.FILE_HISTORY_DIR, period)
        if not files_to_process:
            logger.error("Nenhum arquivo encontrado para o período %s", period)
            return
    elif all_files:
        files_to_process = find_sap_files(Config.FILE_HISTORY_DIR)
        if not files_to_process:
            logger.error("Nenhum arquivo sap_gov_sp encontrado em %s", Config.FILE_HISTORY_DIR)
            return
    else:
        logger.error("Especifique um arquivo, período ou use --all")
        return

    logger.info("Arquivos a processar: %d", len(files_to_process))

    # EXTRAÇÃO
    if len(files_to_process) == 1:
        df_sap, df_brs = extract_sap_and_brs(files_to_process[0])
        df_raw = _merge_sap_brs(df_sap, df_brs)
    else:
        dfs_sap, dfs_brs = extract_multiple_files(files_to_process)
        merged = [_merge_sap_brs(s, b) for s, b in zip(dfs_sap, dfs_brs)]
        df_raw = pd.concat(merged, ignore_index=True) if merged else pd.DataFrame()

    if df_raw.empty:
        logger.error("Nenhum dado extraído")
        return

    # TRANSFORMAÇÃO
    df_transformed = transform_data(df_raw)

    unique_dates = get_unique_dates_from_transformed(df_transformed)
    logger.info("Datas de abertura: %d | Período: %s a %s",
                len(unique_dates),
                min(unique_dates) if unique_dates else '-',
                max(unique_dates) if unique_dates else '-')

    print(df_transformed['protocolo_gov_zucrm'].dtype)
    print(df_transformed[df_transformed['numero_sgo_zucrm'] == '100013198887']['protocolo_gov_zucrm'].values)
    stats = load_dataframe_to_db(df_transformed, unique_dates)

    logger.info("ETL concluído — processados: %d | deletados: %d | inseridos: %d",
                len(df_transformed), stats['deleted'], stats['inserted'])

    try:
        total = get_record_count()
        logger.info("Total na tabela: %d", total)
    except Exception:
        pass


def main():
    """Ponto de entrada principal."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    parser = argparse.ArgumentParser(
        description='ETL para dados SAP GOV SP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    Exemplos de uso:
      python pipeline.py --file file_history/sap_gov_sp_202501.XLSX
      python pipeline.py --period 202501
      python pipeline.py --all
    """
    )

    parser.add_argument('--file', '-f', type=str, help='Caminho do arquivo sap_gov_sp específico')
    parser.add_argument('--period', '-p', type=str, help='Período no formato YYYYMM (ex: 202501)')
    parser.add_argument('--all', '-a', action='store_true', help='Processa todos os arquivos sap_gov_sp')

    args = parser.parse_args()

    if not (args.file or args.period or args.all):
        parser.print_help()
        sys.exit(1)

    try:
        run_etl(file_path=args.file, period=args.period, all_files=args.all)
    except KeyboardInterrupt:
        logger.warning("Execução cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.exception("Erro durante execução: %s", e)
        raise


if __name__ == '__main__':
    main()
