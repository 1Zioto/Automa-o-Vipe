// ==============================================
// VIPE TRANSPORTES — BOT WHATSAPP
// Atendente: VIPI
// ==============================================

const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const { execFile } = require('child_process');
const path = require('path');
const ai = require('./openai_helper');
require('dotenv').config();

const PYTHON        = process.env.PYTHON_PATH || 'python';
const SCRIPT_CIOT   = path.join(__dirname, 'ciot_excel.py');
const SCRIPT_MULTA  = path.join(__dirname, 'multas_excel.py');
const SCRIPT_PDF     = path.join(__dirname, 'relatorio_pdf.py');
const SCRIPT_CHATBOT = path.join(__dirname, 'chatbot_vip.py');
const SCRIPT_CHAT   = path.join(__dirname, 'chatbot_vip.py');
const CAMINHO_PDF   = 'C:\\Users\\User\\Desktop\\Bot\\bot_vipe_transportes\\Relatórios\\Pendencias.pdf';
const TIMEOUT_MS    = 5 * 60 * 1000;

// ==============================
// LISTA VIP
// ==============================
const NUMEROS_VIP = new Set([
    '153265991852189@lid',
	'139534964666618@lid',
	'132268014198868@lid',
	'86548003463384@lid',
	'137417898106906@lid',
	'173907655037133@lid',
	'100729935151264@lid',
	'168659221753911@lid',
	'139534964666618@lid',
	'19748410683399@lid',
	'106605416824900@lid',
]);

function isVip(chatId) { return NUMEROS_VIP.has(chatId); }

// ==============================
// SAUDAÇÕES
// ==============================
function saudacaoPorHorario() {
    const h = new Date().getHours();
    const periodo = h < 12 ? 'Bom dia' : h < 18 ? 'Boa tarde' : 'Boa noite';
    const emojis  = h < 12 ? '🌅' : h < 18 ? '☀️' : '🌙';
    const msgs = [
        `${emojis} ${periodo}! Aqui é o *Vipi*, do time da Vipe Transportes! Como posso te ajudar? 😊`,
        `${emojis} ${periodo}! Bem-vindo à *Vipe Transportes*! Sou o *Vipi*, pode falar!`,
        `${emojis} ${periodo}! Que bom ter você aqui! Sou o *Vipi* — no que posso ajudar?`,
        `🚛 ${periodo}! Aqui é o *Vipi* da Vipe Transportes. No que posso ajudar?`,
        `👊 ${periodo}! *Vipi* na área! Pode mandar o que precisar.`,
    ];
    return msgs[Math.floor(Math.random() * msgs.length)];
}

const MSGS_CONSULTANDO = [
    '🔍 Deixa eu verificar isso pra você... um segundo! ⏳',
    '⏳ Buscando as informações agora, só um instante!',
    '🔎 Já estou olhando aqui no sistema... aguarda um pouquinho!',
    '📋 Vou checar isso agora mesmo! Um momento...',
    '💻 Consultando o sistema... já já trago o resultado!',
];
function msgConsultandoAleatoria() {
    return MSGS_CONSULTANDO[Math.floor(Math.random() * MSGS_CONSULTANDO.length)];
}

// ==============================
// CLIENT
// ==============================
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox'] }
});

// ==============================
// ESTADO POR CHAT
// ==============================
const userState = {};

function getEstado(id)      { return (userState[id] || {}).estado || null; }
function setEstado(id, est) { _limparTimer(id); userState[id] = { ...(userState[id] || {}), estado: est, timer: null }; if (est !== 'menu') _iniciarTimer(id); }
function resetar(id)        { _limparTimer(id); const prev = userState[id] || {}; userState[id] = { estado: 'menu', timer: null, saudado: prev.saudado, foiTimeout: prev.foiTimeout }; }
function _limparTimer(id)   { if (userState[id]?.timer) { clearTimeout(userState[id].timer); userState[id].timer = null; } }

function _iniciarTimer(id) {
    _limparTimer(id);
    const t = setTimeout(async () => {
        if (!getEstado(id) || getEstado(id) === 'menu') return;
        resetar(id);
        try {
            const msgs = [
                '⏱️ Ei, sumiu! Encerrando por inatividade... Quando precisar, é só chamar o *Vipi*! 👊',
                '😴 Parece que você foi descansar! Encerrando por inatividade. Qualquer coisa, estou aqui! 🚛',
                '⏱️ Sessão encerrada por inatividade. Estamos sempre aqui! *Vipi* 😊',
            ];
            await enviar(id, msgs[Math.floor(Math.random() * msgs.length)]);
            if (!userState[id]) userState[id] = {};
            userState[id].foiTimeout = true;
        } catch (e) { console.error('[TIMEOUT]', e.message); }
    }, TIMEOUT_MS);
    if (userState[id]) userState[id].timer = t;
}

function renovarTimer(id) { const e = getEstado(id); if (e && e !== 'menu') _iniciarTimer(id); }

// ==============================
// FILA POR CHAT
// ==============================
const filaProcessamento = {};
async function processarComFila(chatId, body) {
    if (!filaProcessamento[chatId]) filaProcessamento[chatId] = Promise.resolve();
    filaProcessamento[chatId] = filaProcessamento[chatId].then(() => processar(chatId, body));
    return filaProcessamento[chatId];
}

// ==============================
// ENVIO
// ==============================
async function enviar(chatId, texto) { await client.sendMessage(chatId, texto); }

async function enviarComDigitacao(chatId, texto, ms = 1200) {
    try { const chat = await client.getChatById(chatId); await chat.sendStateTyping(); await sleep(ms); await chat.clearState(); } catch (_) {}
    await client.sendMessage(chatId, texto);
}

async function enviarMenu(chatId) {
    const vip = isVip(chatId);
    let menu =
        '📋 *Menu de Serviços*\n' +
        '━━━━━━━━━━━━━━━━━━━━\n\n' +
        '1️⃣  Consulta Saldo CIOT\n' +
        '2️⃣  Consulta de Multas\n' +
        '3️⃣  Baixa de Manifesto\n' +
        '4️⃣  Encerrar Atendimento\n';
    if (vip) {
        menu += '5️⃣  📄 Relatório de Pendências (PDF)\n';
        menu += '6️⃣  🤖 Perguntar ao Vipi (IA)\n';
    }
    menu += '\n━━━━━━━━━━━━━━━━━━━━\n_Digite o número da opção desejada_ 👆';
    await enviarComDigitacao(chatId, menu, 800);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function validarCPF(t) { return /^\d{11}$/.test(t.replace(/\D/g, '')); }

// ==============================
// CHAMADAS PYTHON
// ==============================
function chamarPython(script, arg) {
    return new Promise((resolve, reject) => {
        execFile(PYTHON, [script, arg],
            { timeout: 30000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } },
            (err, stdout, stderr) => {
                if (err) { reject(stderr || err.message); return; }
                try { resolve(JSON.parse(stdout.trim())); }
                catch (e) { reject(`Erro ao interpretar: ${stdout.slice(0, 200)}`); }
            }
        );
    });
}

function chamarChatbot(pergunta) {
    return new Promise((resolve, reject) => {
        const proc = execFile(
            PYTHON, [SCRIPT_CHAT],
            { timeout: 60000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } },
            (err, stdout, stderr) => {
                if (err) reject(stderr || err.message);
                else resolve(stdout.trim());
            }
        );
        proc.stdin.write(pergunta);
        proc.stdin.end();
    });
}

function chamarPythonRaw(script, arg) {
    return new Promise((resolve, reject) => {
        execFile(PYTHON, [script, arg],
            { timeout: 60000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } },
            (err, stdout, stderr) => { if (err) reject(stderr || err.message); else resolve(stdout.trim()); }
        );
    });
}

// ==============================
// PROCESSAMENTO
// ==============================
async function processar(chatId, body) {
    const estado = getEstado(chatId);
    renovarTimer(chatId);

    if (body === 'menu' || body === '0') { resetar(chatId); return enviarMenu(chatId); }

    // ---- CHATBOT VIP — estado livre ----
    if (estado === 'chatbot_vip') {
        if (body === 'sair' || body === 'voltar') {
            resetar(chatId);
            return enviarMenu(chatId);
        }

        // Detecta pedido de PDF dentro do chatbot
        const pedePDF = /pdf|relat[oó]rio|exportar|gerar.*relat|relat.*gerar/i.test(body);
        if (pedePDF) {
            await enviarComDigitacao(chatId, '📄 Gerando relatório de pendências... aguarda um momento! ⏳', 1000);
            try {
                await chamarPythonRaw(SCRIPT_PDF, CAMINHO_PDF);
                const media = MessageMedia.fromFilePath(CAMINHO_PDF);
                await client.sendMessage(chatId, media, {
                    caption: `📊 *Relatório de Pendências — Vipe Transportes*
🗓️ Gerado em ${new Date().toLocaleString('pt-BR')}`
                });
                await sleep(500);
                await enviarComDigitacao(chatId, '_Pode fazer outra pergunta ou digitar *sair* para voltar ao menu._', 600);
            } catch (err) {
                console.error('[PDF no CHAT]', err);
                await enviarComDigitacao(chatId, '😬 Erro ao gerar o PDF. Tenta novamente ou digita *sair*.', 800);
            }
            return;
        }

        await enviarComDigitacao(chatId, '🤖 Deixa eu pensar... ⏳', 1500);
        try {
            const resultado = await chamarChatbot(body);
            const dados = JSON.parse(resultado);
            if (dados.erro) {
                await enviarComDigitacao(chatId, `😬 ${dados.erro}`, 800);
            } else {
                await enviarComDigitacao(chatId, dados.resposta, 1000);
                await sleep(500);
                await enviarComDigitacao(chatId,
                    '_Pode fazer outra pergunta ou digitar *sair* para voltar ao menu._', 600);
            }
        } catch (err) {
            console.error('[CHATBOT]', err);
            await enviarComDigitacao(chatId, '😬 Erro ao consultar a IA. Tenta novamente ou digita *sair*.', 800);
        }
        return;
    }

    // ---- MENU PRINCIPAL ----
    if (!estado || estado === 'menu') {

        if (body === '1') {
            if (isVip(chatId)) {
                setEstado(chatId, 'aguardando_ciot_tipo');
                return enviarComDigitacao(chatId,
                    '💰 *Consulta Saldo CIOT*\n\nComo prefere buscar?\n\n1️⃣  Por CPF\n2️⃣  Por nome do motorista\n\n_(Digite 0 para voltar ao menu)_', 1000);
            }
            setEstado(chatId, 'aguardando_cpf_ciot');
            return enviarComDigitacao(chatId, '💰 *Consulta Saldo CIOT*\n\nMe passa o *CPF* do motorista ou proprietário! 😊\n\n_(Digite 0 para voltar ao menu)_', 1000);
        }

        if (body === '2') {
            if (isVip(chatId)) {
                setEstado(chatId, 'aguardando_multa_tipo');
                return enviarComDigitacao(chatId,
                    '🚨 *Consulta de Multas*\n\nComo prefere buscar?\n\n1️⃣  Por CPF\n2️⃣  Por nome do motorista\n\n_(Digite 0 para voltar ao menu)_', 1000);
            }
            setEstado(chatId, 'aguardando_cpf_multa');
            return enviarComDigitacao(chatId, '🚨 *Consulta de Multas*\n\nMe passa o *CPF* do motorista! 😊\n\n_(Digite 0 para voltar ao menu)_', 1000);
        }

        if (body === '3') {
            setEstado(chatId, 'aguardando_manifesto');
            return enviarComDigitacao(chatId, '📦 *Baixa de Manifesto*\n\nQual o *número do manifesto* a ser baixado?\n\n_(Digite 0 para voltar ao menu)_', 1000);
        }

        if (body === '4') {
            resetar(chatId);
            const msgs = [
                '👊 Valeu! Qualquer coisa é só chamar o *Vipi*! Até mais! 🚛',
                '😊 Tá bom! Estamos sempre aqui quando precisar. Abraço! 🤜🤛',
                '✅ Ok! Se precisar de algo, pode chamar! Até logo! 👋',
                '🙌 Encerrando por aqui! Boa viagem e bons fretes! Até mais! 🚛',
            ];
            return enviarComDigitacao(chatId, msgs[Math.floor(Math.random() * msgs.length)], 800);
        }

        // Opção 5 — PDF (VIP)
        if (body === '6' && isVip(chatId)) {
            setEstado(chatId, 'chatbot_vip');
            return enviarComDigitacao(chatId,
                '🤖 *Vipi — Assistente de Dados*\n\n' +
                'Pode me perguntar qualquer coisa sobre os dados de *CIOT* e *Multas*!\n\n' +
                'Exemplos:\n' +
                '• _Quais motoristas têm mais de R$ 5.000 pendente?_\n' +
                '• _Qual o total de multas vencidas?_\n' +
                '• _Quem tem mais contratos em aberto?_\n\n' +
                '_(Digite 0 para voltar ao menu)_', 1200
            );
        }

        if (body === '5' && isVip(chatId)) {
            await enviarComDigitacao(chatId, '📄 Gerando relatório de pendências... aguarda um momento! ⏳', 1000);
            try {
                await chamarPythonRaw(SCRIPT_PDF, CAMINHO_PDF);
                const media = MessageMedia.fromFilePath(CAMINHO_PDF);
                await client.sendMessage(chatId, media, {
                    caption: `📊 *Relatório de Pendências — Vipe Transportes*\n🗓️ Gerado em ${new Date().toLocaleString('pt-BR')}\n\n_Conteúdo: CIOTs em aberto + Multas em aberto_`
                });
            } catch (err) {
                console.error('[PDF]', err);
                await enviarComDigitacao(chatId, '😬 Erro ao gerar o relatório. Verifique se as planilhas estão acessíveis e tente novamente.', 800);
            }
            return;
        }

        // Opção 6 — Chatbot IA (VIP)
        if (body === '6' && isVip(chatId)) {
            setEstado(chatId, 'chatbot_vip');
            return enviarComDigitacao(chatId,
                '🤖 *Vipi IA — Assistente de Dados*\n\n' +
                'Pode me perguntar qualquer coisa sobre as bases de *CIOT* e *Multas*!\n\n' +
                'Exemplos:\n' +
                '• _"Quais motoristas têm mais de R$ 5.000 pendente?"_\n' +
                '• _"Quantas multas vencidas temos?"_\n' +
                '• _"Qual o total de saldo em aberto?"_\n' +
                '• _"Liste os 5 maiores devedores"_\n\n' +
                '_Digite *sair* a qualquer momento para voltar ao menu._',
                1200
            );
        }

        // Primeira mensagem / retorno
        resetar(chatId);
        const foiTimeout = (userState[chatId] || {}).foiTimeout;
        if (foiTimeout) {
            userState[chatId].foiTimeout = false;
            const msgs = [
                '👋 Oi, voltou! Que bom! Como posso te ajudar agora? 😊',
                '🙌 Olá de novo! No que posso ajudar?',
                '😄 Ei, tá de volta! *Vipi* aqui, pronto pra ajudar!',
                '👊 Oba, apareceu! Pode falar, estou aqui! 🚛',
            ];
            await enviarComDigitacao(chatId, msgs[Math.floor(Math.random() * msgs.length)], 1000);
            await sleep(400);
        } else if (!userState[chatId] || !userState[chatId].saudado) {
            await enviarComDigitacao(chatId, saudacaoPorHorario(), 1500);
            if (!userState[chatId]) userState[chatId] = {};
            userState[chatId].saudado = true;
            await sleep(600);
        }
        return enviarMenu(chatId);
    }

    // ---- SUBMENU CIOT (VIP) ----
    if (estado === 'aguardando_ciot_tipo') {
        if (body === '1') { setEstado(chatId, 'aguardando_cpf_ciot'); return enviarComDigitacao(chatId, '🪪 Me passa o *CPF* pra eu consultar! 😊\n\n_(Digite 0 para voltar ao menu)_', 800); }
        if (body === '2') { setEstado(chatId, 'aguardando_nome_ciot'); return enviarComDigitacao(chatId, '🔍 Me fala *parte do nome* do motorista! 😊\n\n_(Digite 0 para voltar ao menu)_', 800); }
        return enviarComDigitacao(chatId, '⚠️ Digite *1* para CPF ou *2* para nome.\n\n_(Digite 0 para voltar)_', 600);
    }

    // ---- SUBMENU MULTAS (VIP) ----
    if (estado === 'aguardando_multa_tipo') {
        if (body === '1') { setEstado(chatId, 'aguardando_cpf_multa'); return enviarComDigitacao(chatId, '🪪 Me passa o *CPF* pra eu consultar! 😊\n\n_(Digite 0 para voltar ao menu)_', 800); }
        if (body === '2') { setEstado(chatId, 'aguardando_nome_multa'); return enviarComDigitacao(chatId, '🔍 Me fala *parte do nome* do motorista! 😊\n\n_(Digite 0 para voltar ao menu)_', 800); }
        return enviarComDigitacao(chatId, '⚠️ Digite *1* para CPF ou *2* para nome.\n\n_(Digite 0 para voltar)_', 600);
    }

    // Validação CPF
    const precisaCPF = estado === 'aguardando_cpf_ciot' || estado === 'aguardando_cpf_multa';
    if (precisaCPF && !validarCPF(body)) {
        return enviarComDigitacao(chatId, '⚠️ CPF inválido! Me manda os *11 dígitos* sem pontos ou traço, tá? 😊\n\n_(Digite 0 para voltar ao menu)_', 800);
    }

    // ---- CIOT POR CPF ----
    if (estado === 'aguardando_cpf_ciot') {
        const cpf = body.replace(/\D/g, '');
        await enviarComDigitacao(chatId, msgConsultandoAleatoria(), 1200);
        try {
            const dados = await chamarPython(SCRIPT_CIOT, cpf);
            await enviarComDigitacao(chatId, await ai.gerarRespostaCIOT(dados).catch(() => fallbackCIOT(dados)), 1000);
        } catch (err) { console.error(`[CIOT CPF]`, err); resetar(chatId); await enviarComDigitacao(chatId, '😬 Deu um erro! Tenta de novo ou digita *menu*.', 800); }
        return;
    }

    // ---- CIOT POR NOME ----
    if (estado === 'aguardando_nome_ciot') {
        await enviarComDigitacao(chatId, msgConsultandoAleatoria(), 1200);
        try {
            const dados = await chamarPython(SCRIPT_CIOT, `--nome:${body}`);
            if (!dados.encontrado || !dados.nomes || dados.nomes.length === 0) {
                return enviarComDigitacao(chatId, `😕 Não achei nenhum motorista com *"${body}"* nos últimos 30 dias.\n\nTenta com outra parte do nome! 😊\n\n_(Digite 0 para voltar)_`, 900);
            }
            if (dados.nomes.length === 1) {
                const r = await chamarPython(SCRIPT_CIOT, `--nome-exato:${dados.nomes[0]}`);
                return enviarComDigitacao(chatId, await ai.gerarRespostaCIOT(r).catch(() => fallbackCIOT(r)), 1000);
            }
            userState[chatId].listaNomes = dados.nomes;
            setEstado(chatId, 'aguardando_escolha_nome');
            let msg = `🔍 Achei *${dados.nomes.length}* motoristas com *"${body}"*:\n\n`;
            dados.nomes.forEach((n, i) => { msg += `*${i+1}* — ${n}\n`; });
            msg += `\nQual deles? Digite o *número*! 😊\n_(Digite 0 para voltar)_`;
            return enviarComDigitacao(chatId, msg, 1000);
        } catch (err) { console.error(`[CIOT NOME]`, err); resetar(chatId); return enviarComDigitacao(chatId, '😬 Deu um erro! Tenta de novo ou digita *menu*.', 800); }
    }

    // ---- ESCOLHA NOME CIOT ----
    if (estado === 'aguardando_escolha_nome') {
        const lista = (userState[chatId] || {}).listaNomes || [];
        const idx = parseInt(body) - 1;
        if (isNaN(idx) || idx < 0 || idx >= lista.length) {
            let msg = `⚠️ Inválido! Escolha entre 1 e ${lista.length}:\n\n`;
            lista.forEach((n, i) => { msg += `*${i+1}* — ${n}\n`; });
            return enviarComDigitacao(chatId, msg + '\n_(Digite 0 para voltar)_', 800);
        }
        await enviarComDigitacao(chatId, msgConsultandoAleatoria(), 1200);
        try {
            const r = await chamarPython(SCRIPT_CIOT, `--nome-exato:${lista[idx]}`);
            setEstado(chatId, 'aguardando_nome_ciot');
            return enviarComDigitacao(chatId, await ai.gerarRespostaCIOT(r).catch(() => fallbackCIOT(r)), 1000);
        } catch (err) { console.error(`[CIOT ESCOLHA]`, err); resetar(chatId); return enviarComDigitacao(chatId, '😬 Deu um erro! Tenta de novo ou digita *menu*.', 800); }
    }

    // ---- MULTAS POR CPF ----
    if (estado === 'aguardando_cpf_multa') {
        const cpf = body.replace(/\D/g, '');
        await enviarComDigitacao(chatId, msgConsultandoAleatoria(), 1200);
        try {
            const dados = await chamarPython(SCRIPT_MULTA, cpf);
            await enviarComDigitacao(chatId, await ai.gerarRespostaMultas(dados).catch(() => fallbackMultas(dados)), 1000);
        } catch (err) { console.error(`[MULTAS]`, err); resetar(chatId); await enviarComDigitacao(chatId, '😬 Erro ao consultar! Tenta de novo ou digita *menu*.', 800); }
        return;
    }

    // ---- MULTAS POR NOME ----
    if (estado === 'aguardando_nome_multa') {
        await enviarComDigitacao(chatId, msgConsultandoAleatoria(), 1200);
        try {
            const dados = await chamarPython(SCRIPT_MULTA, `--nome:${body}`);
            if (!dados.encontrado || !dados.nomes || dados.nomes.length === 0) {
                return enviarComDigitacao(chatId, `😕 Nenhum motorista com *"${body}"* nos últimos 30 dias.\n\nTenta com outra parte do nome! 😊\n\n_(Digite 0 para voltar)_`, 900);
            }
            if (dados.nomes.length === 1) {
                const r = await chamarPython(SCRIPT_MULTA, `--nome-exato:${dados.nomes[0]}`);
                return enviarComDigitacao(chatId, await ai.gerarRespostaMultas(r).catch(() => fallbackMultas(r)), 1000);
            }
            userState[chatId].listaNomesMulta = dados.nomes;
            setEstado(chatId, 'aguardando_escolha_nome_multa');
            let msg = `🔍 Achei *${dados.nomes.length}* motoristas com *"${body}"*:\n\n`;
            dados.nomes.forEach((n, i) => { msg += `*${i+1}* — ${n}\n`; });
            msg += `\nQual deles? 😊\n_(Digite 0 para voltar)_`;
            return enviarComDigitacao(chatId, msg, 1000);
        } catch (err) { console.error(`[MULTA NOME]`, err); resetar(chatId); return enviarComDigitacao(chatId, '😬 Deu um erro! Tenta de novo ou digita *menu*.', 800); }
    }

    // ---- ESCOLHA NOME MULTAS ----
    if (estado === 'aguardando_escolha_nome_multa') {
        const lista = (userState[chatId] || {}).listaNomesMulta || [];
        const idx = parseInt(body) - 1;
        if (isNaN(idx) || idx < 0 || idx >= lista.length) {
            let msg = `⚠️ Inválido! Escolha entre 1 e ${lista.length}:\n\n`;
            lista.forEach((n, i) => { msg += `*${i+1}* — ${n}\n`; });
            return enviarComDigitacao(chatId, msg + '\n_(Digite 0 para voltar)_', 800);
        }
        await enviarComDigitacao(chatId, msgConsultandoAleatoria(), 1200);
        try {
            const r = await chamarPython(SCRIPT_MULTA, `--nome-exato:${lista[idx]}`);
            setEstado(chatId, 'aguardando_nome_multa');
            return enviarComDigitacao(chatId, await ai.gerarRespostaMultas(r).catch(() => fallbackMultas(r)), 1000);
        } catch (err) { console.error(`[MULTA ESCOLHA]`, err); resetar(chatId); return enviarComDigitacao(chatId, '😬 Deu um erro! Tenta de novo ou digita *menu*.', 800); }
    }

    // ---- CHATBOT VIP ----
    if (estado === 'chatbot_vip') {
        await enviarComDigitacao(chatId, '🤖 Consultando os dados... aguarda! ⏳', 1000);
        try {
            const openaiKey = process.env.OPENAI_API_KEY || '';
            const resultado = await new Promise((resolve, reject) => {
                execFile(
                    PYTHON, [SCRIPT_CHATBOT, body, openaiKey],
                    { timeout: 60000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } },
                    (err, stdout, stderr) => {
                        if (err) { reject(stderr || err.message); return; }
                        try {
                            const parsed = JSON.parse(stdout.trim());
                            if (parsed.erro) reject(parsed.erro);
                            else resolve(parsed.resposta);
                        } catch (e) { reject(stdout.slice(0, 200)); }
                    }
                );
            });
            await enviarComDigitacao(chatId, resultado, 800);
            await sleep(500);
            await enviarComDigitacao(chatId,
                '💬 Pode fazer outra pergunta ou digitar *0* para voltar ao menu.', 600);
        } catch (err) {
            console.error('[CHATBOT]', err);
            await enviarComDigitacao(chatId, '😬 Não consegui responder agora. Tenta de novo!', 800);
        }
        return;
    }

    // ---- MANIFESTO ----
    if (estado === 'aguardando_manifesto') {
        await enviarComDigitacao(chatId, `📦 Manifesto *${body}* recebido!\n\n⚙️ Funcionalidade em desenvolvimento. Em breve disponível!\n\nDigita *menu* pra voltar. 😊`, 1000);
        resetar(chatId);
        return;
    }

    // Fallback
    resetar(chatId);
    return enviarMenu(chatId);
}

// ==============================
// FALLBACKS
// ==============================
function fallbackCIOT(d) {
    if (!d.encontrado) return `😕 Nenhum contrato encontrado nos últimos 30 dias.\n\nTenta verificar os dados! 😊\n\nDigite *menu* para voltar.`;
    return `📊 *${d.total_contratos}* contrato(s) | Pendente: *R$ ${Number(d.valor_total_pendente||0).toFixed(2)}*\n\nDigite *menu* para voltar.`;
}
function fallbackMultas(d) {
    if (!d.encontrado) return `✅ Nenhuma multa em aberto nos últimos 30 dias! 🎉\n\nDigite *menu* para voltar.`;
    return `🚨 *${d.total_multas}* multa(s) | Total: *R$ ${Number(d.valor_total||0).toFixed(2)}*\n\nDigite *menu* para voltar.`;
}

// ==============================
// EVENTOS
// ==============================
client.on('qr', (qr) => { console.log('\n📱 Escaneie o QR Code:\n'); qrcode.generate(qr, { small: true }); });

client.once('ready', () => {
    console.log('✅ Vipi está pronto!');
    console.log(`🔑 VIPs cadastrados: ${NUMEROS_VIP.size}`);
});

client.on('message', async (msg) => {
    if (msg.isGroupMsg) return;
    const chatId = msg.from;
    const body   = msg.body.trim().toLowerCase();
    console.log(`[MSG] ${chatId} | vip=${isVip(chatId)} | estado=${getEstado(chatId)} | body=${body.slice(0,50)}`);
    try { await processarComFila(chatId, body); }
    catch (err) { console.error(`[BOT ${chatId}]`, err.message); }
});

client.on('message_create', async (msg) => {
    if (!msg.fromMe) return;
    const chatId = msg.to;
    if (msg.body.trim().toLowerCase() === 'encerrar atendimento') {
        resetar(chatId);
        await enviarComDigitacao(chatId, '✅ Atendimento encerrado pelo operador. *Vipi* de volta! 😊', 800);
        await sleep(1500);
        await enviarMenu(chatId);
    }
});

client.initialize();
