import pandas as pd
from etl.transform.transform import reconstruct_protocolo_gov

teste = pd.DataFrame({
    'Protocolo GOV': ['0'],
    'N.SGO': ['100013198887'],
    'Data Início': ['19/01/2026'],
    'Origem': ['Gov']
})
resultado = reconstruct_protocolo_gov(teste)
print(resultado['Protocolo GOV'].iloc[0])  # Deve imprimir: 20260100013198887


