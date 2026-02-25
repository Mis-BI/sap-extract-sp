from etl.extract.extract import read_excel
from utils.contants import PROJECT_ROOT

file_xlsx_zucrm = 'sap_gov_sp_atual.XLSX'
file_xlsx_iw59 = 'brs_sap_gov_sp_atual.XLSX'

file_path = PROJECT_ROOT / 'file_history' / file_xlsx_iw59
dataframe = read_excel(file_path)
print('debug')


