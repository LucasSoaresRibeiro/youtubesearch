const fs = require('fs');

const manifest = JSON.parse(fs.readFileSync('data/manifest.json'));
const busca = JSON.parse(fs.readFileSync('data/busca.json'));
const video = JSON.parse(fs.readFileSync('data/videos/jg2Va2wzs-8.json'));

function cleanText(text) { return text.replace(/ {2,}/g, ' '); }
function normalizarTexto(text) {
    return text.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
}
function maxErrosPermitidos(termo) {
    if (termo.length <= 3) return 0;
    if (termo.length <= 6) return 1;
    return Math.min(3, Math.floor(termo.length / 4));
}
function distanciaLevenshteinLimitada(a, b, limite) {
    if (Math.abs(a.length - b.length) > limite) return limite + 1;
    if (a === b) return 0;
    const prev = new Array(b.length + 1);
    const curr = new Array(b.length + 1);
    for (let j = 0; j <= b.length; j++) prev[j] = j;
    for (let i = 1; i <= a.length; i++) {
        curr[0] = i;
        let minLinha = curr[0];
        for (let j = 1; j <= b.length; j++) {
            const custo = a[i - 1] === b[j - 1] ? 0 : 1;
            curr[j] = Math.min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + custo);
            minLinha = Math.min(minLinha, curr[j]);
        }
        if (minLinha > limite) return limite + 1;
        for (let j = 0; j <= b.length; j++) prev[j] = curr[j];
    }
    return prev[b.length];
}

function tokenizar(texto) {
    const tokens = [];
    let i = 0;
    while (i < texto.length) {
        if (texto.charCodeAt(i) === 32) { i++; continue; }
        const start = i;
        while (i < texto.length && texto.charCodeAt(i) !== 32) i++;
        tokens.push({ w: texto.slice(start, i), start, end: i });
    }
    return tokens;
}

function buscarExato(texto, termo) {
    const ocorrencias = [];
    let pos = 0;
    while ((pos = texto.indexOf(termo, pos)) !== -1) {
        ocorrencias.push({ start: pos, end: pos + termo.length });
        pos += 1;
    }
    return ocorrencias;
}

function buscarPalavraFuzzy(tokens, palavra) {
    const maxErr = maxErrosPermitidos(palavra);
    if (maxErr === 0) return [];
    const ocorrencias = [];
    for (const tok of tokens) {
        if (Math.abs(tok.w.length - palavra.length) > maxErr) continue;
        if (distanciaLevenshteinLimitada(tok.w, palavra, maxErr) <= maxErr) {
            ocorrencias.push({ start: tok.start, end: tok.end });
        }
    }
    return ocorrencias;
}

function buscarOcorrenciasNovo(texto, termo, tokens) {
    const exato = buscarExato(texto, termo);
    if (exato.length) return exato;
    const palavras = termo.split(' ');
    if (palavras.length === 1) return buscarPalavraFuzzy(tokens, palavras[0]);
    return [];
}

function buscarOcorrenciasAntigo(texto, termo) {
    const exato = buscarExato(texto, termo);
    if (exato.length) return exato;
    const maxErros = maxErrosPermitidos(termo);
    if (maxErros === 0) return [];
    const minLen = Math.max(1, termo.length - maxErros);
    const maxLen = Math.min(texto.length, termo.length + maxErros);
    const ocorrencias = [];
    for (let start = 0; start < texto.length; start++) {
        for (let len = minLen; len <= maxLen && start + len <= texto.length; len++) {
            const trecho = texto.substring(start, start + len);
            if (distanciaLevenshteinLimitada(trecho, termo, maxErros) <= maxErros) {
                ocorrencias.push({ start, end: start + len });
                start += len - 1;
                break;
            }
        }
    }
    return ocorrencias;
}

function montarIndiceLegado(transcricao) {
    const partes = [];
    const segmentos = [];
    let pos = 0;
    for (const seg of transcricao) {
        const norm = normalizarTexto(cleanText(seg.text));
        if (!norm) continue;
        if (partes.length > 0) pos += 1;
        segmentos.push([pos, seg.tStartMs]);
        partes.push(norm);
        pos += norm.length;
    }
    return { t: partes.join(' '), s: segmentos };
}

const termos = ['transmisao', 'noite alo boa noite', 'sacha', 'genesis'];

for (const termo of termos) {
    const indice = busca.itens['jg2Va2wzs-8'];
    const legado = montarIndiceLegado(video.transcricao);
    const t0 = Date.now();
    for (let i = 0; i < 100; i++) {
        const tokens = tokenizar(indice.t);
        buscarOcorrenciasNovo(indice.t, termo, tokens);
    }
    const novo = Date.now() - t0;

    const t1 = Date.now();
    for (let i = 0; i < 100; i++) {
        buscarOcorrenciasAntigo(legado.t, termo);
    }
    const antigo = Date.now() - t1;

    console.log(termo, 'novo 100x:', novo + 'ms', 'antigo 100x:', antigo + 'ms');
}

const itens = manifest.itens.filter(i => i.possui_transcricao && busca.itens[i.id]);
const termo = 'transmisao';
const t2 = Date.now();
let count = 0;
for (const item of itens) {
    const indice = busca.itens[item.id];
    const tokens = tokenizar(indice.t);
    count += buscarOcorrenciasNovo(indice.t, termo, tokens).length;
    if (count >= 20) break;
}
console.log('Full catalog search:', Date.now() - t2 + 'ms', 'matches', count, 'videos scanned', itens.length);
