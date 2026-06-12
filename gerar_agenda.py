#!/usr/bin/env python3
"""
Gerador diário de agenda de eventos beneficentes
Cidades: Gaspar/SC, Blumenau/SC e Indaial/SC
Gera uma página HTML com tabela dos próximos 12 fins de semana
(sábados e domingos) e os eventos beneficentes encontrados.

Requer:
  pip install anthropic --break-system-packages
  export ANTHROPIC_API_KEY="sua-chave-aqui"

Agendamento sugerido (Linux/Mac - crontab):
  0 6 * * * /usr/bin/python3 /caminho/gerar_agenda.py >> /caminho/log.txt 2>&1

Windows - Agendador de Tarefas:
  Criar tarefa diária que execute:
  python C:/caminho/gerar_agenda.py
"""

import os
import json
import datetime
from anthropic import Anthropic

# -------------------- CONFIGURAÇÃO --------------------
OUTPUT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agenda_beneficente.html")
MODEL = "claude-sonnet-4-6"
CIDADES = ["Gaspar/SC", "Blumenau/SC", "Indaial/SC"]
MESES_A_FRENTE = 12

# URL do CSV publicado da Google Sheet ligada ao Google Forms de reservas.
# Deixe em branco ("") se ainda não tiver configurado.
URL_RESERVAS_CSV = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQNPeg2pjF0Qw0osePneOqf5GaPBI3DS9D_NLzTJK1jOgcXlyxJCm9fS4qj4py5ZMeLqa-25I9vLvFT/pub?gid=1675863191&single=true&output=csv"

# Link do Google Forms de reserva, com placeholder {DATA} no parâmetro da
# pergunta "Data". Exemplo real (substitua o ID da entrada pelo seu):
# "https://docs.google.com/forms/d/e/SEU_ID/viewform?usp=pp_url&entry.111111111={DATA}"
URL_FORMULARIO_RESERVA = "https://docs.google.com/forms/d/e/1FAIpQLSflqHKK92JjpM99WjjWSluANqimWKm8rj_vfKPec_97Fbm7xA/viewform?usp=pp_url&entry.1859357884={DATA}"
# --------------------------------------------------------


def carregar_reservas_manuais(url_csv):
    """Lê reservas feitas pelo formulário (Google Forms -> Sheet -> CSV publicado)
    e devolve uma lista no mesmo formato dos eventos da pesquisa web."""
    if not url_csv:
        return []

    import csv
    import urllib.request

    eventos = []
    try:
        with urllib.request.urlopen(url_csv, timeout=15) as resp:
            conteudo = resp.read().decode("utf-8")

        leitor = csv.DictReader(conteudo.splitlines())
        print(f"Colunas encontradas no CSV: {leitor.fieldnames}")
        for linha_raw in leitor:
            # normaliza chaves: remove espaços extras
            linha = {(k or "").strip(): (v or "").strip() for k, v in linha_raw.items()}

            data_raw = linha.get("Data", "").strip()
            if not data_raw:
                continue

            # Aceita AAAA-MM-DD, DD/MM/AAAA ou M/D/AAAA (formato do Google Forms)
            dt = None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    dt = datetime.datetime.strptime(data_raw, fmt).date()
                    break
                except ValueError:
                    continue
            if dt is None:
                print(f"Aviso: data não reconhecida '{data_raw}', linha ignorada")
                continue

            eventos.append({
                "data": dt.strftime("%d/%m/%Y"),
                "dia_semana": "Sábado" if dt.weekday() == 5 else "Domingo",
                "cidade": linha.get("Cidade", "").strip(),
                "nome_evento": linha.get("Nome do evento", "").strip(),
                "local": linha.get("Local", "").strip(),
                "horario": "A confirmar",
                "entidade_beneficiada": linha.get("Entidade promotora", "").strip(),
                "fonte": "Reserva enviada pelo formulário",
            })
    except Exception as e:
        print(f"Aviso: não foi possível carregar reservas manuais ({e})")

    return eventos


def proximos_finais_de_semana(meses=12):
    """Retorna lista de tuplas (sabado, domingo) cobrindo os próximos N meses a partir de hoje."""
    hoje = datetime.date.today()
    fim = hoje.replace(year=hoje.year + ((hoje.month - 1 + meses) // 12),
                        month=((hoje.month - 1 + meses) % 3) + 1)

    finais = []
    dias_para_sabado = (5 - hoje.weekday()) % 7
    sabado = hoje + datetime.timedelta(days=dias_para_sabado)
    while sabado <= fim:
        domingo = sabado + datetime.timedelta(days=1)
        finais.append((sabado, domingo))
        sabado = sabado + datetime.timedelta(days=7)
    return finais


def montar_prompt(finais_de_semana):
    data_inicio = finais_de_semana[0][0].strftime("%d/%m/%Y")
    data_fim = finais_de_semana[-1][1].strftime("%d/%m/%Y")
    cidades_str = ", ".join(CIDADES)

    prompt = f"""
Você é um assistente de pesquisa que monta uma agenda de EVENTOS BENEFICENTES
em {cidades_str}, para o período de {data_inicio} a {data_fim} (sábados e
domingos apenas).

São considerados "eventos beneficentes": jantares, almoços, feijoadas,
macarronadas com data marcada, etc., cuja renda/objetivo seja
beneficiar uma entidade, ONG, igreja, associação ou causa social.

PASSOS QUE VOCÊ DEVE SEGUIR:
1. Faça VÁRIAS buscas (pelo menos 5-8), variando os termos, por exemplo:
   - "evento beneficente Blumenau {data_inicio[3:]}"
   - "agenda Blumenau fim de semana eventos"
   - "feijoada beneficente Blumenau OR Gaspar OR Indaial"
   - "site:blumenau.sc.gov.br agenda eventos"
   - "eventos Gaspar SC agenda cultural"
   - "eventos Indaial SC agenda"
   - busque também páginas de prefeituras, secretarias de turismo, rádios
     locais (ex: Blumenau FM, Bom Som), jornais regionais (NSC, Blumenau Hoje),
     e páginas/Instagram de paróquias, clubes e associações.
2. Para cada resultado relevante, extraia: data exata, nome do evento,
   cidade, local, horário e entidade beneficiada.
3. Inclua APENAS eventos com data específica já divulgada (dia/mês/ano).
   NÃO inclua eventos recorrentes sem data definida (ex: "todo sábado").
4. Se a mesma fonte mencionar um evento anual mas sem data da próxima edição
   confirmada, NÃO inclua — apenas se houver data explícita para o período
   pesquisado.
5. NUNCA invente eventos, datas, locais ou entidades. Se não encontrar nada
   confirmado, retorne a lista "eventos" vazia — isso é uma resposta válida
   e esperada caso a divulgação ainda não tenha ocorrido.
6. Ordene os eventos por data, do mais próximo ao mais distante.
7. Antes de responder, REVISE sua lista: remova qualquer item cuja data
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
  "gerado_em": "{datetime.date.today().strftime('%d/%m/%Y')}",
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
    return prompt


def consultar_eventos(finais_de_semana):
    client = Anthropic()  # usa ANTHROPIC_API_KEY do ambiente
    prompt = montar_prompt(finais_de_semana)

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
    )

    # Junta todos os blocos de texto da resposta final
    texto_final = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            texto_final += block.text

    texto_final = texto_final.strip()
    # remove possíveis cercas de código
    if texto_final.startswith("```"):
        texto_final = texto_final.strip("`")
        texto_final = texto_final.replace("json\n", "", 1)

    try:
        dados = json.loads(texto_final)
    except json.JSONDecodeError:
        dados = _extrair_json(texto_final)

    return dados


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
                        break  # tenta o próximo "{"
    raise ValueError(f"Nenhum JSON válido encontrado na resposta:\n{texto[:1000]}")


def gerar_html(finais_de_semana, dados):
    eventos = dados.get("eventos", [])
    gerado_em = dados.get("gerado_em", datetime.date.today().strftime("%d/%m/%Y"))

    meses_pt = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

    # Indexa eventos por data (DD/MM/AAAA)
    eventos_por_data = {}
    for ev in eventos:
        eventos_por_data.setdefault(ev.get("data", ""), []).append(ev)

    linhas_html = []
    mes_atual = None

    # Lista plana de todas as datas (sáb e dom) em ordem
    todas_datas = []
    for sab, dom in finais_de_semana:
        todas_datas.append((sab, "Sábado"))
        todas_datas.append((dom, "Domingo"))

    for data_obj, label in todas_datas:
        data_str = data_obj.strftime("%d/%m/%Y")
        mes_label = f"{meses_pt[data_obj.month]} de {data_obj.year}"

        if mes_label != mes_atual:
            linhas_html.append(f"""
                    <tr class="mes-header">
                        <td colspan="6">{mes_label}</td>
                    </tr>""")
            mes_atual = mes_label

        evs = eventos_por_data.get(data_str, [])

        if evs:
            for ev in evs:
                linhas_html.append(f"""
                    <tr>
                        <td class="data">{data_str}<br><span class="dia">{label}</span></td>
                        <td class="cidade"><span class="badge badge-{ev.get('cidade','').split('/')[0].lower()}">{ev.get('cidade','')}</span></td>
                        <td class="evento">
                            <strong>{ev.get('nome_evento','')}</strong>
                            {f"<br><small>Em benefício de: {ev.get('entidade_beneficiada')}</small>" if ev.get('entidade_beneficiada') else ""}
                        </td>
                        <td class="local">{ev.get('local','')}</td>
                        <td class="horario">{ev.get('horario','A confirmar')}</td>
                        <td class="fonte">{f'<a href="{ev.get("fonte")}" target="_blank">link</a>' if ev.get('fonte') else '-'}</td>
                    </tr>""")
        else:
            data_iso = data_obj.strftime("%Y-%m-%d")
            if URL_FORMULARIO_RESERVA:
                link_reserva = URL_FORMULARIO_RESERVA.format(DATA=data_iso)
                botao = f'<a class="btn-reservar" href="{link_reserva}" target="_blank">Reservar esta data</a>'
            else:
                botao = '<span class="btn-reservar btn-desativado">Reservar esta data</span>'

            linhas_html.append(f"""
                    <tr class="data-livre">
                        <td class="data">{data_str}<br><span class="dia">{label}</span></td>
                        <td colspan="4" class="livre">Data disponível — nenhum evento registrado</td>
                        <td class="acao">{botao}</td>
                    </tr>""")

    corpo_tabela = "\n".join(linhas_html)
    periodo = f"{finais_de_semana[0][0].strftime('%d/%m/%Y')} a {finais_de_semana[-1][1].strftime('%d/%m/%Y')}"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agenda de Eventos Beneficentes — Gaspar, Blumenau e Indaial</title>
<style>
  :root {{
    --azul: #1f4e8c;
    --azul-claro: #e8f0fb;
    --verde: #2e8b57;
    --cinza: #6b7280;
    --bg: #f4f6f9;
  }}
  * {{ box-sizing: border-box; font-family: 'Segoe UI', Roboto, Arial, sans-serif; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: #1f2933;
    padding: 24px;
  }}
  .container {{
    max-width: 1100px;
    margin: 0 auto;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.07);
    overflow: hidden;
  }}
  header {{
    background: linear-gradient(135deg, var(--azul), #3a7bd5);
    color: #fff;
    padding: 28px 32px;
  }}
  header h1 {{
    margin: 0 0 6px 0;
    font-size: 1.6rem;
  }}
  header p {{
    margin: 0;
    opacity: 0.9;
    font-size: 0.95rem;
  }}
  .conteudo {{
    padding: 24px 32px 32px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
  }}
  thead th {{
    background: var(--azul-claro);
    color: var(--azul);
    text-align: left;
    padding: 10px 12px;
    border-bottom: 2px solid var(--azul);
    position: sticky;
    top: 0;
  }}
  tbody td {{
    padding: 10px 12px;
    border-bottom: 1px solid #e5e7eb;
    vertical-align: top;
  }}
  tbody tr:hover {{ background: #f9fbff; }}
  .data {{ white-space: nowrap; font-weight: 600; color: var(--azul); }}
  .dia {{ font-size: 0.78rem; color: var(--cinza); font-weight: 400; }}
  .badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #fff;
  }}
  .badge-blumenau {{ background: #1f4e8c; }}
  .badge-gaspar {{ background: #2e8b57; }}
  .badge-indaial {{ background: #b1740f; }}
  .sem-evento td {{ color: var(--cinza); font-style: italic; }}
  .vazio {{ text-align: center; }}
  .data-livre td {{ color: var(--cinza); }}
  .data-livre .livre {{ font-style: italic; }}
  .acao {{ text-align: right; white-space: nowrap; }}
  .btn-reservar {{
    display: inline-block;
    padding: 6px 14px;
    border-radius: 999px;
    background: var(--verde);
    color: #fff;
    text-decoration: none;
    font-size: 0.82rem;
    font-weight: 600;
    white-space: nowrap;
  }}
  .btn-reservar:hover {{ background: #246b46; }}
  .btn-desativado {{
    background: #cbd5e1;
    color: #64748b;
    cursor: default;
  }}
  .mes-header td {{
    background: var(--azul);
    color: #fff;
    font-weight: 700;
    font-size: 0.95rem;
    padding: 8px 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  footer {{
    text-align: center;
    padding: 16px;
    font-size: 0.8rem;
    color: var(--cinza);
  }}
  @media (max-width: 700px) {{
    .conteudo {{ padding: 16px; }}
    table, thead, tbody, th, td, tr {{ display: block; }}
    thead {{ display: none; }}
    tbody tr {{
      margin-bottom: 14px;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      padding: 8px;
    }}
    tbody td {{ border: none; padding: 4px 8px; }}
    tbody td:before {{
      content: attr(data-label);
      font-weight: 600;
      color: var(--azul);
      display: block;
      font-size: 0.75rem;
    }}
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🎗️ Agenda de Eventos Beneficentes</h1>
    <p>Gaspar/SC · Blumenau/SC · Indaial/SC — período: {periodo}</p>
  </header>
  <div class="conteudo">
    <table>
      <thead>
        <tr>
          <th>Data</th>
          <th>Cidade</th>
          <th>Evento</th>
          <th>Local</th>
          <th>Horário</th>
          <th>Fonte</th>
        </tr>
      </thead>
      <tbody>
        {corpo_tabela}
      </tbody>
    </table>
  </div>
  <footer>
    Gerado automaticamente em {gerado_em} · As informações dependem da disponibilidade de divulgação dos eventos na web e podem mudar — confirme sempre com a organização.
  </footer>
</div>
</body>
</html>"""
    return html


def main():
    finais = proximos_finais_de_semana(MESES_A_FRENTE)
    dados = consultar_eventos(finais)
    print(f"Eventos encontrados pela IA: {len(dados.get('eventos', []))}")
    for ev in dados.get("eventos", []):
        print(f"  - {ev.get('data')} | {ev.get('nome_evento')}")

    reservas = carregar_reservas_manuais(URL_RESERVAS_CSV)
    print(f"Reservas lidas do formulário: {len(reservas)}")
    for ev in reservas:
        print(f"  - {ev.get('data')} | {ev.get('nome_evento')}")

    if reservas:
        existentes = {(ev.get("data"), ev.get("nome_evento", "").strip().lower())
                       for ev in dados.get("eventos", [])}
        for ev in reservas:
            chave = (ev["data"], ev["nome_evento"].strip().lower())
            if chave not in existentes:
                dados.setdefault("eventos", []).append(ev)
                existentes.add(chave)

    html = gerar_html(finais, dados)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Página gerada em: {OUTPUT_HTML}")
    print(f"Eventos encontrados: {len(dados.get('eventos', []))}")


if __name__ == "__main__":
    main()
