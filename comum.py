"""
Funções compartilhadas entre popular_planilha.py e gerar_html.py
"""

import datetime

MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def proximos_finais_de_semana(meses=12):
    """Retorna lista de tuplas (sabado, domingo) cobrindo os próximos N meses a partir de hoje."""
    hoje = datetime.date.today()
    fim = hoje.replace(year=hoje.year + ((hoje.month - 1 + meses) // 12),
                        month=((hoje.month - 1 + meses) % 12) + 1)

    finais = []
    dias_para_sabado = (5 - hoje.weekday()) % 7
    sabado = hoje + datetime.timedelta(days=dias_para_sabado)
    while sabado <= fim:
        domingo = sabado + datetime.timedelta(days=1)
        finais.append((sabado, domingo))
        sabado = sabado + datetime.timedelta(days=7)
    return finais


def gerar_html(finais_de_semana, eventos, gerado_em, url_formulario_reserva):
    """Gera o HTML completo da agenda.

    eventos: lista de dicts com chaves
        data (DD/MM/AAAA), dia_semana, cidade, nome_evento, local,
        horario, entidade_beneficiada, fonte
    """
    eventos_por_data = {}
    for ev in eventos:
        eventos_por_data.setdefault(ev.get("data", ""), []).append(ev)

    linhas_html = []
    mes_atual = None

    todas_datas = []
    for sab, dom in finais_de_semana:
        todas_datas.append((sab, "Sábado"))
        todas_datas.append((dom, "Domingo"))

    for data_obj, label in todas_datas:
        data_str = data_obj.strftime("%d/%m/%Y")
        mes_label = f"{MESES_PT[data_obj.month]} de {data_obj.year}"

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
            if url_formulario_reserva:
                link_reserva = url_formulario_reserva.format(DATA=data_iso)
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
<title>Agenda de Eventos Beneficentes — Blumenau, Gaspar, Indaial, Pomerode e Timbó/SC</title>
<style>
  :root {{
    --azul: #1f4e8c;
    --azul-claro: #e8f0fb;
    --verde: #2e8b57;
    --cinza: #6b7280;
    --bg: #f4f6f9;
  }}
  * {{ box-sizing: border-box; font-family: 'Segoe UI', Roboto, Arial, sans-serif; }}
  body {{ margin: 0; background: var(--bg); color: #1f2933; padding: 24px; }}
  .container {{ max-width: 1100px; margin: 0 auto; background: #fff; border-radius: 16px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.07); overflow: hidden; }}
  header {{ background: linear-gradient(135deg, var(--azul), #3a7bd5); color: #fff; padding: 28px 32px; }}
  header h1 {{ margin: 0 0 6px 0; font-size: 1.6rem; }}
  header p {{ margin: 0; opacity: 0.9; font-size: 0.95rem; }}
  .conteudo {{ padding: 24px 32px 32px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
  thead th {{ background: var(--azul-claro); color: var(--azul); text-align: left; padding: 10px 12px;
              border-bottom: 2px solid var(--azul); position: sticky; top: 0; }}
  tbody td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
  tbody tr:hover {{ background: #f9fbff; }}
  .data {{ white-space: nowrap; font-weight: 600; color: var(--azul); }}
  .dia {{ font-size: 0.78rem; color: var(--cinza); font-weight: 400; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.78rem;
            font-weight: 600; color: #fff; }}
  .badge-blumenau {{ background: #1f4e8c; }}
  .badge-gaspar {{ background: #2e8b57; }}
  .badge-indaial {{ background: #b1740f; }}
  .data-livre td {{ color: var(--cinza); }}
  .data-livre .livre {{ font-style: italic; }}
  .acao {{ text-align: right; white-space: nowrap; }}
  .btn-reservar {{ display: inline-block; padding: 6px 14px; border-radius: 999px; background: var(--verde);
                   color: #fff; text-decoration: none; font-size: 0.82rem; font-weight: 600; white-space: nowrap; }}
  .btn-reservar:hover {{ background: #246b46; }}
  .btn-desativado {{ background: #cbd5e1; color: #64748b; cursor: default; }}
  .mes-header td {{ background: var(--azul); color: #fff; font-weight: 700; font-size: 0.95rem;
                    padding: 8px 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
  footer {{ text-align: center; padding: 16px; font-size: 0.8rem; color: var(--cinza); }}
  @media (max-width: 700px) {{
    .conteudo {{ padding: 16px; }}
    table, thead, tbody, th, td, tr {{ display: block; }}
    thead {{ display: none; }}
    tbody tr {{ margin-bottom: 14px; border: 1px solid #e5e7eb; border-radius: 10px; padding: 8px; }}
    tbody td {{ border: none; padding: 4px 8px; }}
    tbody td:before {{ content: attr(data-label); font-weight: 600; color: var(--azul); display: block; font-size: 0.75rem; }}
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
    Última atualização da lista de eventos: {gerado_em} ·
    As informações dependem da divulgação dos eventos e podem mudar — confirme com a organização.
    Após o cadastramento de um novo evento, a atualização pode levar até 1 miutos. Aguarde.
    Em caso e dúvida ou necessidade de edição, contatar rpnene@gmail.com.
    Este serviço é gratuíto e mantido de forma voluntária.
  </footer>
</div>
</body>
</html>"""
    return html
