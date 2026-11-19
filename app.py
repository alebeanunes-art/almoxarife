from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_cors import CORS
import mysql.connector
import bcrypt

# Inicialização da aplicação Flask e configurações de segurança/CORS
app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = 'senai_almoxarifado_chave'

# Função responsável por estabelecer e retornar a conexão com a base de dados MySQL
def banco_conexao():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='almoxarife'
    )

# ==========================================
# FUNÇÕES AUXILIARES DE SEGURANÇA (BCRYPT)
# ==========================================

# Gera um hash seguro (criptografado) a partir de uma senha em texto plano
def gerar_hash(senha):
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Compara uma senha fornecida com o hash guardado na base de dados para validação
def verificar_senha(senha, senha_hash):
    return bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8'))


# ==========================================
# ROTAS DE PÁGINAS (RENDERIZAÇÃO HTML)
# ==========================================

# Rota principal e de login: gere a autenticação via formulário web
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = banco_conexao()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        usuario = cursor.fetchone()
        cursor.close()
        conn.close()

        # Valida as credenciais utilizando o bcrypt
        if usuario and verificar_senha(password, usuario['password_hash']):
            session['usuario_id'] = usuario['id']
            session['username'] = usuario['username']
            session['role'] = usuario['role']
            return redirect(url_for('home_page'))
        
        return render_template('login.html', erro="Usuário ou senha incorretos.")

    return render_template('login.html')

# Encerra a sessão atual do utilizador e redireciona para o login
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# Página inicial do sistema (Home): lista todos os produtos cadastrados
@app.route('/home')
def home_page():
    if 'usuario_id' not in session:
        return redirect(url_for('login_page'))

    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produtos ORDER BY id DESC")
    produtos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('home.html', produtos=produtos)

# Página de movimentações: lista o histórico e permite registrar entradas/saídas via formulário HTML
@app.route('/movimentacoes', methods=['GET', 'POST'])
def movimentacoes_page():
    if 'usuario_id' not in session:
        return redirect(url_for('login_page'))

    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        produto_id = request.form.get('produto_id')
        tipo = request.form.get('tipo')
        quantidade = int(request.form.get('quantidade', 0))
        usuario_id = session.get('usuario_id', 1)

        try:
            # Insere o registo da movimentação e atualiza o stock do produto correspondente
            cursor.execute(
                "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, %s, %s)",
                (produto_id, usuario_id, tipo, quantidade)
            )
            if tipo == 'entrada':
                cursor.execute("UPDATE produtos SET quantidade = quantidade + %s WHERE id = %s", (quantidade, produto_id))
            elif tipo == 'saida':
                cursor.execute("UPDATE produtos SET quantidade = quantidade - %s WHERE id = %s", (quantidade, produto_id))
            conn.commit()
        except mysql.connector.Error as err:
            conn.rollback()
            print(f"Erro na movimentação: {err}")

        cursor.close()
        conn.close()
        return redirect(url_for('movimentacoes_page'))

    cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()

    # Consulta com JOIN para trazer os nomes dos produtos e utilizadores associados às movimentações
    cursor.execute("""
        SELECT 
            m.id, m.tipo, m.quantidade, m.data_movimentacao,
            COALESCE(p.nome, 'Produto Removido') AS produto_nome, 
            COALESCE(p.foto, '') AS produto_foto,
            COALESCE(u.username, 'Sistema/Removido') AS username
        FROM movimentacoes m
        LEFT JOIN produtos p ON m.produto_id = p.id
        LEFT JOIN usuarios u ON m.usuario_id = u.id
        ORDER BY m.id DESC
    """)
    movimentacoes = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('movimentacoes.html', produtos=produtos, movimentacoes=movimentacoes)

# Página restrita a administradores para o cadastro de novos utilizadores via painel web
@app.route('/add-usuario', methods=['GET', 'POST'])
def add_usuario_page():
    if session.get('role') != 'admin':
        return redirect(url_for('home_page'))
    
    mensagem = None
    erro = None

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'usuario')

        try:
            hashed_password = gerar_hash(password)
            conn = banco_conexao()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, role) VALUES (%s, %s, %s)",
                (username, hashed_password, role)
            )
            conn.commit()
            cursor.close()
            conn.close()
            mensagem = "Usuário cadastrado com sucesso!"
        except mysql.connector.Error:
            erro = "Nome de usuário já existe ou erro na base de dados."

    return render_template('add-usuario.html', mensagem=mensagem, erro=erro)


# ==========================================
# ROTAS DE API (COMUNICAÇÃO EM JSON)
# ==========================================

# API de login: valida credenciais e retorna resposta JSON para requisições assíncronas (AJAX/Fetch)
@app.route('/api/login', methods=['POST'])
def api_login():
    dados = request.get_json() or request.form
    username = dados.get('username')
    password = dados.get('password')

    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()

    if usuario and verificar_senha(password, usuario['password_hash']):
        session['usuario_id'] = usuario['id']
        session['username'] = usuario['username']
        session['role'] = usuario['role']
        return jsonify({
            "sucesso": True,
            "mensagem": "Login efetuado com sucesso!",
            "usuario": {"id": usuario['id'], "username": usuario['username'], "role": usuario['role']}
        }), 200

    return jsonify({"sucesso": False, "erro": "Usuário ou senha incorretos."}), 401

# API de logout: limpa a sessão atual via pedido JSON
@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({"sucesso": True, "mensagem": "Logout efetuado com sucesso!"}), 200

# API para listar todos os produtos em formato JSON
@app.route('/api/produtos', methods=['GET'])
def api_listar_produtos():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produtos ORDER BY id DESC")
    produtos = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(produtos), 200

# API para cadastrar um novo produto (aceita tanto JSON quanto formulário tradicional)
@app.route('/api/produtos', methods=['POST'])
def api_cadastrar_produto():
    if request.is_json:
        dados = request.get_json()
    else:
        dados = request.form

    nome = dados.get('nome')
    categoria = dados.get('categoria')
    quantidade = int(dados.get('quantidade', 0))
    foto = dados.get('foto', '')
    usuario_id = session.get('usuario_id', 1)

    conn = banco_conexao()
    cursor = conn.cursor()
    try:
        # Insere o produto com código temporário e depois atualiza formatado com base no ID gerado
        cursor.execute(
            "INSERT INTO produtos (codigo, nome, categoria, quantidade, foto) VALUES (%s, %s, %s, %s, %s)",
            ('TEMP', nome, categoria, quantidade, foto)
        )
        produto_id = cursor.lastrowid
        cursor.execute("UPDATE produtos SET codigo = %s WHERE id = %s", (f"{produto_id:03d}", produto_id))

        if quantidade > 0:
            cursor.execute(
                "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, %s, %s)",
                (produto_id, usuario_id, 'entrada', quantidade)
            )

        conn.commit()
        
        if not request.is_json:
            return redirect(url_for('home_page'))
            
        return jsonify({"sucesso": True, "mensagem": "Produto cadastrado com sucesso!", "id": produto_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"sucesso": False, "erro": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# API para editar um produto existente e registrar automaticamente a movimentação de diferença no stock
@app.route('/api/produtosEditar', methods=['POST'])
def api_editar_produto():
    if request.is_json:
        dados = request.get_json()
    else:
        dados = request.form

    produto_id = dados.get('id')
    codigo = dados.get('codigo')
    nome = dados.get('nome')
    categoria = dados.get('categoria')
    nova_quantidade = int(dados.get('quantidade', 0))
    foto = dados.get('foto', '')
    usuario_id = session.get('usuario_id', 1)

    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT quantidade FROM produtos WHERE id = %s", (produto_id,))
        prod_atual = cursor.fetchone()
        qtd_antiga = prod_atual['quantidade'] if prod_atual else 0

        cursor.execute("""
            UPDATE produtos 
            SET codigo = %s, nome = %s, categoria = %s, quantidade = %s, foto = %s 
            WHERE id = %s
        """, (codigo, nome, categoria, nova_quantidade, foto, produto_id))

        # Calcula a diferença de quantidade para atualizar o histórico de movimentações
        diferenca = nova_quantidade - qtd_antiga
        if diferenca != 0:
            tipo = 'entrada' if diferenca > 0 else 'saida'
            cursor.execute(
                "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, %s, %s)",
                (produto_id, usuario_id, tipo, abs(diferenca))
            )

        conn.commit()

        if not request.is_json:
            return redirect(url_for('home_page'))

        return jsonify({"sucesso": True, "mensagem": "Produto atualizado com sucesso!"}), 200
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"sucesso": False, "erro": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# API para listar todas as movimentações do sistema em formato JSON
@app.route('/api/movimentacoes', methods=['GET'])
def api_listar_movimentacoes():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            m.id, m.tipo, m.quantidade, m.data_movimentacao,
            COALESCE(p.nome, 'Produto Removido') AS produto_nome, 
            COALESCE(p.foto, '') AS produto_foto,
            COALESCE(u.username, 'Sistema/Removido') AS username
        FROM movimentacoes m
        LEFT JOIN produtos p ON m.produto_id = p.id
        LEFT JOIN usuarios u ON m.usuario_id = u.id
        ORDER BY m.id DESC
    """)
    movimentacoes = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(movimentacoes), 200

# API para cadastrar um novo utilizador via requisição JSON
@app.route('/api/usuarios', methods=['POST'])
def api_cadastrar_usuario():
    dados = request.get_json() or request.form
    username = dados.get('username')
    password = dados.get('password')
    role = dados.get('role', 'usuario')

    hashed_password = gerar_hash(password)

    conn = banco_conexao()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash, role) VALUES (%s, %s, %s)",
            (username, hashed_password, role)
        )
        conn.commit()
        return jsonify({"sucesso": True, "mensagem": "Usuário cadastrado com sucesso!"}), 201
    except mysql.connector.Error:
        conn.rollback()
        return jsonify({"sucesso": False, "erro": "Nome de usuário já existe."}), 400
    finally:
        cursor.close()
        conn.close()


# ==========================================
# INICIALIZAÇÃO E CONFIGURAÇÃO DO ADMINISTRADOR
# ==========================================

# Garante que existe sempre um administrador padrão na base de dados ao iniciar o servidor
def garantir_admin_padrao():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM usuarios WHERE role = 'admin' LIMIT 1")
        admin_existente = cursor.fetchone()

        if not admin_existente:
            senha_hash = gerar_hash('1503')
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, role) VALUES (%s, %s, %s)",
                ('alebeanunes@gmail.com', senha_hash, 'admin')
            )
            conn.commit()
            print("Administrador padrão criado automaticamente com sucesso!")
        else:
            print("Administrador padrão já existe na base de dados.")
    except Exception as err:
        print(f"Erro ao verificar/criar administrador padrão: {err}")
    finally:
        cursor.close()
        conn.close()

# Executa a verificação do administrador logo no arranque da aplicação Flask
with app.app_context():
    garantir_admin_padrao()

# Executa o servidor web local em modo de depuração (debug)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)