# ==============================================
# VIPE TRANSPORTES — RELATÓRIO DE PENDÊNCIAS
# Uma linha por motorista — resumo consolidado
# ==============================================

import sys, io, os, json, re
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(__file__))
import ciot_excel
import multas_excel

CAMINHO_CIOT   = r"C:\Users\User\Desktop\Bot\bot_vipe_transportes\Relatórios\Ciot.xls"
CAMINHO_MULTAS = r"C:\Users\User\Desktop\Bot\bot_vipe_transportes\Relatórios\Multas.xlsx"
CAMINHO_SAIDA  = r"C:\Users\User\Desktop\Bot\bot_vipe_transportes\Relatórios\Pendencias.pdf"

def br(v):
    try:
        return f"R$ {float(v or 0):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except:
        return "R$ 0,00"

def vencida(iso):
    try:
        from datetime import datetime as dt
        d = dt.fromisoformat(str(iso).replace('Z','+00:00'))
        return d.date() < date.today()
    except:
        return False

def gerar_pdf(caminho_saida=CAMINHO_SAIDA):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable, KeepTogether)
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

    pg = landscape(A4)
    largura, altura = pg

    doc = SimpleDocTemplate(
        caminho_saida, pagesize=pg,
        rightMargin=1.2*cm, leftMargin=1.2*cm,
        topMargin=1.2*cm, bottomMargin=1.2*cm,
    )

    # Estilos
    def estilo(nome, **kw):
        return ParagraphStyle(nome, **kw)

    s_titulo   = estilo('t',  fontSize=15, fontName='Helvetica-Bold',   alignment=TA_CENTER, spaceAfter=3,  textColor=colors.HexColor('#1a1a2e'))
    s_sub      = estilo('s',  fontSize=9,  fontName='Helvetica',        alignment=TA_CENTER, spaceAfter=10, textColor=colors.HexColor('#555555'))
    s_sec      = estilo('sc', fontSize=11, fontName='Helvetica-Bold',   textColor=colors.white, spaceBefore=12, spaceAfter=4)
    s_normal   = estilo('n',  fontSize=8,  fontName='Helvetica',        leading=11)
    s_neg      = estilo('nb', fontSize=8,  fontName='Helvetica-Bold',   leading=11)
    s_total    = estilo('tt', fontSize=9,  fontName='Helvetica-Bold',   alignment=TA_RIGHT,  textColor=colors.HexColor('#922b21'))
    s_rodape   = estilo('r',  fontSize=7,  fontName='Helvetica',        alignment=TA_CENTER, textColor=colors.HexColor('#999999'))

    COR_AZUL   = colors.HexColor('#2c3e50')
    COR_VERM   = colors.HexColor('#922b21')
    COR_CINZA1 = colors.HexColor('#f8f9fa')
    COR_CINZA2 = colors.white
    COR_HEADER = colors.HexColor('#34495e')
    COR_HVERM  = colors.HexColor('#7b241c')

    historia = []

    # Cabeçalho
    historia.append(Paragraph("VIPE TRANSPORTES", s_titulo))
    historia.append(Paragraph(
        f"Relatório de Pendências — {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
        s_sub))
    historia.append(HRFlowable(width="100%", thickness=1.5, color=COR_AZUL, spaceAfter=8))

    # =========================================
    # SEÇÃO 1: CIOT — resumo por motorista
    # =========================================
    try:
        registros_ciot = ciot_excel._ler_excel(CAMINHO_CIOT)
        pendentes_ciot = [r for r in registros_ciot if r.get('pendente')]
    except Exception as e:
        pendentes_ciot = []
        historia.append(Paragraph(f"Erro ao ler CIOT: {e}", s_normal))

    # Agrupa por chave única (motorista + proprietário)
    grupos = {}
    for r in pendentes_ciot:
        mot  = (r.get('nome_motorista','') or '').strip() or '-'
        prop = (r.get('nome_proprietario','') or '').strip() or '-'
        chave = f"{mot}|{prop}"
        if chave not in grupos:
            grupos[chave] = {
                'motorista':    mot,
                'proprietario': prop,
                'contratado':   0.0,
                'adiantado':    0.0,
                'pendente':     0.0,
                'contratos':    0,
            }
        grupos[chave]['contratado'] += float(r.get('vlr_contratado', 0) or 0)
        grupos[chave]['adiantado']  += float(r.get('adiantamentos',  0) or 0)
        grupos[chave]['pendente']   += float(r.get('vlr_liquido',    0) or 0)
        grupos[chave]['contratos']  += 1

    # Ordena por pendente desc
    linhas_ciot = sorted(grupos.values(), key=lambda x: x['pendente'], reverse=True)

    total_contratos  = sum(g['contratos']  for g in linhas_ciot)
    total_contratado = sum(g['contratado'] for g in linhas_ciot)
    total_adiantado  = sum(g['adiantado']  for g in linhas_ciot)
    total_pendente   = sum(g['pendente']   for g in linhas_ciot)

    # Cabeçalho seção
    historia.append(KeepTogether([
        Table([[Paragraph(
            f"  SALDO CIOT EM ABERTO  —  {len(linhas_ciot)} motorista(s)  |  {total_contratos} contrato(s)", s_sec)]],
            colWidths=[largura - 2.4*cm],
            style=TableStyle([
                ('BACKGROUND',    (0,0),(-1,-1), COR_AZUL),
                ('TOPPADDING',    (0,0),(-1,-1), 5),
                ('BOTTOMPADDING', (0,0),(-1,-1), 5),
                ('LEFTPADDING',   (0,0),(-1,-1), 8),
            ])
        ),
    ]))

    if linhas_ciot:
        # Cabeçalho da tabela
        cab = [
            Paragraph('<b>Motorista</b>',    s_neg),
            Paragraph('<b>Proprietário</b>', s_neg),
            Paragraph('<b>Contratos</b>',    s_neg),
            Paragraph('<b>Contratado</b>',   s_neg),
            Paragraph('<b>Adiantado</b>',    s_neg),
            Paragraph('<b>Pendente</b>',     s_neg),
        ]
        dados = [cab]
        for g in linhas_ciot:
            dados.append([
                Paragraph(g['motorista'][:35],    s_normal),
                Paragraph(g['proprietario'][:35], s_normal),
                Paragraph(str(g['contratos']),    s_normal),
                Paragraph(br(g['contratado']),    s_normal),
                Paragraph(br(g['adiantado']),     s_normal),
                Paragraph(f"<b>{br(g['pendente'])}</b>", s_neg),
            ])
        # Linha de total
        dados.append([
            Paragraph('<b>TOTAL</b>', s_neg),
            Paragraph('', s_normal),
            Paragraph(f'<b>{total_contratos}</b>', s_neg),
            Paragraph(f'<b>{br(total_contratado)}</b>', s_neg),
            Paragraph(f'<b>{br(total_adiantado)}</b>',  s_neg),
            Paragraph(f'<b>{br(total_pendente)}</b>',   s_neg),
        ])

        tabela = Table(dados,
            colWidths=[6.5*cm, 6.5*cm, 2.0*cm, 3.5*cm, 3.5*cm, 3.5*cm],
            repeatRows=1,
        )
        tabela.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0),   COR_HEADER),
            ('TEXTCOLOR',     (0,0), (-1,0),   colors.white),
            ('ROWBACKGROUNDS',(0,1), (-1,-2),  [COR_CINZA1, COR_CINZA2]),
            ('BACKGROUND',    (0,-1),(-1,-1),  colors.HexColor('#dce8f5')),
            ('GRID',          (0,0), (-1,-1),  0.3, colors.HexColor('#c8d6e5')),
            ('TOPPADDING',    (0,0), (-1,-1),  4),
            ('BOTTOMPADDING', (0,0), (-1,-1),  4),
            ('LEFTPADDING',   (0,0), (-1,-1),  5),
            ('RIGHTPADDING',  (0,0), (-1,-1),  5),
            ('ALIGN',         (2,0), (-1,-1),  'RIGHT'),
            ('FONTSIZE',      (0,0), (-1,-1),  8),
        ]))
        historia.append(tabela)
    else:
        historia.append(Paragraph("Nenhum CIOT com saldo em aberto.", s_normal))

    historia.append(Spacer(1, 14))

    # =========================================
    # SEÇÃO 2: MULTAS — resumo por motorista
    # =========================================
    try:
        registros_multas = multas_excel._ler_excel(CAMINHO_MULTAS)
    except Exception as e:
        registros_multas = []
        historia.append(Paragraph(f"Erro ao ler Multas: {e}", s_normal))

    # Agrupa por motorista
    grupos_m = {}
    for m in registros_multas:
        mot = (m.get('motorista','') or '').strip() or '-'
        if mot not in grupos_m:
            grupos_m[mot] = {
                'motorista': mot,
                'multas':    0,
                'vencidas':  0,
                'vlr_multa': 0.0,
                'vlr_nic':   0.0,
                'total':     0.0,
            }
        grupos_m[mot]['multas']    += 1
        grupos_m[mot]['vlr_multa'] += float(m.get('vlr_multa', 0) or 0)
        grupos_m[mot]['vlr_nic']   += float(m.get('vlr_nic',   0) or 0)
        grupos_m[mot]['total']     += float(m.get('vlr_total', 0) or 0)
        if vencida(m.get('data_vencimento','')):
            grupos_m[mot]['vencidas'] += 1

    linhas_m = sorted(grupos_m.values(), key=lambda x: x['total'], reverse=True)

    tot_multas    = sum(g['multas']    for g in linhas_m)
    tot_vencidas  = sum(g['vencidas']  for g in linhas_m)
    tot_vlr_multa = sum(g['vlr_multa'] for g in linhas_m)
    tot_vlr_nic   = sum(g['vlr_nic']   for g in linhas_m)
    tot_total     = sum(g['total']     for g in linhas_m)

    historia.append(KeepTogether([
        Table([[Paragraph(
            f"  MULTAS EM ABERTO  —  {len(linhas_m)} motorista(s)  |  {tot_multas} multa(s)  |  {tot_vencidas} vencida(s)", s_sec)]],
            colWidths=[largura - 2.4*cm],
            style=TableStyle([
                ('BACKGROUND',    (0,0),(-1,-1), COR_VERM),
                ('TOPPADDING',    (0,0),(-1,-1), 5),
                ('BOTTOMPADDING', (0,0),(-1,-1), 5),
                ('LEFTPADDING',   (0,0),(-1,-1), 8),
            ])
        ),
    ]))

    if linhas_m:
        cab_m = [
            Paragraph('<b>Motorista</b>',      s_neg),
            Paragraph('<b>Multas</b>',         s_neg),
            Paragraph('<b>Vencidas</b>',       s_neg),
            Paragraph('<b>Valor Multas</b>',   s_neg),
            Paragraph('<b>Valor NICs</b>',     s_neg),
            Paragraph('<b>Total</b>',          s_neg),
        ]
        dados_m = [cab_m]
        for g in linhas_m:
            venc_txt = f'<font color="red"><b>{g["vencidas"]}</b></font>' if g['vencidas'] > 0 else '0'
            dados_m.append([
                Paragraph(g['motorista'][:50],    s_normal),
                Paragraph(str(g['multas']),        s_normal),
                Paragraph(venc_txt,                s_normal),
                Paragraph(br(g['vlr_multa']),      s_normal),
                Paragraph(br(g['vlr_nic']),        s_normal),
                Paragraph(f"<b>{br(g['total'])}</b>", s_neg),
            ])
        # Linha de total
        dados_m.append([
            Paragraph('<b>TOTAL</b>', s_neg),
            Paragraph(f'<b>{tot_multas}</b>',         s_neg),
            Paragraph(f'<b>{tot_vencidas}</b>',        s_neg),
            Paragraph(f'<b>{br(tot_vlr_multa)}</b>',  s_neg),
            Paragraph(f'<b>{br(tot_vlr_nic)}</b>',    s_neg),
            Paragraph(f'<b>{br(tot_total)}</b>',      s_neg),
        ])

        tab_m = Table(dados_m,
            colWidths=[8.5*cm, 2.0*cm, 2.0*cm, 3.5*cm, 3.5*cm, 3.5*cm],
            repeatRows=1,
        )
        tab_m.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0),  COR_HVERM),
            ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
            ('ROWBACKGROUNDS',(0,1), (-1,-2), [colors.HexColor('#fdf2f2'), colors.white]),
            ('BACKGROUND',    (0,-1),(-1,-1), colors.HexColor('#f5d0ce')),
            ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#f5c6c6')),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING',   (0,0), (-1,-1), 5),
            ('RIGHTPADDING',  (0,0), (-1,-1), 5),
            ('ALIGN',         (1,0), (-1,-1), 'RIGHT'),
            ('FONTSIZE',      (0,0), (-1,-1), 8),
        ]))
        historia.append(tab_m)
    else:
        historia.append(Paragraph("Nenhuma multa em aberto.", s_normal))

    # Rodapé
    historia.append(Spacer(1, 14))
    historia.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc')))
    historia.append(Spacer(1, 4))
    historia.append(Paragraph(
        f"Vipe Transportes — Relatório gerado automaticamente em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        s_rodape))

    doc.build(historia)
    return caminho_saida


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    saida = sys.argv[1] if len(sys.argv) > 1 else CAMINHO_SAIDA
    caminho = gerar_pdf(saida)
    print(json.dumps({"ok": True, "arquivo": caminho}, ensure_ascii=False))
