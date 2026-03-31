# ==============================================
# VIPE TRANSPORTES — CHATBOT VIP
# Arquivo: chatbot_vip.py
# Responde perguntas livres sobre CIOT e Multas
# ==============================================

import sys, io, os, json
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(__file__))
import ciot_excel
import multas_excel

CAMINHO_CIOT   = r"C:\Users\User\Desktop\Bot\bot_vipe_transportes\Relatórios\Ciot.xls"
CAMINHO_MULTAS = r"C:\Users\User\Desktop\Bot\bot_vipe_transportes\Relatórios\Multas.xlsx"


def _br(v):
    try:
        return f"R$ {float(v or 0):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except:
        return "R$ 0,00"

def _vencida(iso):
    try:
        from datetime import datetime as dt
        d = dt.fromisoformat(str(iso).replace('Z','+00:00'))
        return d.date() < date.today()
    except:
        return False

def _fmt_venc(iso):
    try:
        from datetime import datetime as dt
        d = dt.fromisoformat(str(iso).replace('Z','+00:00'))
        return d.strftime('%d/%m/%Y')
    except:
        return str(iso)[:10] if iso else '-'


def _resumo_ciot():
    try:
        registros = ciot_excel._ler_excel(CAMINHO_CIOT)
    except Exception as e:
        return f"[Erro ao ler CIOT: {e}]"

    pendentes = [r for r in registros if r.get('pendente')]

    grupos = {}
    for r in pendentes:
        mot  = (r.get('nome_motorista','') or '').strip() or '-'
        prop = (r.get('nome_proprietario','') or '').strip() or '-'
        if mot not in grupos:
            grupos[mot] = {'motorista': mot, 'proprietario': prop,
                           'contratos': [], 'total_pendente': 0.0}
        grupos[mot]['contratos'].append({
            'numero':     r.get('contrato',''),
            'rota':       r.get('rota',''),
            'filial':     r.get('filial_origem',''),
            'contratado': float(r.get('vlr_contratado', 0) or 0),
            'adiantado':  float(r.get('adiantamentos',  0) or 0),
            'liquido':    float(r.get('vlr_liquido',    0) or 0),
        })
        grupos[mot]['total_pendente'] += float(r.get('vlr_liquido', 0) or 0)

    linhas = ["=== CIOT — SALDOS EM ABERTO ===",
              f"Total contratos pendentes: {len(pendentes)}",
              f"Total motoristas com pendencia: {len(grupos)}",
              f"Valor total pendente: {_br(sum(g['total_pendente'] for g in grupos.values()))}",
              ""]

    for g in sorted(grupos.values(), key=lambda x: x['total_pendente'], reverse=True):
        linhas.append(f"Motorista: {g['motorista']} | Proprietario: {g['proprietario']} | "
                      f"Total pendente: {_br(g['total_pendente'])} | {len(g['contratos'])} contrato(s)")
        for c in g['contratos']:
            linhas.append(f"  Contrato {c['numero']} | Rota: {c['rota']} | "
                          f"Contratado: {_br(c['contratado'])} | "
                          f"Adiantado: {_br(c['adiantado'])} | "
                          f"Liquido: {_br(c['liquido'])}")
        linhas.append("")

    return "\n".join(linhas)


def _resumo_multas():
    try:
        registros = multas_excel._ler_excel(CAMINHO_MULTAS)
    except Exception as e:
        return f"[Erro ao ler Multas: {e}]"

    linhas = ["=== MULTAS EM ABERTO ===",
              f"Total registros: {len(registros)}",
              f"Total vencidas: {sum(1 for r in registros if _vencida(r.get('data_vencimento','')))}",
              f"Valor total: {_br(sum(float(r.get('vlr_total',0) or 0) for r in registros))}",
              ""]

    grupos = {}
    for r in registros:
        mot = (r.get('motorista','') or '').strip() or '-'
        if mot not in grupos:
            grupos[mot] = []
        grupos[mot].append(r)

    for mot, multas in sorted(grupos.items(),
                               key=lambda x: sum(float(m.get('vlr_total',0) or 0) for m in x[1]),
                               reverse=True):
        total = sum(float(m.get('vlr_total',0) or 0) for m in multas)
        venc  = sum(1 for m in multas if _vencida(m.get('data_vencimento','')))
        linhas.append(f"Motorista: {mot} | {len(multas)} multa(s) | {venc} vencida(s) | Total: {_br(total)}")
        for m in multas:
            linhas.append(f"  AIT {m.get('ait','')} | {m.get('descricao','')[:60]} | "
                          f"Cidade: {m.get('cidade','')} | "
                          f"Venc: {_fmt_venc(m.get('data_vencimento',''))}"
                          f"{' (VENCIDA)' if _vencida(m.get('data_vencimento','')) else ''} | "
                          f"Total: {_br(m.get('vlr_total',0))}")
        linhas.append("")

    return "\n".join(linhas)


def responder(pergunta: str) -> str:
    import urllib.request

    contexto = _resumo_ciot() + "\n\n" + _resumo_multas()

    system_prompt = (
        "Voce e o Vipi, assistente de dados da Vipe Transportes. "
        "Voce tem acesso completo as bases de CIOT (contratos de frete) e Multas. "
        "SEMPRE responda usando os dados fornecidos — eles contem TODAS as informacoes disponíveis. "
        "Quando perguntarem sobre um motorista, procure o nome nos dados e liste tudo que encontrar. "
        "Se nao encontrar o nome exato, procure por partes do nome. "
        "Nunca recuse perguntas sobre motoristas, multas ou CIOT — essa e sua funcao principal. "
        "Formate valores em R$ (ex: R$ 1.234,56) e datas em DD/MM/AAAA. "
        "Seja objetivo e use emojis com moderacao. "
        "So recuse perguntas completamente fora do contexto de transportes (ex: receitas, futebol)."
    ) e Multas em aberto. "
        "Responda APENAS perguntas relacionadas a esses dados. "
        "Se perguntarem algo fora do escopo, diga que so pode ajudar com dados de CIOT e Multas da Vipe Transportes. "
        "Formate valores em R$ brasileiro. Use linguagem direta e amigavel. "
        "Nao invente dados — use apenas o que esta no contexto fornecido. "
        "Seja objetivo e formatado para WhatsApp (use *negrito* com asteriscos quando necessario)."
    )

    user_prompt = f"Dados:\n\n{contexto}\n\nPergunta: {pergunta}"

    payload = json.dumps({
        "model": "gpt-4o-mini",
        "max_tokens": 1000,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
    }).encode('utf-8')

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_KEY}",
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        return data['choices'][0]['message']['content'].strip()



if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding='utf-8', errors='replace')
    pergunta = sys.stdin.read().strip()
    if not pergunta:
        print(json.dumps({"erro": "Pergunta nao informada"}, ensure_ascii=False))
    else:
        resposta = responder(pergunta)
        print(json.dumps({"resposta": resposta}, ensure_ascii=False))
