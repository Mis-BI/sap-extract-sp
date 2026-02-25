from sqlalchemy import Column, Integer, String, DateTime, Date, Index, Text, BigInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SapGovSP(Base):
    """
    Modelo de dados combinado das transações ZUCRM_039 (sap_gov_sp) e IW59 (brs_sap_gov_sp).
    """
    __tablename__ = 'ouvidoria_sap_sp'

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # ========================================
    # Dados da transação ZUCRM_039 (sap_gov_sp)
    # ========================================
    numero_nota_medida_zucrm = Column(Text)  # Nº Nota/Medida (convertido para número)
    numero_sgo_zucrm = Column(Text)  # N.SGO
    cip_zucrm = Column(Text)  # CIP
    protocolo_gov_zucrm = Column(Text)  # Protocolo GOV
    protocolo_gov_zucrm_original = Column(Text)  # Protocolo GOV original (antes de possível reconstrução)
    numero_parceiro_zucrm = Column(Text)  # Nº Parceiro
    instalacao_zucrm = Column(Text)  # Instalação
    motivo_zucrm = Column(Text)  # Motivo
    assunto_zucrm = Column(Text)  # Assunto
    processo_zucrm = Column(Text)  # Processo
    origem_zucrm = Column(Text)  # Origem
    meio_de_contato_zucrm = Column(Text)  # Meio de Contato
    nota_revisada_zucrm = Column(Text)  # Nota Revisada
    status_zucrm = Column(Text)  # Status
    providencia_zucrm = Column(Text)  # Providência
    status_anterior_zucrm = Column(Text)  # Status Anterior
    data_sage_zucrm = Column(Date)  # Data SAGE
    data_inicio_zucrm = Column(Date)  # Data Início
    data_fim_zucrm = Column(Date)  # Data Fim
    data_encerramento_zucrm = Column(Date)  # Data de Encerramento
    localidade_zucrm = Column(Text)  # Localidade
    regional_zucrm = Column(Text)  # Regional


    # ========================================
    # Dados da transação IW59 (brs_sap_gov_sp)
    # ========================================
    tipo_de_nota_iw59 = Column(Text)  # Tipo de nota
    nota_iw59 = Column(Text)  # Nota
    notificador_iw59 = Column(Text)  # Notificador
    status_usuario_iw59 = Column(Text)  # Status usuário
    modificado_por_iw59 = Column(Text)  # Modificado por
    data_criacao_iw59 = Column(Date)  # Dt.criação
    data_hora_inicio_avaria_iw59 = Column(DateTime)  # InícioAvar + HoraInícioAvar (combinados)
    data_hora_inicio_desejado_iw59 = Column(DateTime)  # Início desejado + Hora iníc.des. (combinados)
    data_conclusao_desejada_iw59 = Column(Date)  # Concl.desejada
    data_hora_fim_avaria_iw59 = Column(DateTime)  # Fim avaria + Hora fim avaria (combinados)
    data_encerramento_iw59 = Column(Date)  # Data encermto.
    data_modificado_em_iw59 = Column(Date)  # Modificado em
    instalacao_iw59 = Column(Text)  # Instalação
    cliente_iw59 = Column(Text)  # Cliente
    descricao_iw59 = Column(Text)  # Descrição
    cidade_iw59 = Column(Text)  # Cidade
    rua_iw59 = Column(Text)  # Rua
    bairro_iw59 = Column(Text)  # Bairro
    numero_endereco_iw59 = Column(Text)  # Nº endereço

    # Índice para busca por data de início (data de abertura)
    __table_args__ = (
        Index('ix_sap_gov_sp_data_inicio', 'data_inicio_zucrm'),
    )