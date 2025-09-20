from flask import request, session, jsonify
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
from conecao_site import db, Mensagem, Usuario
import logging
socketio = SocketIO(cors_allowed_origins="*")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Controle de chamadas atendidas: guarda pares de usuários que entraram
chamadas_aceitas = set()
def registrar_rotas_chamada(app):
    @app.route('/registrar_chamada', methods=['POST'])
    def registrar_chamada():
        try:
            if 'usuario_id' not in session:
                return jsonify({'erro': 'Não autenticado'}), 401
            data = request.get_json()
            destinatario_id = data.get('destinatario_id')
            conteudo = data.get('conteudo')
            if not destinatario_id or not conteudo:
                return jsonify({'erro': 'Dados incompletos'}), 400
    
            nova_msg = Mensagem(
                remetente_id=session['usuario_id'],
                destinatario_id=destinatario_id,
                conteudo=conteudo,
                tipo='sistema',
                status='enviado'
            )
            db.session.add(nova_msg)
            db.session.commit()
            socketio.emit('nova_mensagem', {
                'remetente_id': session['usuario_id'],
                'destinatario_id': destinatario_id,
                'conteudo': conteudo,
                'tipo': 'sistema'
            }, room=str(destinatario_id))
            return jsonify({'sucesso': True}), 200
        except Exception as e:
            logger.error(f"Erro: {str(e)}")
            return jsonify({'erro': str(e)}), 500
    # 🔹 Registrar usuário na sala própria
    @socketio.on('registrar_usuario')
    def registrar_usuario(user_id):
        try:
            join_room(str(user_id))
            logger.info(f"Usuário {user_id} registrado e entrou na sala {user_id}")
        except Exception as e:
            logger.error(f"Erro ao registrar usuário: {str(e)}")
    @socketio.on('join')
    def on_join(data):
        try:
            sala = data.get('sala')
            usuario_id = session.get('usuario_id')
            if sala and usuario_id:
                join_room(sala)
                logger.info(f"Usuário {usuario_id} entrou na sala {sala}")
        except Exception as e:
            logger.error(f"Erro no join: {str(e)}")
    @socketio.on('iniciar_chamada')
    def on_iniciar_chamada(data):
        try:
            destinatario = data.get('destinatario')
            nome_remetente = data.get('nome_remetente')
            sala = data.get('sala')
            if not all([destinatario, nome_remetente, sala]):
                return
            join_room(sala)
            emit('chamada_recebida', {
                'remetente': session.get('usuario_id'),
                'nome_remetente': nome_remetente,
                'sala': sala
            }, room=str(destinatario))
        except Exception as e:
            logger.error(f"Erro ao iniciar chamada: {str(e)}")
    @socketio.on('aceitar_chamada')
    def on_aceitar_chamada(data):
        try:
            remetente = str(data.get('remetente'))
            
            nome = session.get('usuario_nome')
            sala = data.get('sala')
            usuario_atual = str(session.get('usuario_id'))
            if not remetente:
                return
            if sala:
                join_room(sala)
            # Marca que esta chamada foi aceita
            chamadas_aceitas.add(tuple(sorted([remetente, usuario_atual])))
            emit('chamada_aceita', {
                'destinatario': usuario_atual,
                'nome': nome,
                'sala': sala
            }, room=str(remetente))
        except Exception as e:
            logger.error(f"Erro ao aceitar chamada: {str(e)}")
    @socketio.on('recusar_chamada')
    def on_recusar_chamada(data):
        try:
            remetente = data.get('remetente')
            nome = data.get('nome')
            if remetente:
                emit('chamada_recusada', {
                    'destinatario': session.get('usuario_id'),
                    'nome': nome
                }, room=str(remetente))
        except Exception as e:
            logger.error(f"Erro ao recusar chamada: {str(e)}")
    @socketio.on('encerrar_chamada')
    def on_encerrar_chamada(data):
        try:
            destinatario = str(data.get('destinatario'))
            nome = data.get('nome')
            usuario_atual = str(session.get('usuario_id'))
            if destinatario:
                emit('chamada_encerrada', {
                    'remetente': usuario_atual,
                    'nome': nome
                }, room=str(destinatario))
                # Verifica se houve aceite
                chamada_id = tuple(sorted([destinatario, usuario_atual]))
                if chamada_id in chamadas_aceitas:
                    conteudo = f"✅ Esteve em chamada com {nome}"
                    chamadas_aceitas.discard(chamada_id)
                else:
                    conteudo = f"📵 Chamada não atendida por {nome}"
                # Registra a SMS final no banco
                nova_msg = Mensagem(
                    remetente_id=usuario_atual,
                    destinatario_id=destinatario,
                    conteudo=conteudo,
                    tipo='sistema',
                    status='enviado'
                )
                db.session.add(nova_msg)
                db.session.commit()
                socketio.emit('nova_mensagem', {
                    'remetente_id': usuario_atual,
                    'destinatario_id': destinatario,
                    'conteudo': conteudo,
                    'tipo': 'sistema'
                }, room=str(destinatario))
        except Exception as e:
            logger.error(f"Erro ao encerrar chamada: {str(e)}")
@socketio.on('sinal')
def on_sinal(data):
    try:
        para = data.get('para')  # ID do destino
        sala = data.get('sala')
        if para:
            # Envia o sinal diretamente para o usuário de destino
            emit('sinal', data, room=str(para))
            logger.info(f"Sinal '{data.get('tipo')}' enviado para usuário {para}")
        elif sala:
            # Envia para todos da sala, exceto quem enviou
            emit('sinal', data, room=sala, include_self=False)
            logger.info(f"Sinal '{data.get('tipo')}' enviado para sala {sala}")
        else:
            logger.warning("Sinal recebido sem 'para' ou 'sala' definidos.")
    except Exception as e:
        logger.error(f"Erro no sinal: {str(e)}")