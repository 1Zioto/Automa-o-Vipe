# ==============================================
# VIPE TRANSPORTES — LEITOR MULTAS EXCEL
# Retorna JSON para ser formatado pela OpenAI
# ==============================================

import zipfile, xml.etree.ElementTree as ET, re, os, io, sys, json
from datetime import datetime, timedelta, date

CAMINHO_EXCEL = r"C:\Users\User\Desktop\Bot\bot_vipe_transportes\Relatórios\Multas.xlsx"
NS = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def _serial_to_iso(valor):
    if not valor: return ''
    if 'T' in str(valor) or '/' in str(valor): return valor
    try:
        serial = float(valor)
        d = date(1899, 12, 30) + timedelta(days=int(serial))
        frac = serial - int(serial)
        seg = int(frac * 86400)
        h, m = seg // 3600, (seg % 3600) // 60
        return f"{d.isoformat()}T{h:02d}:{m:02d}:00.000Z"
    except: return valor

def _fmt_data(iso):
    if not iso: return '-'
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M')
    except: return str(iso)[:10]

def _fmt_venc(iso):
    if not iso: return '-'
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y')
    except: return str(iso)[:10]

def _vencida(iso):
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return dt.date() < datetime.now().date()
    except: return False

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
        0:'cpf', 1:'motorista', 2:'numero_ifr', 3:'ait', 4:'veiculo',
        5:'situacao', 6:'descricao', 7:'data_infracao', 8:'endereco', 9:'cidade',
        10:'vlr_multa', 11:'vlr_nic', 12:'vlr_total', 13:'data_vencimento', 14:'data_venc_nic'
    }

    registros = []
    cpf_atual = motorista_atual = ''

    for row in rows[1:]:
        vals = [get_val(c) for c in row.findall('ns:c', NS)]
        while len(vals) < 15: vals.append('')
        if not vals[3]: continue
        if str(vals[0]).strip() == 'Total': continue
        if vals[0] and vals[0] != '-': cpf_atual = vals[0].strip()
        if vals[1] and vals[1] != '-': motorista_atual = vals[1].strip()

        reg = {MAPA[i]: str(vals[i]).strip() for i in MAPA}
        reg['cpf'] = cpf_atual
        reg['motorista'] = motorista_atual
        for campo in ['data_infracao','data_vencimento','data_venc_nic']:
            reg[campo] = _serial_to_iso(reg[campo])
        for campo in ['vlr_multa','vlr_nic','vlr_total']:
            try: reg[campo] = float(reg[campo]) if reg[campo] else 0.0
            except: reg[campo] = 0.0
        registros.append(reg)
    return registros

def _limpar_cpf(cpf): return re.sub(r'\D', '', str(cpf))

def consultar_cpf(cpf, caminho=CAMINHO_EXCEL):
    registros = _ler_excel(caminho)
    cpf_limpo = _limpar_cpf(cpf)
    multas = [r for r in registros if _limpar_cpf(r['cpf']) == cpf_limpo]

    if not multas:
        return {"encontrado": False, "cpf": cpf}

    vencidas  = [m for m in multas if _vencida(m['data_vencimento'])]
    a_vencer  = [m for m in multas if not _vencida(m['data_vencimento'])]

    return {
        "encontrado": True,
        "cpf": cpf,
        "nome": multas[0]['motorista'],
        "total_multas": len(multas),
        "total_vencidas": len(vencidas),
        "total_a_vencer": len(a_vencer),
        "valor_multas": sum(m['vlr_multa'] for m in multas),
        "valor_nics": sum(m['vlr_nic'] for m in multas),
        "valor_total": sum(m['vlr_total'] for m in multas),
        "multas": [
            {
                "ait": m['ait'],
                "numero_ifr": m['numero_ifr'],
                "veiculo": m['veiculo'],
                "descricao": m['descricao'],
                "data_infracao": _fmt_data(m['data_infracao']),
                "endereco": m['endereco'],
                "cidade": m['cidade'],
                "vlr_multa": m['vlr_multa'],
                "vlr_nic": m['vlr_nic'],
                "vlr_total": m['vlr_total'],
                "vencimento": _fmt_venc(m['data_vencimento']),
                "vencida": _vencida(m['data_vencimento']),
            } for m in multas
        ]
    }



def _sem_acento(texto):
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


def listar_nomes(termo, caminho=CAMINHO_EXCEL):
    """Retorna nomes únicos de motoristas que contêm o termo."""
    registros = _ler_excel(caminho)
    t = _sem_acento(termo).strip()
    nomes = set()
    for r in registros:
        n = r.get('motorista', '').strip()
        n_limpo = re.sub(r'^[\d.\-/]+\s*', '', n).strip()
        if n_limpo and t in _sem_acento(n_limpo):
            nomes.add(n_limpo)
    return {"encontrado": len(nomes) > 0, "nomes": sorted(nomes)}


def consultar_nome_exato(nome, caminho=CAMINHO_EXCEL):
    """Retorna multas de um motorista pelo nome exato."""
    registros = _ler_excel(caminho)
    nome_lower = _sem_acento(nome).strip()
    multas = [r for r in registros if _sem_acento(r.get('motorista', '')) == nome_lower]

    if not multas:
        return {"encontrado": False, "nome": nome}

    vencidas = [m for m in multas if _vencida(m['data_vencimento'])]
    a_vencer = [m for m in multas if not _vencida(m['data_vencimento'])]

    return {
        "encontrado": True,
        "nome": multas[0]['motorista'],
        "cpf": multas[0]['cpf'],
        "total_multas": len(multas),
        "total_vencidas": len(vencidas),
        "total_a_vencer": len(a_vencer),
        "valor_multas": sum(m['vlr_multa'] for m in multas),
        "valor_nics": sum(m['vlr_nic'] for m in multas),
        "valor_total": sum(m['vlr_total'] for m in multas),
        "multas": [
            {
                "ait": m['ait'], "numero_ifr": m['numero_ifr'],
                "veiculo": m['veiculo'], "descricao": m['descricao'],
                "data_infracao": _fmt_data(m['data_infracao']),
                "endereco": m['endereco'], "cidade": m['cidade'],
                "vlr_multa": m['vlr_multa'], "vlr_nic": m['vlr_nic'],
                "vlr_total": m['vlr_total'],
                "vencimento": _fmt_venc(m['data_vencimento']),
                "vencida": _vencida(m['data_vencimento']),
            } for m in multas
        ]
    }

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    arg = sys.argv[1] if len(sys.argv) > 1 else "00000000000"
    if arg.startswith('--nome-exato:'):
        print(json.dumps(consultar_nome_exato(arg[13:]), ensure_ascii=False))
    elif arg.startswith('--nome:'):
        print(json.dumps(listar_nomes(arg[7:]), ensure_ascii=False))
    else:
        print(json.dumps(consultar_cpf(arg), ensure_ascii=False))
