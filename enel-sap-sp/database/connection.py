"""
Módulo de conexão com o banco de dados SQL Server.
"""
import logging
import urllib.parse
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from config.config import Config
from database.model import Base

logger = logging.getLogger(__name__)


def get_connection_string() -> str:
    """Retorna a string de conexão para o SQL Server usando ODBC."""
    params = urllib.parse.quote_plus(
        f"DRIVER={{{Config.DB_DRIVER}}};"
        f"SERVER={Config.DB_SERVER};"
        f"DATABASE={Config.DB_DATABASE};"
        f"UID={Config.DB_USER};"
        f"PWD={Config.DB_PASSWORD};"
        f"Encrypt=no;" #ALTERAR PARA YES EM PRODUÇÃO
        f"TrustServerCertificate=no;" #COMENTAR EM PRODUÇÃO, USAR APENAS SE NECESSÁRIO PARA TESTES LOCAIS COM CERTIFICADO AUTOASSINADO
    )
    return f"mssql+pyodbc:///?odbc_connect={params}"


def get_engine():
    """Cria e retorna o engine do SQLAlchemy com fast_executemany."""
    connection_string = get_connection_string()
    engine = create_engine(connection_string, fast_executemany=True)

    # Configurar evento para ajustar setinputsizes antes de executemany
    # Isso permite que strings longas (NVARCHAR MAX) funcionem com fast_executemany
    @event.listens_for(engine, "before_cursor_execute")
    def set_input_sizes(conn, cursor, statement, parameters, context, executemany):
        if executemany:
            cursor.fast_executemany = True
            cursor.setinputsizes(None)

    return engine


def get_session():
    """Cria e retorna uma sessão do SQLAlchemy."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def create_tables():
    """Cria as tabelas no banco de dados se não existirem.
    Também garante que colunas de protocolo sejam do tipo texto (nvarchar) para preservar zeros."""
    engine = get_engine()
    Base.metadata.create_all(engine)

    # Garante que protocolo_gov_zucrm seja nvarchar (texto) e não numérico,
    # para preservar o zero do mês (ex: 20260100013198887 e não 2026100013198887)
    fix_sql = """
    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ouvidoria_sap_sp'
          AND COLUMN_NAME = 'protocolo_gov_zucrm'
          AND DATA_TYPE NOT IN ('nvarchar', 'varchar', 'text', 'ntext', 'char', 'nchar')
    )
    BEGIN
        ALTER TABLE ouvidoria_sap_sp ALTER COLUMN protocolo_gov_zucrm NVARCHAR(50);
    END
    """
    with engine.connect() as conn:
        conn.execute(text(fix_sql))
        conn.commit()

    logger.info("Tabelas criadas/verificadas")
