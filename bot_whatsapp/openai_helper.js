// ==============================================
// VIPE TRANSPORTES — INTEGRAÇÃO OPENAI
// ==============================================

const https = require('https');

const OPENAI_KEY = process.env.OPENAI_API_KEY;
const MODEL      = 'gpt-4o-mini';
const MAX_TOKENS = 2000;

const SYSTEM_PROMPT = `Você é a Ana, assistente virtual da Vipe Transportes.
Seu tom é amigável e humano, como uma atendente real pelo WhatsApp.
Use emojis com moderação. Formate valores em R$ (ex: R$ 1.234,56). Datas em DD/MM/AAAA.
Nunca invente dados — use apenas o que for fornecido.
Escreva em português do Brasil.`;

function chamarOpenAI(mensagens) {
    return new Promise((resolve, reject) => {
        if (!OPENAI_KEY) { reject(new Error('OPENAI_API_KEY não configurada')); return; }

        const body = JSON.stringify({
            model: MODEL,
            max_tokens: MAX_TOKENS,
            temperature: 0.4,
            messages: mensagens,
        });

        const options = {
            hostname: 'api.openai.com',
            path: '/v1/chat/completions',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${OPENAI_KEY}`,
                'Content-Length': Buffer.byteLength(body),
            },
        };

        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const json = JSON.parse(data);
                    if (json.error) reject(new Error(json.error.message));
                    else resolve(json.choices[0].message.content.trim());
                } catch (e) { reject(e); }
            });
        });

        req.on('error', reject);
        req.setTimeout(30000, () => req.destroy(new Error('Timeout OpenAI')));
        req.write(body);
        req.end();
    });
}

// ==============================
// BOAS-VINDAS
// ==============================
async function gerarBoasVindas() {
    return chamarOpenAI([
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content:
            'Crie uma saudação curta e amigável de boas-vindas para um motorista que entrou no atendimento da Vipe Transportes. ' +
            'Máximo 2 linhas. Não mencione as opções do menu.' }
    ]);
}

// ==============================
// SALDO CIOT
// ==============================
async function gerarRespostaCIOT(dados) {
    if (!dados.encontrado) {
        return chamarOpenAI([
            { role: 'system', content: SYSTEM_PROMPT },
            { role: 'user', content:
                `CPF/nome consultado: ${dados.cpf || dados.nome}. Nenhum contrato encontrado nos últimos 30 dias. ` +
                'Informe isso de forma amigável, mencione os "últimos 30 dias" e sugira verificar os dados.' }
        ]);
    }

    // Monta a resposta estruturada diretamente — OpenAI só humaniza o texto livre
    const d = dados;

    const br = v => `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;

    let resposta =
        `👤 *${d.nome}*\n` +
        `🪪 CPF: \`${formatarCPF(d.cpf)}\`\n` +
        `━━━━━━━━━━━━━━━━━━━━\n` +
        `📅 *RESUMO — últimos 30 dias*\n` +
        `📊 *RESUMO*\n` +
        `• Total de contratos:  *${d.total_contratos}*\n` +
        `• Pagos:               *${d.total_pagos}*\n` +
        `• Pendentes:           *${d.total_pendentes}*\n` +
        `• Total contratado:    *${br(d.valor_total_contratado)}*\n` +
        `• Total pago:          *${br(d.valor_total_pago)}*\n` +
        `• 🔴 Saldo em aberto:  *${br(d.valor_total_pendente)}*\n` +
        `━━━━━━━━━━━━━━━━━━━━\n`;

    if (d.pendentes && d.pendentes.length > 0) {
        resposta += `⏳ *CONTRATOS PENDENTES*\n`;
        for (const [idx, c] of d.pendentes.entries()) {
            if (idx > 0) resposta += `\n─────────────────────\n`;
            resposta +=
                `📋 Contrato *${c.contrato}*\n` +
                `   Filial:      ${c.filial || '-'}\n` +
                `   Emissão:     ${c.emissao || '-'}\n` +
                `   Rota:        ${c.rota || '-'}\n` +
                `   Manifesto:   ${c.manifesto || '-'}\n` +
                `   Motorista:   ${c.nome_motorista || '-'}\n` +
                `   Proprietário:${c.nome_proprietario || '-'}\n` +
                `   Contratado:  ${br(c.vlr_contratado)}\n` +
                `   Adiantado:   ${br(c.adiantamento)}\n` +
                `   💰 Líquido:  *${br(c.vlr_liquido)}*\n`;
        }
    }

    if (d.pagos && d.pagos.length > 0) {
        resposta += `\n✅ *CONTRATOS PAGOS*\n`;
        for (const [idx, c] of d.pagos.entries()) {
            if (idx > 0) resposta += `\n─────────────────────\n`;
            resposta +=
                `📋 Contrato *${c.contrato}* — RPA ${c.nr_rpa}\n` +
                `   💳 Pago em:   *${c.data_rpa || '-'}*\n` +
                `   Rota:        ${c.rota || '-'}\n` +
                `   Motorista:   ${c.nome_motorista || '-'}\n` +
                `   Proprietário:${c.nome_proprietario || '-'}\n` +
                `   💰 Líquido:  *${br(c.vlr_liquido)}*\n`;
        }
    }

    resposta +=
        `━━━━━━━━━━━━━━━━━━━━\n` +
        `📅 *RESUMO — últimos 30 dias*\n` +
        `Digite outro *CPF* para nova consulta\nou *menu* para voltar ao início.`;

    return resposta;
}

// ==============================
// MULTAS
// ==============================
async function gerarRespostaMultas(dados) {
    if (!dados.encontrado) {
        return chamarOpenAI([
            { role: 'system', content: SYSTEM_PROMPT },
            { role: 'user', content:
                `CPF/nome consultado: ${dados.cpf || dados.nome}. Nenhuma multa em aberto encontrada nos últimos 30 dias. ` +
                'Escreva uma mensagem curta comemorando que está limpo, mencionando "últimos 30 dias".' }
        ]);
    }

    const d = dados;
    const br = v => `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;

    let resposta =
        `🚨 *MULTAS EM ABERTO*\n\n` +
        `👤 *${d.nome}*\n` +
        `🪪 CPF: \`${formatarCPF(d.cpf)}\`\n\n` +
        `━━━━━━━━━━━━━━━━━━━━\n` +
        `📅 *RESUMO — últimos 30 dias*\n` +
        `📊 *RESUMO*\n` +
        `• Total de multas:   *${d.total_multas}*\n` +
        `• Vencidas:          *${d.total_vencidas}*  ⚠️\n` +
        `• A vencer:          *${d.total_a_vencer}*\n` +
        `• Valor das multas:  *${br(d.valor_multas)}*\n` +
        `• Valor das NICs:    *${br(d.valor_nics)}*\n` +
        `• 💰 Total geral:    *${br(d.valor_total)}*\n` +
        `━━━━━━━━━━━━━━━━━━━━\n`;

    const vencidas = d.multas.filter(m => m.vencida);
    const avencer  = d.multas.filter(m => !m.vencida);

    if (vencidas.length > 0) {
        resposta += `\n⚠️ *VENCIDAS*\n\n`;
        for (const [i, m] of vencidas.entries()) {
            resposta += _linhaMulta(i + 1, m, br);
        }
    }

    if (avencer.length > 0) {
        resposta += `\n📅 *A VENCER*\n\n`;
        for (const [i, m] of avencer.entries()) {
            resposta += _linhaMulta(i + 1, m, br);
        }
    }

    resposta +=
        `━━━━━━━━━━━━━━━━━━━━\n` +
        `📅 *RESUMO — últimos 30 dias*\n` +
        `Digite outro *CPF* para nova consulta\nou *menu* para voltar ao início.`;

    return resposta;
}

function _linhaMulta(i, m, br) {
    let linha =
        `🚗 *Multa ${i} — AIT ${m.ait}*\n` +
        `   Nº Processo:  ${m.numero_ifr || '-'}\n` +
        `   Veículo:      ${m.veiculo || '-'}\n` +
        `   Infração:     ${m.descricao || '-'}\n` +
        `   Data:         ${m.data_infracao || '-'}\n` +
        `   Local:        ${m.endereco || '-'}\n` +
        `   Cidade:       ${m.cidade || '-'}\n` +
        `   Multa:        ${br(m.vlr_multa)}`;

    if (m.vlr_nic > 0) {
        linha += `\n   NIC:          ${br(m.vlr_nic)}`;
    }

    linha +=
        `\n   💰 Total:     *${br(m.vlr_total)}*\n` +
        `   Vencimento:   ${m.vencida ? '⚠️ ' : ''}${m.vencimento}${m.vencida ? ' (VENCIDA)' : ''}\n\n`;

    return linha;
}

// ==============================
// ERRO
// ==============================
async function gerarMensagemErro(contexto) {
    return chamarOpenAI([
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content:
            `Ocorreu um erro ao processar: ${contexto}. ` +
            'Escreva uma mensagem curta pedindo desculpas e orientando a tentar novamente ou digitar "menu".' }
    ]);
}

// ==============================
// ENCERRAMENTO
// ==============================
async function gerarMensagemEncerramento(motivo) {
    const ctx = motivo === 'timeout'
        ? 'O atendimento foi encerrado automaticamente por 5 minutos de inatividade.'
        : 'O usuário escolheu encerrar o atendimento.';
    return chamarOpenAI([
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content:
            `${ctx} Escreva uma despedida curta e amigável, dizendo que estaremos disponíveis quando precisar.` }
    ]);
}

// ==============================
// HELPER CPF
// ==============================
function formatarCPF(cpf) {
    const d = String(cpf).replace(/\D/g, '');
    if (d.length === 11) return `${d.slice(0,3)}.${d.slice(3,6)}.${d.slice(6,9)}-${d.slice(9)}`;
    return cpf;
}

module.exports = {
    gerarBoasVindas,
    gerarRespostaCIOT,
    gerarRespostaMultas,
    gerarMensagemErro,
    gerarMensagemEncerramento,
};
