"""
Configurações do projeto.
Carrega variáveis de ambiente do arquivo .env
"""
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()


class Config:
    """Configurações do banco de dados e aplicação."""
    
    # Configurações do SQL Server
    DB_DRIVER = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
    DB_SERVER = os.getenv('DB_SERVER', 'localhost')
    DB_DATABASE = os.getenv('DB_DATABASE', 'enel_sap')
    DB_USER = os.getenv('DB_USER', 'sa')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    
    # Diretório dos arquivos
    FILE_HISTORY_DIR = os.getenv(
        'FILE_HISTORY_DIR', 
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'file_history')
    )
