# ==============================================
# VIPE TRANSPORTES — API PYTHON (FastAPI)
# Cache em memória RAM — sem banco de dados
# Fluxo:
#   1. Na primeira consulta (ou se cache expirado),
#      busca TUDO dos últimos 30 dias da API Aleff
#   2. Armazena em RAM (cache_dados)
#   3. Filtra localmente por nome
#   4. Cache expira após CACHE_TTL_MINUTOS
# ==============================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import aiohttp
import pandas as pd
import re
import json
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vipe_api")

app = FastAPI(title="Vipe Transportes — CIOT API", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TOKEN            = os.getenv("ALEFF_TOKEN",        "f7177163c833dff4b38fc8d2872f1ec6")
COD_TRANSP       = int(os.getenv("ALEFF_COD_TRANSP", "44"))
DIAS             = 30
CACHE_TTL_MINUTOS = 30   # cache expira em 30 minutos — ajuste se quiser


# ==============================
# CACHE EM MEMÓRIA RAM
# Guarda o DataFrame consolidado e o horário da carga
# Some automaticamente quando o processo é reiniciado
# ==============================
cache_dados = {
    "df":          None,   # pd.DataFrame consolidado
    "carregado_em": None,  # datetime da última carga
}

def cache_valido() -> bool:
    if cache_dados["df"] is None or cache_dados["carregado_em"] is None:
        return False
    idade = (datetime.now() - cache_dados["carregado_em"]).total_seconds() / 60
    return idade < CACHE_TTL_MINUTOS

def cache_salvar(df: pd.DataFrame):
    cache_dados["df"]           = df
    cache_dados["carregado_em"] = datetime.now()
    logger.info(f"[CACHE] Salvo em RAM — {len(df)} registros consolidados. "
                f"Expira em {CACHE_TTL_MINUTOS} min.")

def cache_limpar():
    cache_dados["df"]           = None
    cache_dados["carregado_em"] = None
    logger.info("[CACHE] Limpo manualmente.")


# ==============================
# HELPERS
# ==============================
def normalizar(texto) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

def detectar_tipo_busca(entrada: str) -> tuple[str, str]:
    entrada = entrada.strip()
    if re.match(r"^(oi|ol[aá]|boa\s*(tarde|noite|manh[aã])|bom\s*dia|tudo\s*(bem|bom)|hey|hi|hello)[\s!.]*$",
                normalizar(entrada)):
        return "saudacao", ""
    apenas_digitos = re.sub(r"\D", "", entrada)
    if len(apenas_digitos) == 11:
        return "cpf", apenas_digitos
    return "nome", entrada

def extrair_numero_ciot(historico) -> str | None:
    m = re.search(r"CIOT\s*(\d+)", str(historico or ""), re.IGNORECASE)
    return m.group(1) if m else None

def br(valor) -> str:
    try:
        v = float(valor or 0)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def status_ciot(falta: float) -> str:
    if falta > 0.01:  return "⏳ Pendente"
    if falta < -0.01: return "➕ Excedente"
    return "✅ Quitado"

def datas_periodo() -> tuple[str, str]:
    hoje = datetime.now()
    return (hoje - timedelta(days=DIAS)).strftime("%Y-%m-%d"), hoje.strftime("%Y-%m-%d")


# ==============================
# CHAMADAS À API ALEFF
# ==============================
def tratar_resposta_xml(text: str) -> list:
    text = text.strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        root = ET.fromstring(text)
        if root.text:
            return json.loads(root.text)
    except Exception:
        pass
    return []

async def fetch_operacional(session, data_ini, data_fim) -> list:
    url = "https://ws.aleff.com.br/WsClientes/ClientesBI.asmx/RequestDataBI"
    params = {"Token": TOKEN, "CodTransp": COD_TRANSP, "FilialOrigem": "",
              "FilialDestino": "", "DataInicial": data_ini, "DataFinal": data_fim, "Cliente": ""}
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=45)) as r:
        return tratar_resposta_xml(await r.text())

async def fetch_financeiro(session, data_ini, data_fim) -> list:
    url = "https://ws.aleff.com.br/WsClientes/ClientesBI.asmx/RequestDataFinanceiroBI"
    params = {"Token": TOKEN, "CodTransp": COD_TRANSP, "FilialEmissao": "", "FilialCusto": "",
              "DataInicial": data_ini, "DataFinal": data_fim, "TipoData": "PP", "IncluirCanc": ""}
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=45)) as r:
        return tratar_resposta_xml(await r.text())


# ==============================
# CARREGA E CONSOLIDA TUDO EM RAM
# ==============================
async def carregar_cache():
    """
    Busca TODOS os dados dos últimos 30 dias,
    cruza operacional + financeiro pelo CIOT
    e salva o DataFrame consolidado em RAM.
    """
    data_ini, data_fim = datas_periodo()
    logger.info(f"[CACHE] Carregando dados {data_ini} → {data_fim} ...")

    async with aiohttp.ClientSession() as session:
        op_raw, fin_raw = await asyncio.gather(
            fetch_operacional(session, data_ini, data_fim),
            fetch_financeiro(session, data_ini, data_fim),
        )

    logger.info(f"[API] Operacional: {len(op_raw)} | Financeiro: {len(fin_raw)}")

    if not op_raw:
        logger.warning("[CACHE] Operacional veio vazio — cache não atualizado.")
        return

    df_op = pd.DataFrame(op_raw)
    df_op["_CIOT"]  = df_op["NumContrato_Viagem"].astype(str).str.strip()
    df_op["_VALOR"] = pd.to_numeric(df_op["Valor_Carreteiro"], errors="coerce").fillna(0)

    # Financeiro
    if fin_raw:
        df_fin = pd.DataFrame(fin_raw)
        df_fin["_CIOT"] = df_fin["Historico"].apply(extrair_numero_ciot).astype(str).str.strip()
        df_fin["_PAGO"] = pd.to_numeric(df_fin["TotalPago"], errors="coerce").fillna(0)
        df_fin = df_fin[df_fin["_CIOT"].notna() & (df_fin["_CIOT"] != "None")]
        df_fin_grp = df_fin.groupby("_CIOT", as_index=False)["_PAGO"].sum()
    else:
        df_fin_grp = pd.DataFrame(columns=["_CIOT", "_PAGO"])

    df = df_op.merge(df_fin_grp, on="_CIOT", how="left")
    df["_PAGO"]  = df["_PAGO"].fillna(0)
    df["_FALTA"] = df["_VALOR"] - df["_PAGO"]

    # Campos de texto normalizados para busca rápida local
    for col in ["Motorista", "NomeTomador", "NomeRemetente", "NomeDestinatario", "PlacaCavalo"]:
        if col in df.columns:
            df[f"_norm_{col}"] = df[col].apply(normalizar)
        else:
            df[f"_norm_{col}"] = ""

    cache_salvar(df)


# ==============================
# FILTRO LOCAL NO CACHE
# ==============================
def filtrar_local(termo: str) -> list:
    """
    Filtra o DataFrame em RAM por nome (parcial, sem acento, case-insensitive).
    Campos pesquisados: Motorista, NomeTomador, NomeRemetente, NomeDestinatario.
    """
    df = cache_dados["df"]
    termo_norm = normalizar(termo)

    campos = ["_norm_Motorista", "_norm_NomeTomador", "_norm_NomeRemetente", "_norm_NomeDestinatario"]
    campos_ok = [c for c in campos if c in df.columns]

    mask = pd.Series([False] * len(df), index=df.index)
    for col in campos_ok:
        mask = mask | df[col].str.contains(termo_norm, na=False)

    resultado_df = df[mask]
    logger.info(f"[FILTRO] '{termo}' → {len(resultado_df)} registros encontrados")

    ciots = []
    for _, row in resultado_df.iterrows():
        falta = float(row["_FALTA"])
        ciots.append({
            "ciot":          str(row["_CIOT"]),
            "motorista":     str(row.get("Motorista",        "-") or "-").strip(),
            "tomador":       str(row.get("NomeTomador",      "-") or "-").strip(),
            "placa":         str(row.get("PlacaCavalo",      "-") or "-").strip(),
            "documento":     str(row.get("Documento",        "-") or "-").strip(),
            "serie":         str(row.get("Serie",            "-") or "-").strip(),
            "filial_origem": str(row.get("FilialOrigem",     "-") or "-").strip(),
            "valor_ciot":    float(row["_VALOR"]),
            "pago":          float(row["_PAGO"]),
            "falta":         falta,
            "status":        status_ciot(falta),
        })
    return ciots


# ==============================
# FORMATAÇÃO
# ==============================
def montar_resposta(ciots: list, termo: str) -> str:
    if not ciots:
        return (
            f"🔍 Nenhum resultado para *{termo}* nos últimos {DIAS} dias.\n\n"
            "Dicas:\n"
            "• Tente apenas o primeiro nome ou sobrenome\n"
            "• Verifique a grafia\n\n"
            "Tente novamente."
        )

    total_contratado = sum(c["valor_ciot"] for c in ciots)
    total_pago       = sum(c["pago"]       for c in ciots)
    total_pendente   = sum(c["falta"]      for c in ciots if c["falta"] > 0.01)
    ciots_abertos    = sum(1 for c in ciots if c["falta"] > 0.01)
    nome_ref         = next((c["motorista"] for c in ciots if c["motorista"] not in ["-", "", "nan"]), termo)

    linhas = [
        f"👤 *{nome_ref}*",
        f"🔎 Consulta: `{termo}`",
        f"📅 Período: últimos {DIAS} dias",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📊 *RESUMO*",
        f"• Total de CIOTs:    *{len(ciots)}*",
        f"• Total contratado:  *{br(total_contratado)}*",
        f"• Total pago:        *{br(total_pago)}*",
        f"• Total pendente:    *{br(total_pendente)}*",
        f"• CIOTs em aberto:   *{ciots_abertos}*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for i, c in enumerate(ciots, 1):
        linhas += [
            f"📋 *CIOT {i} — {c['ciot']}*  {c['status']}",
            f"   Motorista:  {c['motorista']}",
            f"   Placa:      {c['placa']}",
            f"   Documento:  {c['documento']} / Série: {c['serie']}",
            f"   Filial:     {c['filial_origem']}",
            f"   Contratado: {br(c['valor_ciot'])}",
            f"   Pago:       {br(c['pago'])}",
            f"   Pendente:   {br(c['falta'])}",
            "",
        ]

    linhas += [
        "━━━━━━━━━━━━━━━━━━━━",
        "Digite outro nome para nova consulta\nou *menu* para voltar ao início.",
    ]
    return "\n".join(linhas)


# ==============================
# SCHEMAS
# ==============================
class ConsultaRequest(BaseModel):
    whatsapp_id: str
    mensagem:    str


# ==============================
# ROTAS
# ==============================
@app.get("/health")
def health():
    carregado = cache_dados["carregado_em"]
    registros = len(cache_dados["df"]) if cache_dados["df"] is not None else 0
    return {
        "status":       "ok",
        "versao":       "4.0.0",
        "cache_ativo":  cache_valido(),
        "registros":    registros,
        "carregado_em": carregado.strftime("%Y-%m-%d %H:%M:%S") if carregado else None,
        "expira_em_min": CACHE_TTL_MINUTOS,
    }


@app.post("/consulta/ciot")
async def consulta_ciot(req: ConsultaRequest):
    tipo, valor = detectar_tipo_busca(req.mensagem)

    if tipo == "saudacao":
        return {"tipo": "saudacao", "resposta": (
            "👋 Olá! Tudo bem?\n\n"
            "Sou o assistente de consulta CIOT da *Vipe Transportes*.\n\n"
            "Envie o *nome* do motorista para consultar.\n"
            "Exemplo: _João Silva_ ou apenas _João_\n\n"
            "Vou verificar os últimos 30 dias. 🚛"
        )}

    if tipo == "cpf":
        return {"tipo": "cpf", "resposta": (
            "⚠️ A API não disponibiliza CPF nos dados.\n\n"
            "Por favor, busque pelo *nome* do motorista.\n"
            "Exemplo: _João Silva_"
        )}

    # Carrega cache se necessário
    if not cache_valido():
        try:
            await carregar_cache()
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Timeout na API Aleff. Tente novamente.")
        except Exception as e:
            logger.error(f"[CACHE] Erro ao carregar: {e}")
            raise HTTPException(status_code=502, detail=str(e))

    if cache_dados["df"] is None:
        raise HTTPException(status_code=503, detail="Dados ainda não disponíveis. Tente novamente.")

    # Filtra localmente em RAM — instantâneo
    ciots    = filtrar_local(valor)
    resposta = montar_resposta(ciots, valor)

    return {"tipo": tipo, "termo": valor, "resposta": resposta, "total": len(ciots)}


@app.post("/cache/recarregar")
async def recarregar_cache():
    """Força recarregamento imediato do cache."""
    cache_limpar()
    try:
        await carregar_cache()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "ok": True,
        "registros": len(cache_dados["df"]) if cache_dados["df"] is not None else 0,
        "carregado_em": cache_dados["carregado_em"].strftime("%Y-%m-%d %H:%M:%S"),
    }
