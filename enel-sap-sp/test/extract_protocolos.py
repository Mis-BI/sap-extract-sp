"""
Script para validar e filtrar protocolos a partir de um arquivo TXT existente.
Filtros: protocolo com tamanho correto (17 dígitos) e N.SGO com 12 dígitos.
"""
import os
import sys
import logging
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def validar_protocolo(protocolo: str) -> bool:
    """Valida se o protocolo tem exatamente 17 dígitos numéricos."""
    return bool(re.fullmatch(r'\d{17}', protocolo))


def validar_nsgc(nsgc: str) -> bool:
    """Valida se o N.SGO tem exatamente 12 dígitos numéricos."""
    return bool(re.fullmatch(r'\d{12}', nsgc))


def processar_txt(input_txt: str, output_txt: str = "protocolos_gov_validados.txt"):
    """
    Lê o TXT de entrada, valida e filtra os dados, e salva novo TXT.
    """
    if not os.path.exists(input_txt):
        logger.error("Arquivo não encontrado: %s", input_txt)
        return

    linhas_validas = []
    linhas_invalidas = []

    with open(input_txt, 'r', encoding='utf-8') as f:
        linhas = f.readlines()

    # Pula cabeçalho se existir
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith('N.SGO') or linha.startswith('-'):
            continue

        partes = linha.split()
        if len(partes) < 2:
            linhas_invalidas.append((linha, "formato inválido"))
            continue

        nsgc = partes[0].strip()
        protocolo = partes[1].strip()

        ok_nsgc = validar_nsgc(nsgc)
        ok_proto = validar_protocolo(protocolo)

        if ok_nsgc and ok_proto:
            linhas_validas.append((nsgc, protocolo))
        else:
            motivo = []
            if not ok_nsgc:
                motivo.append(f"N.SGO inválido ({len(nsgc)} dígitos)")
            if not ok_proto:
                motivo.append(f"Protocolo inválido ({len(protocolo)} dígitos)")
            linhas_invalidas.append((linha, " | ".join(motivo)))

    logger.info("Total lido: %d linhas", len(linhas_validas) + len(linhas_invalidas))
    logger.info("Válidos: %d", len(linhas_validas))
    logger.info("Inválidos: %d", len(linhas_invalidas))

    # Salva válidos
    output_path = os.path.join(os.path.dirname(input_txt), output_txt)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"{'N.SGO':<25} {'Protocolo GOV'}\n")
        f.write("-" * 50 + "\n")
        for nsgc, protocolo in linhas_validas:
            f.write(f"{nsgc:<25} {protocolo}\n")
    logger.info("Arquivo validado salvo em: %s", output_path)

    # Salva inválidos para revisão
    invalid_path = os.path.join(os.path.dirname(input_txt), "protocolos_invalidos.txt")
    with open(invalid_path, 'w', encoding='utf-8') as f:
        f.write(f"{'Linha original':<50} {'Motivo'}\n")
        f.write("-" * 80 + "\n")
        for linha, motivo in linhas_invalidas:
            f.write(f"{linha:<50} {motivo}\n")
    logger.info("Inválidos salvos em: %s", invalid_path)

    print(f"\n✅ Válidos: {len(linhas_validas)}")
    print(f"❌ Inválidos: {len(linhas_invalidas)}")


if __name__ == '__main__':
    # Passa o caminho do TXT como argumento ou usa o padrão
    input_file = sys.argv[1] if len(sys.argv) > 1 else "protocolos_gov.txt"
    processar_txt(input_file)
