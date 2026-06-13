#!/usr/bin/env python3
"""
Roda 1x por semana.
Consulta a IA (com web search) para encontrar refeições beneficentes em
Gaspar/SC, Blumenau/SC e Indaial/SC nos próximos meses, e adiciona os
eventos novos (que ainda não existem nem em Eventos_IA nem em
Eventos_Manual) na aba Eventos_IA da planilha.

Requer variáveis de ambiente:
  ANTHROPIC_API_KEY
  GOOGLE_SERVICE_ACCOUNT_JSON  (conteúdo do JSON da service account)
"""

import json
import datetime
from anthropic import Anthropic

from comum import proximos_finais_de_semana
from planilha import conectar, ler_eventos_ia, ler_eventos_manual, adicionar_eventos_ia

MODEL = "claude-sonnet-4-6"
CIDADES = ["Gaspar/SC", "Blumenau/SC", "Indaial/SC"]
MESES_A_FRENTE = 12


def montar_prompt(finais_de_semana):
    data_inicio = finais_de_semana[0][0].strftime("%d/%m/%Y")
    data_fim = finais_de_semana[-1][1].strftime("%d/%m/%Y")
    cidades_str = ", ".join(CIDADES)

    return f"""
Você é um assistente de pesquisa que monta uma agenda de EVENTOS
GASTRONÔMICOS BENEFICENTES em {cidades_str}, para o período de
{data_inicio} a {data_fim} (sábados e domingos apenas).

São considerados "eventos beneficentes": jantares, almoços, feijoadas,
costeladas, macarronadas, macarrojôs, carreteiros, pasteladas e eventos
gastronômicos semelhantes (refeições/comidas vendidas com fins
beneficentes), cuja renda seja revertida para uma entidade, ONG, igreja,
associação ou causa social.

NÃO incluir: pedágios beneficentes, campanhas de doação de sangue, bazares,
rifas/sorteios sem refeição, leilões, shows, palestras, ou qualquer evento
que não seja uma refeição/comida vendida com fins beneficentes.

PASSOS QUE VOCÊ DEVE SEGUIR:
1. Faça VÁRIAS buscas (pelo menos 5-8), variando os termos, por exemplo:
   - "feijoada beneficente Blumenau {data_inicio[3:]}"
   - "jantar beneficente Blumenau OR Gaspar OR Indaial"
   - "macarronada beneficente Blumenau"
   - "costelada beneficente Blumenau OR Gaspar OR Indaial"
   - "carreteiro beneficente Blumenau"
   - "pastelada beneficente Blumenau OR Indaial"
   - "almoço beneficente Gaspar SC"
   - "site:blumenau.sc.gov.br agenda eventos beneficente"
   - busque também páginas de prefeituras, secretarias de turismo, rádios
     locais (ex: Blumenau FM, Bom Som), jornais regionais (NSC, Blumenau Hoje),
     e páginas/Instagram de paróquias, clubes e associações.
2. Para cada resultado relevante, extraia: data exata, nome do evento,
   cidade, local, horário e entidade beneficiada.
3. Inclua APENAS eventos com data específica já divulgada (dia/mês/ano).
   NÃO inclua eventos recorrentes sem data definida (ex: "todo sábado").
4. NUNCA invente eventos, datas, locais ou entidades. Se não encontrar nada
   confirmado, retorne a lista "eventos" vazia — isso é uma resposta válida.
5. Ordene os eventos por data, do mais próximo ao mais distante.
6. Antes de responder, REVISE sua lista: remova qualquer item cuja data
   não caia em um sábado ou domingo, ou que esteja fora do período
   {data_inicio} a {data_fim}.

Para cada item da lista final, retorne:
- data (formato DD/MM/AAAA)
- dia_semana ("Sábado" ou "Domingo")
- cidade (exatamente uma de: {cidades_str})
- nome_evento
- local
- horario (se disponível, senão "A confirmar")
- entidade_beneficiada (se souber, senão "")
- fonte (URL da fonte da informação)

FORMATO DE RESPOSTA — MUITO IMPORTANTE:
Responda SOMENTE com um objeto JSON válido, sem nenhum texto antes ou depois,
sem markdown, sem ```json, sem comentários. A resposta deve começar com "{{"
e terminar com "}}", e ser o ÚNICO conteúdo da sua mensagem final:

{{
  "eventos": [
    {{
      "data": "DD/MM/AAAA",
      "dia_semana": "Sábado",
      "cidade": "Blumenau/SC",
      "nome_evento": "...",
      "local": "...",
      "horario": "...",
      "entidade_beneficiada": "...",
      "fonte": "https://..."
    }}
  ]
}}
"""


def _extrair_json(texto):
    """Varre o texto procurando o primeiro objeto JSON válido,
    balanceando chaves para lidar com texto extra antes/depois."""
    for i, ch in enumerate(texto):
        if ch != "{":
            continue
        profundidade = 0
        for j in range(i, len(texto)):
            if texto[j] == "{":
                profundidade += 1
            elif texto[j] == "}":
                profundidade -= 1
                if profundidade == 0:
                    candidato = texto[i:j + 1]
                    try:
                        return json.loads(candidato)
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"Nenhum JSON válido encontrado na resposta:\n{texto[:1000]}")


def consultar_eventos(finais_de_semana):
    client = Anthropic()
    prompt = montar_prompt(finais_de_semana)

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
    )

    texto_final = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()

    if texto_final.startswith("```"):
        texto_final = texto_final.strip("`")
        texto_final = texto_final.replace("json\n", "", 1)

    try:
        return json.loads(texto_final)
    except json.JSONDecodeError:
        return _extrair_json(texto_final)


def chave(data, nome):
    return (data.strip(), nome.strip().lower())


def main():
    finais = proximos_finais_de_semana(MESES_A_FRENTE)

    planilha = conectar()
    existentes_ia = ler_eventos_ia(planilha)
    existentes_manual = ler_eventos_manual(planilha)

    chaves_existentes = set()
    for ev in existentes_ia:
        chaves_existentes.add(chave(str(ev.get("Data", "")), str(ev.get("Nome do evento", ""))))
    for ev in existentes_manual:
        chaves_existentes.add(chave(ev["Data"], ev["Nome do evento"]))

    print(f"Eventos já existentes na planilha: {len(chaves_existentes)}")

    dados = consultar_eventos(finais)
    eventos_ia = dados.get("eventos", [])
    print(f"Eventos encontrados pela IA: {len(eventos_ia)}")

    novos = []
    for ev in eventos_ia:
        k = chave(ev.get("data", ""), ev.get("nome_evento", ""))
        if k not in chaves_existentes:
            novos.append(ev)
            chaves_existentes.add(k)
        else:
            print(f"  (duplicado, ignorado) {ev.get('data')} | {ev.get('nome_evento')}")

    print(f"Eventos novos a adicionar: {len(novos)}")
    for ev in novos:
        print(f"  + {ev.get('data')} | {ev.get('nome_evento')}")

    adicionar_eventos_ia(planilha, novos)
    print("Concluído.")


if __name__ == "__main__":
    main()
