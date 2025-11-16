import os
import pandas as pd
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta
from sqlalchemy import func, cast, Date

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__, static_folder='templates/static')
CORS(app) # Permite requisições de origens diferentes (para o nosso frontend)

# Configuração do caminho do banco de dados e SQLAlchemy
# Formato da URI: mysql+pymysql://usuario:senha@host/database
# Substitua com suas credenciais do MySQL
DB_USER = "root"
DB_PASSWORD = "admin2025" # <-- ATENÇÃO: Troque sua senha aqui
DB_HOST = "localhost"
DB_NAME = "historico_vendas_db"
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELO DO BANCO DE DADOS (TABELA) ---
class ItemVendidos(db.Model):
    __tablename__ = 'item_vendido' # Nome explícito da tabela
    id = db.Column(db.Integer, primary_key=True)
    id_produto = db.Column(db.String(100))
    nome_produto = db.Column(db.String(255), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    data_venda = db.Column(db.Date)

    def to_dict(self):
        """Converte o objeto para um dicionário, útil para serialização JSON."""
        return {
            'id': self.id,
            'id_produto': self.id_produto,
            'nome_produto': self.nome_produto,
            'quantidade': self.quantidade,
            'valor_unitario': str(self.valor_unitario), # Converte Decimal para string
            'data_venda': self.data_venda.strftime('%Y-%m-%d') if self.data_venda else None
        }

class VendaDetalhe(db.Model):
    __tablename__ = 'vendas_detalhe'
    # Colunas de Identificação e Tempo
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data_hora_item = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_abertura_pedido = db.Column("data_abertura_ped", db.Date, default=datetime.utcnow)
    data_fechamento_pedido = db.Column("data_fechamento_ped", db.DateTime, default=datetime.utcnow)

    # Colunas de Quantidade e Valor
    quantidade_item = db.Column(db.Integer, nullable=False, default=1)
    # DECIMAL(10, 2) mapeia para DECIMAL no Python
    valor_unitario = db.Column("valor_unitario_item", db.DECIMAL(10, 2), nullable=False, default=0.0)
    valor_total = db.Column("valor_total_item", db.DECIMAL(10, 2), nullable=False, default=0.0)
    valor_produto = db.Column(db.DECIMAL(10, 2), default=0.0)
    
    # Colunas de Produto (VARCHAR mapeia para String no Python)
    nome_produto = db.Column(db.String(255), nullable=False, default='')
    tipo_item = db.Column(db.String(50))
    tipo_produto = db.Column(db.String(50))
    categoria_produto = db.Column(db.String(100))
    
    # Colunas do Pedido/Transação
    codigo_pedido = db.Column(db.Integer)
    numero_mesa_comanda = db.Column(db.String(50))
    tipo_pedido = db.Column(db.String(50))
    status_pedido = db.Column(db.String(50))

    def __repr__(self):
        return f"<VendaDetalhe(id={self.id}, produto='{self.nome_produto}', qtd={self.quantidade_item})>"

# --- ROTAS DA API ---

@app.route("/")
def home():
    """Renderiza a página inicial com links."""
    # Esta é uma página simples para navegar para o upload ou para o dashboard
    return """
    <h1>Bem-vindo à Cervejaria Alquimia</h1>
    <a href="/dashboard">Ver Dashboard</a><br>
    <a href="/upload_page">Gerenciar Vendas</a><br>
    <a href="/relatorios">Ver Relatórios Gerais</a>
    """

@app.route('/upload', methods=['POST'])
def upload_file():
    """Recebe a planilha, processa e salva no banco de dados."""
    if 'planilha' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['planilha']
    if file.filename == '':
        return jsonify({'error': 'Nome de arquivo vazio'}), 400

    try:
        # Usando pandas para ler o arquivo excel diretamente da memória
        df = pd.read_excel(file)

        # Renomear colunas para corresponder ao modelo do banco de dados (se necessário)
        # Ex: df.rename(columns={'Nome do Produto': 'nome_produto'}, inplace=True)
        
        # Normaliza os nomes das colunas (remove espaços, acentos, etc.)
        df.columns = [col.strip().lower().replace(' ', '_').replace('ç', 'c').replace('ã', 'a') for col in df.columns]

        # Itera sobre o DataFrame e cria objetos do modelo
        for _, row in df.iterrows():
            if str(row['núm._mesa/com.']).lower() == 'nan':
                row['núm._mesa/com.'] = None
            novo_item = VendaDetalhe(
                data_hora_item=pd.to_datetime(row.get('data/hora_item')),
                data_abertura_pedido=pd.to_datetime(row.get('data_ab._ped.')),
                data_fechamento_pedido=pd.to_datetime(row.get('data_fec._ped.')),
                quantidade_item=row.get('qtd.'),
                valor_unitario=row.get('valor_un._item'),
                valor_total=row.get('valor._tot._item'),
                valor_produto=row.get('valor_prod'),
                nome_produto=row.get('nome_prod'),
                tipo_item=row.get('tipo_de_item'),
                tipo_produto=row.get('tipo_prod'),
                categoria_produto=row.get('cat._prod.'),
                codigo_pedido=row.get('cod._ped.'),
                numero_mesa_comanda=row.get('núm._mesa/com.'),
                tipo_pedido=row.get('tipo_ped.'),
                status_pedido=row.get('stat._ped.')
            )
            db.session.add(novo_item)
        
        db.session.commit() # Salva todas as novas entradas no banco
        
        return jsonify({'message': f'{len(df)} itens importados com sucesso!'}), 201

    except Exception as e:
        db.session.rollback() # Desfaz as alterações em caso de erro
        return jsonify({'error': f'Ocorreu um erro ao processar o arquivo: {str(e)}'}), 500

@app.route('/upload_page')
def upload_page():
    """Renderiza a página de upload de arquivo (se você tiver uma)."""
    return render_template('index.html') # Supondo que index.html é sua página de upload

# --- ROTAS CRUD PARA VENDADETALHE ---

@app.route('/api/vendas', methods=['GET'])
def get_vendas():
    """Retorna uma lista paginada e filtrada de vendas."""
    try:
        # Parâmetros de paginação
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)

        # Parâmetros de filtro
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        search_term = request.args.get('search')

        query = VendaDetalhe.query

        # Aplicar filtro de data
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(VendaDetalhe.data_hora_item >= start_date)
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(VendaDetalhe.data_hora_item < end_date)

        # Aplicar filtro de busca
        if search_term:
            search_filter = f"%{search_term}%"
            query = query.filter(VendaDetalhe.nome_produto.like(search_filter))

        # Ordenar e paginar
        pagination = query.order_by(VendaDetalhe.data_hora_item.desc()).paginate(page=page, per_page=per_page, error_out=False)
        
        vendas = [{
            'id': venda.id,
            'data_hora_item': venda.data_hora_item.strftime('%d/%m/%Y %H:%M'),
            'nome_produto': venda.nome_produto,
            'quantidade_item': venda.quantidade_item,
            'valor_unitario': float(venda.valor_unitario),
            'valor_total': float(venda.valor_total),
            'tipo_pedido': venda.tipo_pedido,
            'status_pedido': venda.status_pedido
        } for venda in pagination.items]

        return jsonify({
            'vendas': vendas,
            'total_pages': pagination.pages,
            'current_page': pagination.page,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vendas/<int:venda_id>', methods=['DELETE'])
def delete_venda(venda_id):
    """Exclui um registro de venda pelo ID."""
    item = VendaDetalhe.query.get_or_404(venda_id)
    try:
        db.session.delete(item)
        db.session.commit()
        return jsonify({'message': 'Item excluído com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# --- ROTAS DO DASHBOARD ---

@app.route('/dashboard')
def dashboard():
    """Renderiza o template do dashboard."""
    return render_template('dashboard.html')

@app.route('/api/dashboard/cervejas')
def get_cervejas_data():
    """Fornece dados agregados por cerveja."""
    try:
        # Pega os parâmetros de data da requisição
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        # Converte as strings de data para objetos datetime
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1) # Inclui o dia todo
        else:
            # Se não houver data, usa o último mês como padrão
            today = datetime.utcnow().date()
            end_date = today + timedelta(days=1)
            start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

        # Filtra apenas por produtos da categoria 'Cervejas'
        base_query = db.session.query(
            VendaDetalhe.nome_produto,
            func.sum(VendaDetalhe.quantidade_item).label('volume_produzido'),
            func.sum(VendaDetalhe.valor_total).label('receita_total_potencial')
        ).filter(VendaDetalhe.categoria_produto == 'Cervejas', VendaDetalhe.data_hora_item.between(start_date, end_date))
        
        query = base_query.group_by(VendaDetalhe.nome_produto).all()

        cervejas = []
        CUSTO_POR_LITRO = 3.50  # Custo de produção simulado por litro

        for row in query:
            volume = float(row.volume_produzido)
            receita = float(row.receita_total_potencial)
            
            custo_total = volume * CUSTO_POR_LITRO
            lucro = receita - custo_total
            margem = (lucro / receita * 100) if receita > 0 else 0

            cervejas.append({
                "nome": row.nome_produto,
                "volume_produzido": volume,
                "volume_real_produzido": volume * 0.95, # Simulação de perda de 5%
                "receita_total_potencial": receita,
                "custo_total_producao": custo_total,
                "lucro_potencial": lucro,
                "margem_lucro": margem
            })

        return jsonify(cervejas)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/dados-gerais')
def get_dados_gerais():
    """Fornece dados gerais para os cartões do dashboard."""
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
        else:
            today = datetime.utcnow().date()
            end_date = today + timedelta(days=1)
            start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

        CAPACIDADE_TOTAL_LITROS = 20000  # Capacidade de produção mensal
        CUSTO_POR_LITRO = 3.50 # Deve ser o mesmo usado na rota de cervejas
        
        # Cria uma subquery base para reutilização
        base_query = db.session.query(VendaDetalhe).filter(
            VendaDetalhe.categoria_produto == 'Cervejas',
            VendaDetalhe.data_hora_item.between(start_date, end_date)
        )

        total_revenue = db.session.query(func.sum(VendaDetalhe.valor_total)).filter(
            VendaDetalhe.categoria_produto == 'Cervejas', VendaDetalhe.data_hora_item.between(start_date, end_date)
        ).scalar() or 0

        total_volume = db.session.query(func.sum(VendaDetalhe.quantidade_item)).filter(
            VendaDetalhe.categoria_produto == 'Cervejas', VendaDetalhe.data_hora_item.between(start_date, end_date)
        ).scalar() or 0

        custo_total_mensal = float(total_volume) * CUSTO_POR_LITRO
        lucratividade_mensal = float(total_revenue) - custo_total_mensal

        dados = {
            "capacidade_total": CAPACIDADE_TOTAL_LITROS,
            "receita_potencial_mes": float(total_revenue),
            "lucratividade_potencial_mes": lucratividade_mensal
        }
        return jsonify(dados)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/metricas')
def get_metricas():
    """Fornece métricas como a utilização da capacidade."""
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
        else:
            today = datetime.utcnow().date()
            end_date = today + timedelta(days=1)
            start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

        CAPACIDADE_TOTAL_LITROS = 20000 # Capacidade de produção mensal

        volume_mensal = db.session.query(func.sum(VendaDetalhe.quantidade_item)).filter(
            VendaDetalhe.categoria_produto == 'Cervejas',
            VendaDetalhe.data_hora_item.between(start_date, end_date)
        ).scalar() or 0

        utilizacao = (float(volume_mensal) / CAPACIDADE_TOTAL_LITROS * 100) if CAPACIDADE_TOTAL_LITROS > 0 else 0

        metricas = {
            "utilizacao_capacidade_percent": utilizacao
        }
        return jsonify(metricas)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/despesas')
def get_despesas():
    """Fornece dados simulados de despesas."""
    # NOTA: Estes dados são simulados. O ideal seria tê-los em outra tabela
    # ou sistema e consultá-los aqui.
    despesas = {
        "principais_despesas_predio_mes": {
            "aluguel": 2500.00,
            "energia": 1200.50,
            "agua": 850.75,
            "marketing": 1500.00,
            "outros": 950.25
        }
    }
    return jsonify(despesas)

# --- ROTAS DE RELATÓRIOS GERAIS ---

@app.route('/relatorios')
def relatorios():
    """Renderiza a página de relatórios gerais."""
    return render_template('relatorio_geral.html')

@app.route('/api/relatorios/top-10-produtos')
def get_top_10_produtos():
    """Retorna os 10 produtos mais vendidos por quantidade."""
    try:
        top_produtos = db.session.query(
            VendaDetalhe.nome_produto,
            func.sum(VendaDetalhe.quantidade_item).label('total_quantidade')
        ).group_by(VendaDetalhe.nome_produto).order_by(func.sum(VendaDetalhe.quantidade_item).desc()).limit(10).all()

        resultado = [{'produto': p.nome_produto, 'quantidade': int(p.total_quantidade)} for p in top_produtos]
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/relatorios/faturamento-mensal')
def get_faturamento_mensal():
    """Retorna o faturamento agregado por mês nos últimos 12 meses."""
    try:
        # Define o período dos últimos 12 meses
        hoje = datetime.utcnow().date()
        inicio_periodo = hoje.replace(year=hoje.year - 1, day=1)

        faturamento = db.session.query(
            func.DATE_FORMAT(VendaDetalhe.data_hora_item, '%Y-%m').label("mes"),
            func.sum(VendaDetalhe.valor_total).label('total_faturamento')
        ).filter(
            VendaDetalhe.data_hora_item >= inicio_periodo
        ).group_by('mes').order_by('mes').all()

        resultado = [{'mes': f.mes, 'faturamento': float(f.total_faturamento)} for f in faturamento]
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- INICIALIZAÇÃO DO SERVIDOR ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Cria as tabelas no banco de dados se elas não existirem
    app.run(debug=True, port=5000) # debug=True reinicia o servidor a cada alteração
