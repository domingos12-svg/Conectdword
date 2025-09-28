// chamada.js (corrigido com flush seguro)
let socket = null;
let peerConnection = null;
let localStream = null;
let currentCall = null;
let pendingCandidates = [];
let timerInterval = null;
let tempoSegundos = 0;
// ====== UTILITÁRIOS DE MODAL ======
function abrirModal() {
    document.body.classList.add("modal-ativo");
    document.getElementById('fundo-ofuscado').style.display = 'block';
    document.getElementById('modal-chamada').style.display = 'block';
    document.getElementById('modal-chamada').focus();
}
function fecharModal() {
    document.body.classList.remove("modal-ativo");
    document.getElementById('fundo-ofuscado').style.display = 'none';
    document.getElementById('modal-chamada').style.display = 'none';
}
// ====== TIMER ======
function iniciarTimer() {
    const timerEl = document.getElementById("timer");
    tempoSegundos = 0;
    timerEl.style.display = "block";
    timerEl.textContent = "00:00";
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        tempoSegundos++;
        const min = String(Math.floor(tempoSegundos / 60)).padStart(2, "0");
        const sec = String(tempoSegundos % 60).padStart(2, "0");
        timerEl.textContent = `${min}:${sec}`;
    }, 1000);
}
function pararTimer() {
    clearInterval(timerInterval);
    const timerEl = document.getElementById("timer");
    timerEl.style.display = "none";
    timerEl.textContent = "00:00";
}
// ====== SOCKET ======
function initSocket() {
    socket = io();
    socket.on('connect', () => {
        console.log('Socket conectado:', socket.id);
        if (window.USUARIO_ID) {
            socket.emit('registrar_usuario', window.USUARIO_ID);
        }
    });
    socket.on('chamada_recebida', (data) => {
        showIncomingCall(data.remetente, data.nome_remetente, data.sala);
    });
    socket.on('chamada_aceita', (data) => {
        updateCallStatus(`Em andamento`);
        iniciarTimer();
        startWebRTC(true).catch(e => console.warn('Erro startWebRTC on chamada_aceita:', e));
    });
    socket.on('chamada_recusada', (data) => {
        endCall();
        alert(`${data.nome} recusou a chamada`);
    });
    socket.on('chamada_encerrada', (data) => {
        endCall();
        alert(`${data.nome} encerrou a chamada`);
    });
    socket.on('sinal', async (data) => {
        try {
            if (data.tipo === 'offer') {
                if (!peerConnection) await startWebRTC(true);
                if (data.sala) {
                    currentCall = currentCall || {};
                    currentCall.sala = data.sala;
                }
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
                socket.emit('sinal', {
                    tipo: 'answer',
                    sdp: peerConnection.localDescription,
                    para: data.de,
                    de: window.USUARIO_ID,
                    sala: currentCall ? currentCall.sala : data.sala
                });
                flushPendingCandidates(); // ✅ só depois de setRemoteDescription
            }
            else if (data.tipo === 'answer') {
                if (!peerConnection) await startWebRTC(true);
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
                flushPendingCandidates(); // ✅ idem
            }
            else if (data.tipo === 'candidate') {
                if (peerConnection && peerConnection.remoteDescription) {
                    try {
                        await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidato));
                    } catch (err) {
                        console.warn('Erro ao adicionar candidate:', err);
                    }
                } else {
                    // guarda para aplicar depois
                    pendingCandidates.push(data.candidato);
                }
            }
        } catch (error) {
            console.error('Erro ao processar sinal:', error);
            endCall();
        }
    });
}
function flushPendingCandidates() {
    if (!peerConnection || !peerConnection.remoteDescription) return;
    while (pendingCandidates.length) {
        const cand = pendingCandidates.shift();
        peerConnection.addIceCandidate(new RTCIceCandidate(cand))
            .catch(err => console.warn('Erro ao aplicar candidate pendente:', err));
    }
}
// ====== INICIAR CHAMADA ======
window.iniciarChamadaCom = function (amigoId, amigoNome) {
    currentCall = {
        destinatario: String(amigoId),
        sala: window.USUARIO_ID < amigoId
            ? `sala_${window.USUARIO_ID}_${amigoId}`
            : `sala_${amigoId}_${window.USUARIO_ID}`
    };
    document.getElementById('nome-modal').textContent = amigoNome;
    document.getElementById('status-chamada').textContent = 'Chamando...';
    abrirModal();
    document.getElementById('controles-chamada').style.display = 'flex';
    document.getElementById('controles-resposta').style.display = 'none';
    socket.emit('join', { sala: currentCall.sala });
    socket.emit('iniciar_chamada', {
        destinatario: currentCall.destinatario,
        nome_remetente: window.NOME_AMIGO,
        sala: currentCall.sala
    });
    startWebRTC().catch(e => console.error('Erro startWebRTC (caller):', e));
};
// ====== RECEBER CHAMADA ======
function showIncomingCall(remetenteId, remetenteNome, sala) {
    currentCall = {
        remetente: String(remetenteId),
        sala: sala || (window.USUARIO_ID < remetenteId
            ? `sala_${window.USUARIO_ID}_${remetenteId}`
            : `sala_${remetenteId}_${window.USUARIO_ID}`)
    };
    document.getElementById('nome-modal').textContent = remetenteNome;
    document.getElementById('status-chamada').textContent = 'Está te ligando...';
    abrirModal();
    document.getElementById('controles-chamada').style.display = 'none';
    document.getElementById('controles-resposta').style.display = 'flex';
}
// ====== WEBRTC ======
async function startWebRTC(isAnswer = false) {
    try {
        if (peerConnection) return;
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        peerConnection = new RTCPeerConnection({
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        });
        localStream.getTracks().forEach(track =>
            peerConnection.addTrack(track, localStream)
        );
        peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                socket.emit('sinal', {
                    tipo: 'candidate',
                    candidato: event.candidate,
                    para: currentCall ? (currentCall.destinatario || currentCall.remetente) : undefined,
                    de: window.USUARIO_ID,
                    sala: currentCall ? currentCall.sala : undefined
                });
            }
        };
        peerConnection.ontrack = (event) => {
            const audio = new Audio();
            audio.srcObject = event.streams[0];
            audio.autoplay = true;
            document.body.appendChild(audio);
        };
        if (!isAnswer) {
            const offer = await peerConnection.createOffer();
            await peerConnection.setLocalDescription(offer);
            socket.emit('sinal', {
                tipo: 'offer',
                sdp: peerConnection.localDescription,
                para: currentCall.destinatario,
                de: window.USUARIO_ID,
                sala: currentCall.sala
            });
        }
    } catch (error) {
        console.error('Erro ao iniciar WebRTC:', error);
        endCall();
    }
}
// ====== CONTROLES ======
window.aceitarChamada = function () {
    if (!currentCall || !currentCall.remetente) return;
    socket.emit('aceitar_chamada', {
        remetente: currentCall.remetente,
        nome: window.NOME_AMIGO,
        sala: currentCall.sala
    });
    document.getElementById('controles-resposta').style.display = 'none';
    document.getElementById('controles-chamada').style.display = 'flex';
    updateCallStatus('Em andamento');
    iniciarTimer();
    startWebRTC(true).catch(e => console.warn('Erro aceitarChamada:', e));
};
window.recusarChamada = function () {
    if (!currentCall) return;
    socket.emit('recusar_chamada', {
        remetente: currentCall.remetente,
        nome: window.NOME_AMIGO
    });
    endCall();
};
window.encerrarChamada = function () {
    if (currentCall && (currentCall.destinatario || currentCall.remetente)) {
        socket.emit('encerrar_chamada', {
            destinatario: currentCall.destinatario || currentCall.remetente,
            nome: window.NOME_AMIGO
        });
    }
    endCall();
};
// ====== AUXILIARES ======
function updateCallStatus(status) {
    const el = document.getElementById('status-chamada');
    if (el) el.textContent = status;
}
function endCall() {
    if (peerConnection) {
        peerConnection.close();
        peerConnection = null;
    }
    if (localStream) {
        localStream.getTracks().forEach(t => t.stop());
        localStream = null;
    }
    pendingCandidates = [];
    pararTimer();
    fecharModal();
    currentCall = null;
}
window.toggleMute = function () {
    if (!localStream) return;
    const audioTracks = localStream.getAudioTracks();
    const isMuted = !audioTracks[0].enabled;
    audioTracks.forEach(track => track.enabled = isMuted);
    const btn = document.getElementById('btn-mute');
    if (btn) btn.textContent = isMuted ? '🔊' : '🔇';
};
document.addEventListener('DOMContentLoaded', () => {
    initSocket();
});