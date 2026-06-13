"""
Acesso à Google Sheet via Service Account (gspread).
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1cjdghdHaF1QRq5bWsY6tl-g-BGoznciho5wLlfi2WYw"
ABA_IA = "Eventos_IA"
ABA_MANUAL = "Eventos_Manual"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def conectar():
    """Autentica via Service Account e retorna o objeto da planilha."""
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    cliente = gspread.authorize(creds)
    return cliente.open_by_key(SHEET_ID)


def ler_eventos_ia(planilha):
    """Lê todos os eventos da aba Eventos_IA como lista de dicts."""
    aba = planilha.worksheet(ABA_IA)
    return aba.get_all_records()


def ler_eventos_manual(planilha):
    """Lê todas as reservas manuais e normaliza para o mesmo formato dos eventos IA."""
    aba = planilha.worksheet(ABA_MANUAL)
    linhas = aba.get_all_records()

    eventos = []
    for linha in linhas:
        data_raw = str(linha.get("Data", "")).strip()
        if not data_raw:
            continue

        data_str = _normalizar_data(data_raw)
        if data_str is None:
            continue

        eventos.append({
            "Data": data_str,
            "Nome do evento": str(linha.get("Nome do evento", "")).strip(),
            "Entidade promotora": str(linha.get("Entidade promotora", "")).strip(),
            "Cidade": str(linha.get("Cidade", "")).strip(),
            "Local": str(linha.get("Local", "")).strip(),
            "Horário": "A confirmar",
            "Fonte": "Reserva enviada pelo formulário",
        })
    return eventos


def _normalizar_data(data_raw):
    """Converte para DD/MM/AAAA, aceitando AAAA-MM-DD, M/D/AAAA ou DD/MM/AAAA."""
    import datetime
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(data_raw, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return None


def adicionar_eventos_ia(planilha, eventos):
    """Adiciona novas linhas na aba Eventos_IA. `eventos` é lista de dicts
    no formato retornado pela IA (data, nome_evento, entidade_beneficiada,
    cidade, local, horario, fonte)."""
    if not eventos:
        return

    aba = planilha.worksheet(ABA_IA)
    linhas = [
        [
            ev.get("data", ""),
            ev.get("nome_evento", ""),
            ev.get("entidade_beneficiada", ""),
            ev.get("cidade", ""),
            ev.get("local", ""),
            ev.get("horario", "A confirmar"),
            ev.get("fonte", ""),
        ]
        for ev in eventos
    ]
    aba.append_rows(linhas, value_input_option="USER_ENTERED")
