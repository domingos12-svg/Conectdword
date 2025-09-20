from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
db = SQLAlchemy()
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    sobre_nome = db.Column(db.String(100), nullable=False)
    data_nado = db.Column(db.Date, nullable=False)
    genero = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    senha = db.Column(db.String(50), nullable=False)
    idioma=db.Column(db.String(10),default='pt-BR')
    traducao=db.Column(db.Boolean,default=True)
class Amizade(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    amigo_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
class Mensagem(db.Model):
    __tablename__ = 'mensagens'
    id = db.Column(db.Integer, primary_key=True)
    remetente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    destinatario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    conteudo = db.Column(db.Text, nullable=False)
    conteudo_traduzido = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    remetente = db.relationship("Usuario", foreign_keys=[remetente_id])
    destinatario = db.relationship("Usuario", foreign_keys=[destinatario_id])
    status=db.Column(db.String(20),nullable=False,default='enviando')
    tipo=db.Column(db.String(20),default='texto')
class Chamada(db.Model):
    __tablename__ = 'chamadas'
    id = db.Column(db.Integer, primary_key=True)
    id_remetente = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    id_destinatario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    inicio = db.Column(db.DateTime, default=datetime.now)
    fim = db.Column(db.DateTime)
    ativa = db.Column(db.Boolean, default=True)
    remetente = db.relationship('Usuario', foreign_keys=[id_remetente])
    destinatario = db.relationship('Usuario', foreign_keys=[id_destinatario])    
