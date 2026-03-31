# 🚛 Vipe Transportes — Bot CIOT v2

## Estrutura

```
vipe_v2/
├── .env.example
├── sql/
│   └── schema.sql          ← apenas 2 tabelas: contatos + consultas
├── python_api/
│   ├── main.py             ← FastAPI: consulta Aleff, salva DB, formata resposta
│   └── requirements.txt
└── bot_whatsapp/
    ├── main.js             ← bot Node.js com máquina de estados
    └── package.json
```

---

## O que o banco armazena

| Tabela | O que guarda |
|--------|-------------|
| `contatos` | Quando o número entrou em contato, quantas consultas fez |
| `consultas` | CPF/nome buscado, resultado consolidado (totais + JSON completo), status |

**Nada mais.** Não há log de mensagens, não há tabelas de CIOTs individuais persistidas — tudo é consultado ao vivo na API Aleff a cada solicitação.

---

## Fluxo de uma consulta

```
Usuário → "Consulta CIOT" (opção 1 no menu)
Bot → "Informe CPF ou nome"
Usuário → "060.707.965-78"  (ou "João Silva")
Bot → "⏳ Consultando..."
       │
       ├─► API Python detecta tipo (CPF)
       ├─► Duas chamadas paralelas à API Aleff (operacional + financeiro)
       ├─► Cruza dados pelo número do CIOT
       ├─► Filtra por CPF/nome
       ├─► Salva no MySQL (contato + resumo)
       └─► Retorna texto formatado pronto
Bot → envia resposta completa ao usuário
```

---

## Saída esperada no WhatsApp

```
👤 JOÃO DA SILVA
🔎 Consulta por CPF: 06070796578
📅 Período: últimos 30 dias

━━━━━━━━━━━━━━━━━━━━
📊 RESUMO
• Total de CIOTs:       3
• Total contratado:     R$ 4.500,00
• Total pago:           R$ 3.200,00
• Total pendente:       R$ 1.300,00
• CIOTs em aberto:      2
━━━━━━━━━━━━━━━━━━━━

📋 CIOT 1 — 123456789  ✅ Quitado
   Documento:   NF-00123 / Série: 1
   Filial:      São Paulo
   Contratado:  R$ 1.500,00
   Pago:        R$ 1.500,00
   Pendente:    R$ 0,00

📋 CIOT 2 — 987654321  ⏳ Pendente
   ...
```

---

## Passo a Passo para rodar

### 1. Configurar .env

```bash
cp .env.example .env
# edite o .env se necessário
```

### 2. Criar tabelas no MySQL

```bash
mysql -h 98.80.70.12 -P 3306 -u douglas -p vipe_transportes < sql/schema.sql
```

### 3. Rodar API Python

```bash
cd python_api
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt

# Copiar .env
cp ../.env .env

uvicorn main:app --host 0.0.0.0 --port 8000
```

Teste: `GET http://localhost:8000/health` → `{"status":"ok"}`

Documentação automática: `http://localhost:8000/docs`

### 4. Rodar Bot Node.js

```bash
cd bot_whatsapp
npm install
cp ../.env .env
node main.js
```

Escaneie o QR Code com o WhatsApp.

---

## Testando a API diretamente (curl / Postman)

```bash
# Consulta por CPF
curl -X POST http://localhost:8000/consulta/ciot \
  -H "Content-Type: application/json" \
  -d '{"whatsapp_id": "teste", "mensagem": "060.707.965-78"}'

# Consulta por nome
curl -X POST http://localhost:8000/consulta/ciot \
  -H "Content-Type: application/json" \
  -d '{"whatsapp_id": "teste", "mensagem": "João Silva"}'

# Saudação
curl -X POST http://localhost:8000/consulta/ciot \
  -H "Content-Type: application/json" \
  -d '{"whatsapp_id": "teste", "mensagem": "oi"}'
```
