import os
import logging
import re
from typing import List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def read_excel(file_path: str, **kwargs) -> pd.DataFrame:
    """
    Lê um arquivo Excel e retorna um DataFrame com dados brutos.
    """
    df = pd.read_excel(file_path, dtype=str, engine='openpyxl', **kwargs)
    df = df.dropna(how='all')
    df.columns = df.columns.str.strip()

    # Remove aspas simples iniciais geradas pelo Excel (prefixo de texto forçado)
    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: x[1:] if isinstance(x, str) and x.startswith("'") else x
        )

    logger.info("Lido %s — %d registros", os.path.basename(file_path), len(df))
    return df


def get_corresponding_brs_file(sap_file_path: str) -> Optional[str]:
    """
    Dado um arquivo sap_gov_sp, retorna o caminho do arquivo brs correspondente.
    """
    directory = os.path.dirname(sap_file_path)
    filename = os.path.basename(sap_file_path)

    match_period = re.search(r'sap_gov_sp_(\d{6})\.XLSX', filename, re.IGNORECASE)

    if match_period:
        brs_filename = f"brs_sap_gov_sp_{match_period.group(1)}.XLSX"
    else:
        match_atual = re.search(r'sap_gov_sp_(atual)\.XLSX', filename, re.IGNORECASE)
        if match_atual:
            brs_filename = "brs_sap_gov_sp_atual.XLSX"
        else:
            logger.warning("Padrão não reconhecido: %s", filename)
            return None

    brs_path = os.path.join(directory, brs_filename)

    if os.path.exists(brs_path):
        return brs_path

    logger.warning("BRS não encontrado: %s", brs_filename)
    return None


def extract_sap_and_brs(sap_file_path: str) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """
    Lê o arquivo SAP (ZUCRM_039) e, se existir, o arquivo BRS (IW59) correspondente.
    """
    df_sap = read_excel(sap_file_path)
    brs_path = get_corresponding_brs_file(sap_file_path)
    df_brs = read_excel(brs_path) if brs_path else None
    return df_sap, df_brs


def extract_multiple_files(sap_file_paths: List[str]) -> Tuple[List[pd.DataFrame], List[Optional[pd.DataFrame]]]:
    """
    Lê múltiplos arquivos SAP e seus respectivos BRS (quando disponíveis).
    """
    if not sap_file_paths:
        logger.warning("Nenhum arquivo para processar")
        return [], []

    dfs_sap = []
    dfs_brs = []

    for file_path in sap_file_paths:
        df_sap, df_brs = extract_sap_and_brs(file_path)
        dfs_sap.append(df_sap)
        dfs_brs.append(df_brs)

    logger.info("Total de arquivos processados: %d", len(sap_file_paths))
    return dfs_sap, dfs_brs