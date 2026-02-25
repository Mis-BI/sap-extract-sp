import logging
from typing import List, Optional
import numpy as np
import pandas as pd
from utils.contants import COLUMN_MAPPING_ZUCRM, COLUMN_MAPPING_IW59

logger = logging.getLogger(__name__)

def parse_date(date_value) -> Optional[pd.Timestamp]:
    """
    Converte string de data para datetime (apenas data, sem hora).
    """
    if pd.isna(date_value) or str(date_value).strip() == '':
        return None
    try:
        date_str = str(date_value).strip()
        # Remove hora se houver
        if ' ' in date_str:
            date_str = date_str.split(' ')[0]

        # ISO YYYY-MM-DD
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            return pd.to_datetime(date_str, format='%Y-%m-%d')
        # DD/MM/YYYY
        if '/' in date_str:
            return pd.to_datetime(date_str, format='%d/%m/%Y')
        # DD.MM.YYYY
        if '.' in date_str:
            return pd.to_datetime(date_str, format='%d.%m.%Y')
        # fallback
        return pd.to_datetime(date_str, dayfirst=True)
    except Exception:
        return None

def combine_date_time(date_value, time_value) -> Optional[pd.Timestamp]:
    """
    Combina colunas de data e hora em um único datetime.
    """
    if pd.isna(date_value) or str(date_value).strip() == '':
        return None
    try:
        date_str = str(date_value).strip()
        if ' ' in date_str:
            date_str = date_str.split(' ')[0]

        # Identifica formato da data
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            date_format = '%Y-%m-%d'
        elif '/' in date_str:
            date_format = '%d/%m/%Y'
        elif '.' in date_str:
            date_format = '%d.%m.%Y'
        else:
            date_format = '%Y-%m-%d'

        # Se há hora
        if pd.notna(time_value) and str(time_value).strip() != '':
            time_str = str(time_value).strip()
            if time_str.count(':') == 1:
                time_str += ':00'
            datetime_str = f"{date_str} {time_str}"
            datetime_format = f"{date_format} %H:%M:%S"
            return pd.to_datetime(datetime_str, format=datetime_format)
        else:
            return pd.to_datetime(date_str, format=date_format)
    except Exception:
        return None

def filter_notas_only(df: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas com '/000' na coluna 'Nº Nota/Medida'."""
    col = 'Nº Nota/Medida'
    if col not in df.columns:
        return df
    before = len(df)
    df = df[~df[col].astype(str).str.contains('/000', na=False)].copy()
    logger.info("Medidas removidas: %d", before - len(df))
    return df


def convert_nota_to_number(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    """
    Remove zeros à esquerda de uma coluna que contém números formatados como string.

    A função extrai apenas os dígitos da coluna, converte para número inteiro
    e depois retorna como string sem zeros à esquerda. Valores inválidos tornam-se None.

    Parâmetros:
    df : pd.DataFrame
        DataFrame de entrada.
    col_name : str
        Nome da coluna a ser processada.

    Retorna:
    pd.DataFrame
        DataFrame com a coluna modificada.
    """
    if col_name not in df.columns:
        return df

    numeric = pd.to_numeric(
        df[col_name].astype(str).str.replace(r'\D', '', regex=True),
        errors='coerce'
    )

    df[col_name] = numeric.apply(lambda x: str(int(x)) if pd.notna(x) else None)

    return df

def reconstruct_protocolo_gov(df: pd.DataFrame) -> pd.DataFrame:
    cols = ['protocolo_gov_zucrm', 'numero_sgo_zucrm', 'data_inicio_zucrm', 'origem_zucrm']
    if not all(c in df.columns for c in cols):
        return df

    df['protocolo_gov_zucrm_original'] = df['protocolo_gov_zucrm']

    protocolo_str = df['protocolo_gov_zucrm'].astype(str).str.strip()

    mask = (
            (
            protocolo_str.isin(['0', '0.0', '', 'None', 'nan']) |  # Zerados OU
            (protocolo_str.str.len() != 17) # Tamanho diferente de 17
            ) &
            (df['origem_zucrm'].astype(str).str.strip().str.upper() == 'GOV') &
            df['numero_sgo_zucrm'].notna() &
            (df['numero_sgo_zucrm'].astype(str).str.strip() != '')
    )

    if not mask.any():
        return df

    df = df.copy()
    subset = df.loc[mask, ['data_inicio_zucrm', 'numero_sgo_zucrm']].copy()

    datas = pd.to_datetime(subset['data_inicio_zucrm'], errors='coerce')
    ano_mes = datas.dt.strftime('%Y%m')

    nsgo_limpo = subset['numero_sgo_zucrm'].astype(str).str.replace(r'\D', '', regex=True)
    ultimos_11 = nsgo_limpo.str[-11:]

    valido = datas.notna() & (nsgo_limpo.str.len() >= 11)
    protocolos = (ano_mes + ultimos_11).where(valido, np.nan)

    # Corrige protocolos com 16 dígitos inserindo '0' após os primeiros 4 dígitos (ano)
    def fix_protocolo(p):
        if pd.isna(p):
            return p
        p = str(p)
        if len(p) == 16:
            p = p[:4] + '0' + p[4:]
        return p

    protocolos = protocolos.apply(fix_protocolo)

    df.loc[mask, 'protocolo_gov_zucrm'] = protocolos.values
    return df


def rename_columns(df: pd.DataFrame, mapping: dict, source_name: str) -> pd.DataFrame:
    """Renomeia colunas conforme mapping (apenas as existentes)."""
    to_rename = {k: v for k, v in mapping.items() if k in df.columns}
    if to_rename:
        df = df.rename(columns=to_rename)
        logger.info("%d colunas do %s renomeadas", len(to_rename), source_name)
    return df

def rename_columns_zucrm(df: pd.DataFrame) -> pd.DataFrame:
    return rename_columns(df, COLUMN_MAPPING_ZUCRM, "ZUCRM")

def rename_columns_iw59(df: pd.DataFrame) -> pd.DataFrame:
    return rename_columns(df, COLUMN_MAPPING_IW59, "IW59")

def convert_and_combine_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converte colunas de data simples e combina pares data+hora.
    Assume que as colunas já estão com os nomes do banco.
    """
    # Colunas de data simples do ZUCRM
    for col in ['data_sage_zucrm', 'data_inicio_zucrm', 'data_fim_zucrm', 'data_encerramento_zucrm']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col].apply(parse_date), errors='coerce').dt.date

    # Colunas de data simples do IW59
    for col in ['data_criacao_iw59', 'data_conclusao_desejada_iw59',
                'data_encerramento_iw59', 'data_modificado_em_iw59']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col].apply(parse_date), errors='coerce').dt.date

    # Pares data+hora do IW59
    pairs = [
        ('inicio_avaria_date_iw59', 'inicio_avaria_time_iw59', 'data_hora_inicio_avaria_iw59'),
        ('inicio_desejado_date_iw59', 'inicio_desejado_time_iw59', 'data_hora_inicio_desejado_iw59'),
        ('fim_avaria_date_iw59', 'fim_avaria_time_iw59', 'data_hora_fim_avaria_iw59'),
    ]
    for date_col, time_col, target in pairs:
        if date_col in df.columns:
            df[target] = df.apply(
                lambda row: combine_date_time(row.get(date_col), row.get(time_col)),
                axis=1
            )
            df[target] = pd.to_datetime(df[target], errors='coerce')
            drop_cols = [c for c in (date_col, time_col) if c in df.columns]
            df = df.drop(columns=drop_cols)

    return df

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Remove espaços extras de strings e substitui valores vazios por None."""
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].apply(lambda x: str(x).strip() if pd.notna(x) else None)

    df = df.replace(['', 'nan', 'None', 'NaT'], None)
    return df

def keep_model_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém apenas as colunas definidas no modelo do banco."""
    valid_columns = [
        # ZUCRM
        'numero_nota_medida_zucrm', 'numero_sgo_zucrm', 'cip_zucrm', 'protocolo_gov_zucrm',
        'numero_parceiro_zucrm', 'instalacao_zucrm', 'motivo_zucrm', 'assunto_zucrm',
        'processo_zucrm', 'origem_zucrm', 'meio_de_contato_zucrm', 'nota_revisada_zucrm',
        'status_zucrm', 'providencia_zucrm', 'status_anterior_zucrm', 'data_sage_zucrm',
        'data_inicio_zucrm', 'data_fim_zucrm', 'data_encerramento_zucrm', 'localidade_zucrm',
        'regional_zucrm',
        # IW59
        'tipo_de_nota_iw59', 'nota_iw59', 'notificador_iw59', 'status_usuario_iw59',
        'modificado_por_iw59', 'data_criacao_iw59', 'data_hora_inicio_avaria_iw59',
        'data_hora_inicio_desejado_iw59', 'data_conclusao_desejada_iw59',
        'data_hora_fim_avaria_iw59', 'data_encerramento_iw59', 'data_modificado_em_iw59',
        'instalacao_iw59', 'cliente_iw59', 'descricao_iw59', 'cidade_iw59',
        'rua_iw59', 'bairro_iw59', 'numero_endereco_iw59',
    ]
    existing = [c for c in valid_columns if c in df.columns]
    return df[existing].copy()


def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Iniciando transformações...")
    df = rename_columns_zucrm(df)
    df = rename_columns_iw59(df)
    df = reconstruct_protocolo_gov(df)
    df = convert_and_combine_dates(df)

    if 'Nota' in df.columns:
        df = df.drop(columns=['Nota'])

    df = keep_model_columns(df)
    df = clean_dataframe(df)
    logger.info("Transformações concluídas: %d registros", len(df))
    return df

def get_unique_dates_from_transformed(df: pd.DataFrame) -> List:
    """Retorna datas únicas de 'data_inicio_zucrm'."""
    if 'data_inicio_zucrm' not in df.columns:
        return []
    dates = pd.to_datetime(df['data_inicio_zucrm']).dropna().dt.date.unique()
    return sorted(dates)