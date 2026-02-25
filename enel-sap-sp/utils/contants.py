from pathlib import Path

COLUMN_MAPPING_ZUCRM = {
    'Nº Nota/Medida': 'numero_nota_medida_zucrm',
    'N.SGO': 'numero_sgo_zucrm',
    'CIP': 'cip_zucrm',
    'Protocolo GOV': 'protocolo_gov_zucrm',
    'Nº Parceiro': 'numero_parceiro_zucrm',
    'Instalação': 'instalacao_zucrm',
    'Motivo': 'motivo_zucrm',
    'Assunto': 'assunto_zucrm',
    'Processo': 'processo_zucrm',
    'Origem': 'origem_zucrm',
    'Meio de Contato': 'meio_de_contato_zucrm',
    'Nota Revisada': 'nota_revisada_zucrm',
    'Status': 'status_zucrm',
    'Providência': 'providencia_zucrm',
    'Status Anterior': 'status_anterior_zucrm',
    'Data SAGE': 'data_sage_zucrm',
    'Data Início': 'data_inicio_zucrm',
    'Data Fim': 'data_fim_zucrm',
    'Data de Encerramento': 'data_encerramento_zucrm',
    'Localidade': 'localidade_zucrm',
    'Regional': 'regional_zucrm',
}

COLUMN_MAPPING_IW59 = {
    'Tipo de nota': 'tipo_de_nota_iw59',
    'Nota': 'nota_iw59',
    'Notificador': 'notificador_iw59',
    'Status usuário': 'status_usuario_iw59',
    'Modificado por': 'modificado_por_iw59',
    'Dt.criação': 'data_criacao_iw59',
    'InícioAvar': 'inicio_avaria_date_iw59',  # Será combinado com hora
    'HoraInícioAvar.': 'inicio_avaria_time_iw59',  # Será combinado
    'Início desejado': 'inicio_desejado_date_iw59',  # Será combinado com hora
    'Hora iníc.des.': 'inicio_desejado_time_iw59',  # Será combinado
    'Concl.desejada': 'data_conclusao_desejada_iw59',
    'Fim avaria': 'fim_avaria_date_iw59',  # Será combinado com hora
    'Hora fim avaria': 'fim_avaria_time_iw59',  # Será combinado
    'Data encermto.': 'data_encerramento_iw59',
    'Modificado em': 'data_modificado_em_iw59',
    'Instalação_brs': 'instalacao_iw59',  # Fica com sufixo _brs após merge (conflito com coluna ZUCRM)
    'Cliente': 'cliente_iw59',
    'Descrição': 'descricao_iw59',
    'Cidade': 'cidade_iw59',
    'Rua': 'rua_iw59',
    'Bairro': 'bairro_iw59',
    'Nº endereço': 'numero_endereco_iw59',
}

SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
