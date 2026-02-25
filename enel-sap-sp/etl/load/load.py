"""
Módulo de carga de dados no banco de dados.
"""
import logging
from typing import List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy import Text as SQLText

from database.connection import get_engine, create_tables

logger = logging.getLogger(__name__)

# Nome da tabela no banco de dados
TABLE_NAME = 'ouvidoria_sap_sp'


def load_dataframe_to_db(df: pd.DataFrame, datas_inicio: Optional[List] = None) -> dict:
    """
    Carrega um DataFrame para o banco de dados.
    Deleta registros existentes com as mesmas datas de início (abertura) antes de inserir.
    """
    create_tables()

    engine = get_engine()
    stats = {
        'deleted': 0,
        'inserted': 0,
    }

    # Deleta registros com as mesmas datas de início (data de abertura)
    if datas_inicio:
        with engine.connect() as conn:
            for data in datas_inicio:
                if data is not None:
                    result = conn.execute(
                        text(f"DELETE FROM {TABLE_NAME} WHERE data_inicio_zucrm = :data"),
                        {"data": data}
                    )
                    stats['deleted'] += result.rowcount
            conn.commit()
        logger.info("%d registros removidos", stats['deleted'])

    # Insere os dados
    try:
        num_columns = len(df.columns)
        max_params = 2000
        optimal_chunksize = max(1, max_params // num_columns)

        df.to_sql(
            name=TABLE_NAME,
            con=engine,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=optimal_chunksize,
            dtype={'protocolo_gov_zucrm': SQLText()},
        )

        stats['inserted'] = len(df)
        logger.info("%d registros inseridos", stats['inserted'])

    except Exception as e:
        logger.error("Erro na inserção: %s", e)
        raise

    return stats


def get_record_count() -> int:
    """
    Retorna a contagem de registros na tabela.
    """
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME}"))
        return result.scalar()