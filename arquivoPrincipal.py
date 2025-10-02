# ====== eventlet monkey patch MUST be done BEFORE other imports ======
import eventlet
eventlet.monkey_patch()
# ====== Imports ======
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from sqlalchemy import or_, and_
from werkzeug.security import generate_password_hash, check_password_hash
from deep_translator import GoogleTranslator
from langdetect import detect
# Importa objetos do teu módulo de conexão e models
# conecao_site deve expor: db, Usuario, Amizade, Mensagem
from conecao_site import db, Usuario, Amizade, Mensagem
# chamada.py deve expor: registrar_rotas_chamada(app) e socketio
from chamada import registrar_rotas_chamada, socketio
# ====== App config ======
app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_segura'
# Use sqlite no /tmp para testes no Render (vai sumir após reinício do container)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/cnw.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Inicializa o banco com o contexto de app (importante)
db.init_app(app)
with app.app_context():
    db.create_all()
    print("[INFO] Banco de dados inicializado com sucesso.")
# Registra rotas / eventos de chamada (se o módulo tiver)
try:
    registrar_rotas_chamada(app)
except Exception:
    # Se o teu módulo chamada.py não estiver presente ou falhar, não trava o startup
    print("[WARN] registrar_rotas_chamada falhou (verifique chamada.py)")
# ====== Filtros Jinja ======
@app.template_filter('formatar_data')
def formatar_data(data):
    if data is None:
        return ""
    try:
        agora = datetime.now().date()
        data_local = data.date()
        if data_local == agora:
            return 'Hoje'
        elif data_local == agora - timedelta(days=1):
            return 'Ontem'
        else:
            return data.strftime('%d de %B de %Y')
    except Exception:
        return str(data)
@app.template_filter('hora_minuto')
def hora_minuto(data):
    try:
        return data.strftime('%H:%M')
    except Exception:
        return ""
# ====== Rotas ======
@app.route('/')
def pagina_principal():
    nome = session.get('usuario_nome')
    # atenção: use o nome exato do template no repo (minúsculas preferidas)
    return render_template('pagina-principal.html', nome=nome)
@app.route('/l')
def ps():
    nome = session.get('usuario_nome')
    return render_template('esqueceu-pass.html', nome=nome)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        if not email or not senha:
            return redirect(url_for('erro'))
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and check_password_hash(usuario.senha, senha):
            session['usuario_id'] = usuario.id
            session['usuario_nome_completo'] = f"{usuario.nome} {usuario.sobre_nome}"
            amigos = db.session.query(Usuario).join(
                Amizade, Usuario.id == Amizade.amigo_id
            ).filter(Amizade.usuario_id == usuario.id).all()
            return render_template('login.html',
                                   nome=session['usuario_nome_completo'],
                                   amigos=amigos,
                                   resultado=[])
        else:
            return redirect(url_for('erro'))
    return render_template('login.html')
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('pagina_principal'))
@app.route('/procurar_amigos', methods=['POST'])
def procurar_amigos():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    termo = request.form.get('termo', '')
    id_usuario = session['usuario_id']
    resultado = Usuario.query.filter(
        ((Usuario.nome.ilike(f"%{termo}%")) | (Usuario.sobre_nome.ilike(f"%{termo}%"))) &
        (Usuario.id != id_usuario)
    ).all()
    amigos = db.session.query(Usuario).join(
        Amizade, Usuario.id == Amizade.amigo_id
    ).filter(Amizade.usuario_id == id_usuario).all()
    sem_resultado = len(resultado) == 0
    amigos_ids = [amigo.id for amigo in amigos]
    return render_template('login.html',
                           nome=session.get('usuario_nome_completo'),
                           resultado=resultado,
                           amigos=amigos,
                           amigos_ids=amigos_ids,
                           sem_resultado=sem_resultado)
@app.route('/adicionar_amigo', methods=['POST'])
def adicionar_amigo():
    meu_id = session.get("usuario_id")
    try:
        amigo_id = int(request.form.get("amigo_id"))
    except (TypeError, ValueError):
        return redirect(url_for('login'))
    termo = request.form.get("termo", "")
    if meu_id and amigo_id and meu_id != amigo_id:
        ja_somos_amigos = Amizade.query.filter_by(usuario_id=meu_id, amigo_id=amigo_id).first()
        if not ja_somos_amigos:
            db.session.add_all([
                Amizade(usuario_id=meu_id, amigo_id=amigo_id),
                Amizade(usuario_id=amigo_id, amigo_id=meu_id)
            ])
            db.session.commit()
    amigos = db.session.query(Usuario).join(
        Amizade, Usuario.id == Amizade.amigo_id
    ).filter(Amizade.usuario_id == meu_id).all()
    resultado = Usuario.query.filter(
        ((Usuario.nome.ilike(f"%{termo}%")) | (Usuario.sobre_nome.ilike(f"%{termo}%"))) &
        (Usuario.id != meu_id)
    ).all()
    amigos_ids = [amigo.id for amigo in amigos]
    sem_resultado = len(resultado) == 0
    return render_template('login.html',
                           nome=session.get('usuario_nome_completo'),
                           amigos=amigos,
                           resultado=resultado,
                           amigos_ids=amigos_ids,
                           sem_resultado=sem_resultado)
@app.route('/chat/<int:amigo_id>')
def chat(amigo_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    amigos = db.session.query(Usuario).join(
        Amizade, Usuario.id == Amizade.amigo_id
    ).filter(Amizade.usuario_id == usuario_id).all()
    mensagens = Mensagem.query.filter(
        or_(
            and_(Mensagem.remetente_id == usuario_id, Mensagem.destinatario_id == amigo_id),
            and_(Mensagem.remetente_id == amigo_id, Mensagem.destinatario_id == usuario_id)
        )
    ).order_by(Mensagem.timestamp.asc()).all()
    amigo_selecionado = Usuario.query.get(amigo_id)
    mensagens_formatadas = []
    for msg in mensagens:
        if msg.remetente_id == amigo_id and getattr(msg, 'conteudo_traduzido', None):
            conteudo_exibido = msg.conteudo_traduzido
        else:
            conteudo_exibido = msg.conteudo
        mensagens_formatadas.append({
            'id': msg.id,
            'conteudo_traduzido': conteudo_exibido,
            'remetente_id': msg.remetente_id,
            'timestamp': msg.timestamp,
            'status': msg.status
        })
    return render_template(
        'login.html',
        nome=session.get('usuario_nome_completo'),
        amigos=amigos,
        mensagens=mensagens_formatadas,
        amigo_selecionado=amigo_selecionado,
        paginaAtiva="sms"
    )
@app.route('/enviar_mensagem', methods=['POST'])
def enviar_mensagem():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    remetente_id = session['usuario_id']
    try:
        destinatario_id = int(request.form.get('destinatario_id'))
    except (TypeError, ValueError):
        return redirect(url_for('login'))
    conteudo = request.form.get('conteudo', '')
    # Detectar idioma
    try:
        idioma_origem = detect(conteudo)
    except Exception:
        idioma_origem = 'auto'
    usuario_destino = Usuario.query.get(destinatario_id)
    idioma_destino = getattr(usuario_destino, 'idioma', None)
    conteudo_traduzido = None
    status_smg = 'enviando'
    try:
        if idioma_destino and idioma_origem != idioma_destino:
            conteudo_traduzido = GoogleTranslator(source=idioma_origem, target=idioma_destino).translate(conteudo)
            status_smg = 'enviado'
        else:
            conteudo_traduzido = None
            status_smg = 'enviando'
    except Exception:
        conteudo_traduzido = None
        status_smg = 'enviando_sem_traducao'
    nova_msg = Mensagem(
        remetente_id=remetente_id,
        destinatario_id=destinatario_id,
        conteudo=conteudo,
        conteudo_traduzido=conteudo_traduzido,
        status=status_smg
    )
    db.session.add(nova_msg)
    db.session.commit()
    return redirect(url_for('chat', amigo_id=destinatario_id))
@app.route('/criar_conta', methods=['GET', 'POST'])
def criar_conta():
    if request.method == 'POST':
        print('DATA RECEBIDA:', request.form)
        nome = request.form.get('nome')
        sobre_nome = request.form.get('sobre_nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        genero = request.form.get('genero')
        data_nado_str = request.form.get('data_nado')
        if not nome or not sobre_nome or not email or not senha or not data_nado_str:
            return "Preencha todos os campos obrigatórios."
        try:
            data_nado = datetime.strptime(data_nado_str, '%Y-%m-%d').date()
        except Exception:
            return "Data inválida."
        senha_hash = generate_password_hash(senha)
        novo_usuario = Usuario(
            nome=nome,
            sobre_nome=sobre_nome,
            email=email,
            senha=senha_hash,
            genero=genero,
            data_nado=data_nado
        )
        db.session.add(novo_usuario)
        db.session.commit()
        # Login automático
        session['usuario_id'] = novo_usuario.id
        session['usuario_nome_completo'] = f"{nome} {sobre_nome}"
        # Buscar amigos (deve estar vazio inicialmente)
        amigos = db.session.query(Usuario).join(
            Amizade, Usuario.id == Amizade.amigo_id
        ).filter(Amizade.usuario_id == novo_usuario.id).all()
        return render_template(
            'login.html',
            nome=session['usuario_nome_completo'],
            amigos=amigos
        )
    return render_template("criar_conta_novo.html")
@app.route('/amigo')
def amigos():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    id_usuario = session['usuario_id']
    amigos = db.session.query(Usuario).join(
        Amizade, Usuario.id == Amizade.amigo_id
    ).filter(Amizade.usuario_id == id_usuario).all()
    return render_template(
        'login.html',
        nome=session.get('usuario_nome_completo'),
        amigos=amigos,
        resultado=[],
        amigos_ids=[a.id for a in amigos],
        sem_resultado=False
    )
@app.route('/erro', methods=['GET', 'POST'])
def erro():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        if not email or not senha:
            return redirect(url_for('erro'))
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and check_password_hash(usuario.senha, senha):
            session['usuario_id'] = usuario.id
            session['usuario_nome_completo'] = f"{usuario.nome} {usuario.sobre_nome}"
            amigos = db.session.query(Usuario).join(
                Amizade, Usuario.id == Amizade.amigo_id
            ).filter(Amizade.usuario_id == usuario.id).all()
            return render_template('login.html',
                                   nome=session['usuario_nome_completo'],
                                   amigos=amigos,
                                   resultado=[])
        else:
            return redirect(url_for('erro'))
    return render_template('erro.html')
@app.route('/fechar_chat')
def fechar_chat():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    amigos = db.session.query(Usuario).join(
        Amizade, Usuario.id == Amizade.amigo_id
    ).filter(Amizade.usuario_id == usuario_id).all()
    return render_template(
        'login.html',
        nome=session.get('usuario_nome_completo'),
        amigos=amigos,
        amigo_selecionado=None,
        mensagens=[],
        paginaAtiva="sms"
    )
@app.route('/definir_idioma', methods=['POST'])
def definir_idioma():
    data = request.get_json()
    idioma = data.get('idioma', '').lower().split('-')[0]
    if 'usuario_id' in session:
        usuario = Usuario.query.get(session['usuario_id'])
        if usuario:
            usuario.idioma = idioma
            db.session.commit()
    return jsonify({'status': 'ok'})
@app.route('/meu_idioma')
def meu_idioma():
    if 'usuario_id' in session:
        usuario = Usuario.query.get(session['usuario_id'])
        return f' idioma salvo: {usuario.idioma}'
    return "usuario nao identificado"
def traduzir(texto, idioma_origen, idioma_destino):
    try:
        traduzido = GoogleTranslator(source=idioma_origen, target=idioma_destino).translate(texto)
        return traduzido
    except Exception:
        return texto
# ====== Rodar localmente (não usado quando executar com gunicorn no Render) ======
if __name__ == '__main__':
    # Inicializa o socketio localmente para testes
    socketio.init_app(app, cors_allowed_origins="*")
    port = int(os.environ.get("PORT", 5000))
    # Usa socketio.run localmente (para desenvolvimento). Em produção o gunicorn é o entrypoint.
    socketio.run(app, host="0.0.0.0", port=port, debug=True)