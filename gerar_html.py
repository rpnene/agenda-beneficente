#!/usr/bin/env python3
"""
Roda diariamente. NÃO usa a API da Anthropic — apenas lê a planilha
(abas Eventos_IA e Eventos_Manual) e gera agenda_beneficente.html.

Requer variável de ambiente:
  GOOGLE_SERVICE_ACCOUNT_JSON
"""

import datetime

from comum import proximos_finais_de_semana, gerar_html
from planilha import conectar, ler_eventos_ia, ler_eventos_manual

MESES_A_FRENTE = 12

# Link do Google Forms de reserva, com placeholder {DATA}.
URL_FORMULARIO_RESERVA = "https://docs.google.com/forms/d/e/1FAIpQLSflqHKK92JjpM99WjjWSluANqimWKm8rj_vfKPec_97Fbm7xA/viewform?usp=pp_url&entry.1859357884={DATA}"


def normalizar(linha):
    """Converte uma linha da planilha (chaves com nomes de coluna em PT)
    para o formato esperado por comum.gerar_html (chaves em snake_case)."""
    return {
        "data": str(linha.get("Data", "")).strip(),
        "dia_semana": "",
        "cidade": str(linha.get("Cidade", "")).strip(),
        "nome_evento": str(linha.get("Nome do evento", "")).strip(),
        "local": str(linha.get("Local", "")).strip(),
        "horario": str(linha.get("Horário", "A confirmar")).strip() or "A confirmar",
        "entidade_beneficiada": str(linha.get("Entidade promotora", "")).strip(),
        "fonte": str(linha.get("Fonte", "")).strip(),
    }


def main():
    finais = proximos_finais_de_semana(MESES_A_FRENTE)

    planilha = conectar()
    eventos_ia = ler_eventos_ia(planilha)
    eventos_manual = ler_eventos_manual(planilha)

    eventos = [normalizar(ev) for ev in eventos_ia] + [normalizar(ev) for ev in eventos_manual]

    # remove eventos sem data válida
    eventos = [ev for ev in eventos if ev["data"]]

    print(f"Eventos da IA: {len(eventos_ia)}")
    print(f"Eventos manuais: {len(eventos_manual)}")
    print(f"Total considerado: {len(eventos)}")

    gerado_em = datetime.date.today().strftime("%d/%m/%Y")
    html = gerar_html(finais, eventos, gerado_em, URL_FORMULARIO_RESERVA)

    with open("agenda_beneficente.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Página gerada em agenda_beneficente.html")


if __name__ == "__main__":
    main()
