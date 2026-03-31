# ==============================================
# VIPE TRANSPORTES — LEITOR CIOT EXCEL
# Retorna JSON para ser formatado pela OpenAI
# ==============================================

import zipfile, xml.etree.ElementTree as ET, re, os, io, sys, json
from datetime import datetime

CAMINHO_EXCEL = r"C:\Users\User\Desktop\Bot\bot_vipe_transportes\Relatórios\Ciot.xls"
NS = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def _ler_excel(caminho):
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    with zipfile.ZipFile(caminho) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall('ns:si', NS):
                t = si.find('.//ns:t', NS)
                strings.append(t.text if t is not None and t.text else '')
        ws = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        rows = ws.findall('.//ns:row', NS)

    def get_val(cell):
        v = cell.find('ns:v', NS)
        if v is None:
            is_ = cell.find('ns:is', NS)
            if is_:
                t = is_.find('.//ns:t', NS)
                return t.text if t is not None else ''
            return ''
        raw = v.text or ''
        if cell.get('t') == 's' and strings:
            try: return strings[int(raw)]
            except: return raw
        return raw

    MAPA = {
        0:'filial_origem', 1:'contrato', 2:'emissao', 3:'status',
        4:'cpf_motorista', 5:'nome_motorista', 6:'nasc_motorista', 7:'pis_motorista',
        8:'cpf_proprietario', 9:'nome_proprietario', 10:'nasc_proprietario', 11:'pis_proprietario',
        12:'inss_proprietario', 13:'rota', 14:'manifestos', 15:'romaneios',
        16:'vlr_contratado', 17:'vlr_coleta', 18:'vlr_entrega', 19:'vlr_outros_mais',
        20:'vlr_pedagio', 21:'rendimentos', 22:'irrf', 23:'inss', 24:'sest', 25:'senat',
        26:'adiantamentos', 27:'combustivel', 28:'outros_menos', 29:'vlr_liquido',
        30:'nr_rpa', 31:'data_rpa', 32:'prazo_pgto', 33:'usuario_cancelamento', 34:'data_cancelamento'
    }

    registros = []
    cpf_mot_atual = cpf_prop_atual = ''
    nome_mot_atual = nome_prop_atual = ''

    for row in rows[1:]:
        vals = [get_val(c) for c in row.findall('ns:c', NS)]
        while len(vals) < 35: vals.append('')

        if vals[4] and vals[4] not in ['-', '']: cpf_mot_atual  = vals[4]
        if vals[5] and vals[5] not in ['-', '']: nome_mot_atual = vals[5]
        if vals[8] and vals[8] not in ['-', '']: cpf_prop_atual  = vals[8]
        if vals[9] and vals[9] not in ['-', '']: nome_prop_atual = vals[9]

        reg = {MAPA[i]: vals[i] for i in MAPA}
        reg['cpf_motorista']     = cpf_mot_atual
        reg['nome_motorista']    = nome_mot_atual
        reg['cpf_proprietario']  = cpf_prop_atual
        reg['nome_proprietario'] = nome_prop_atual

        for campo in ['vlr_contratado','vlr_liquido','rendimentos','adiantamentos','irrf','inss','sest','senat','combustivel','vlr_pedagio']:
            try: reg[campo] = float(reg[campo]) if reg[campo] else 0.0
            except: reg[campo] = 0.0

        reg['pago']    = bool(reg['nr_rpa'].strip())
        reg['pendente'] = not reg['pago']
        if not reg['contrato']: continue
        registros.append(reg)

    return registros

def _limpar_cpf(cpf): return re.sub(r'\D', '', str(cpf))

def consultar_cpf(cpf, caminho=CAMINHO_EXCEL):
    registros = _ler_excel(caminho)
    cpf_limpo = _limpar_cpf(cpf)
    contratos = [r for r in registros if _limpar_cpf(r['cpf_motorista']) == cpf_limpo or _limpar_cpf(r['cpf_proprietario']) == cpf_limpo]

    if not contratos:
        return {"encontrado": False, "cpf": cpf}

    nome = next((c['nome_motorista'] for c in contratos if c['nome_motorista'] not in ['-','']), '')
    if not nome:
        nome = next((c['nome_proprietario'] for c in contratos if c['nome_proprietario'] not in ['-','']), '')

    pagos     = [c for c in contratos if c['pago']]
    pendentes = [c for c in contratos if c['pendente']]

    return {
        "encontrado": True,
        "cpf": cpf,
        "nome": nome,
        "total_contratos": len(contratos),
        "total_pagos": len(pagos),
        "total_pendentes": len(pendentes),
        "valor_total_contratado": sum(c['vlr_contratado'] for c in contratos),
        "valor_total_pago": sum(c['vlr_liquido'] for c in pagos),
        "valor_total_pendente": sum(c['vlr_liquido'] for c in pendentes),
        "pendentes": [
            {
                "contrato": c['contrato'],
                "filial": c['filial_origem'],
                "emissao": c['emissao'][:10] if c['emissao'] else '-',
                "rota": c['rota'],
                "manifesto": c['manifestos'],
                "vlr_contratado": c['vlr_contratado'],
                "adiantamento": c['adiantamentos'],
                "vlr_liquido": c['vlr_liquido'],
            } for c in pendentes
        ],
        "pagos": [
            {
                "contrato": c['contrato'],
                "rota": c['rota'],
                "nr_rpa": c['nr_rpa'],
                "data_rpa": c['data_rpa'],
                "vlr_liquido": c['vlr_liquido'],
            } for c in pagos
        ]
    }






def _sem_acento(texto):
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()



def _sem_acento(texto):
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


def listar_nomes(termo, caminho=CAMINHO_EXCEL):
    """Retorna nomes únicos que contêm o termo (motorista e proprietario)."""
    registros = _ler_excel(caminho)
    t = _sem_acento(termo).strip()
    nomes = set()
    for r in registros:
        for campo in ["nome_motorista", "nome_proprietario"]:
            n = r.get(campo, "").strip()
            n_limpo = re.sub(r"^[\d.\-/]+\s*", "", n).strip()
            if n_limpo and n_limpo not in ["-", ""] and t in _sem_acento(n_limpo):
                nomes.add(n_limpo)
    return {"encontrado": len(nomes) > 0, "nomes": sorted(nomes)}


def consultar_nome_exato(nome, caminho=CAMINHO_EXCEL):
    """
    Retorna contratos onde o nome aparece como MOTORISTA ou PROPRIETARIO.
    Cada contrato traz nome_motorista e nome_proprietario.
    """
    registros = _ler_excel(caminho)
    nome_norm = _sem_acento(nome).strip()

    contratos = [
        r for r in registros
        if _sem_acento(r.get("nome_motorista", "")) == nome_norm
        or _sem_acento(r.get("nome_proprietario", "")) == nome_norm
    ]

    if not contratos:
        return {"encontrado": False, "nome": nome}

    # CPF do nome buscado (pode ser motorista ou proprietario)
    cpf = ""
    for c in contratos:
        if _sem_acento(c.get("nome_motorista","")) == nome_norm and c.get("cpf_motorista","") not in ["-",""]:
            cpf = c["cpf_motorista"]; break
    if not cpf:
        for c in contratos:
            if _sem_acento(c.get("nome_proprietario","")) == nome_norm and c.get("cpf_proprietario","") not in ["-",""]:
                cpf = c["cpf_proprietario"]; break

    pagos     = [c for c in contratos if c["pago"]]
    pendentes = [c for c in contratos if c["pendente"]]

    return {
        "encontrado": True,
        "nome": nome,
        "cpf": cpf,
        "total_contratos": len(contratos),
        "total_pagos": len(pagos),
        "total_pendentes": len(pendentes),
        "valor_total_contratado": sum(c["vlr_contratado"] for c in contratos),
        "valor_total_pago":       sum(c["vlr_liquido"]    for c in pagos),
        "valor_total_pendente":   sum(c["vlr_liquido"]    for c in pendentes),
        "pendentes": [
            {
                "contrato":       c["contrato"],
                "filial":         c["filial_origem"],
                "emissao":        c["emissao"][:10] if c["emissao"] else "-",
                "rota":           c["rota"],
                "manifesto":      c["manifestos"],
                "nome_motorista":    c.get("nome_motorista", "-"),
                "nome_proprietario": c.get("nome_proprietario", "-"),
                "vlr_contratado": c["vlr_contratado"],
                "adiantamento":   c["adiantamentos"],
                "vlr_liquido":    c["vlr_liquido"],
            }
            for c in pendentes
        ],
        "pagos": [
            {
                "contrato":          c["contrato"],
                "rota":              c["rota"],
                "nr_rpa":            c["nr_rpa"],
                "data_rpa":          c["data_rpa"],
                "nome_motorista":    c.get("nome_motorista", "-"),
                "nome_proprietario": c.get("nome_proprietario", "-"),
                "vlr_liquido":       c["vlr_liquido"],
            }
            for c in pagos
        ],
    }


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    arg = sys.argv[1] if len(sys.argv) > 1 else "00000000000"
    if arg.startswith("--nome-exato:"):
        print(json.dumps(consultar_nome_exato(arg[13:]), ensure_ascii=False))
    elif arg.startswith("--nome:"):
        print(json.dumps(listar_nomes(arg[7:]), ensure_ascii=False))
    else:
        print(json.dumps(consultar_cpf(arg), ensure_ascii=False))
