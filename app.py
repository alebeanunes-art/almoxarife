from flask import Flask, render_template, request, redirect, url_for, session,jsonify
from flask_cors import CORS
import mysql.connector
import bcrypt

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = 'senai_almoxarifado_chave'



# ==========================================
# CONEXÃO BANCO DE DADOS
# ==========================================
def banco_conexao():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='almoxarife'
    )

# ==========================================
# ROTAS DE PÁGINAS (HTML)
# ==========================================

# 1. TELA DE LOGIN
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

        if usuario and bcrypt.checkpw(password.encode('utf-8'), usuario['password_hash'].encode('utf-8')):
            # Salva os dados na sessão
            session['usuario_id'] = usuario['id']
            session['username'] = usuario['username']
            session['role'] = usuario['role']
            return redirect(url_for('home_page'))
        
        return render_template('login.html', erro="Usuário ou senha incorretos.")

    return render_template('login.html')

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# 2. TELA HOME (PRODUTOS DO ESTOQUE)
@app.route('/home')
def home_page():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produtos ORDER BY id DESC")
    produtos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('home.html', produtos=produtos)

# 3. TELA DE MOVIMENTAÇÕES (HISTÓRICO AUTOMÁTICO)
@app.route('/movimentacoes')
def movimentacoes_page():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)

    # O LEFT JOIN relaciona os IDs com as tabelas de produtos e usuários para trazer os nomes
    cursor.execute("""
        SELECT 
            m.id, 
            m.tipo, 
            m.quantidade, 
            m.data_movimentacao,
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
    return render_template('movimentacoes.html', movimentacoes=movimentacoes)

# 4. CADASTRO DE USUÁRIO (APENAS ADMIN)
@app.route('/add-usuario', methods=['GET', 'POST'])
def add_usuario_page():
    # Bloqueia quem não for admin e redireciona para a home
    if session.get('role') != 'admin':
        return redirect(url_for('home_page'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'usuario')

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        conn = banco_conexao()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, role) VALUES (%s, %s, %s)",
                (username, hashed_password, role)
            )
            conn.commit()
            return render_template('add-usuario.html', mensagem="Usuário cadastrado com sucesso!")
        except mysql.connector.Error:
            conn.rollback()
            return render_template('add-usuario.html', erro="Nome de usuário já existe.")
        finally:
            cursor.close()
            conn.close()

    return render_template('add-usuario.html')

# ==========================================
# ROTAS DE API (AUTENTICAÇÃO, USUÁRIOS E PRODUTOS)
# ==========================================


# 1. API DE LOGIN
@app.route('/api/login', methods=['POST'])
def api_login():
    username = request.form.get('username') or (request.get_json() or {}).get('username')
    password = request.form.get('password') or (request.get_json() or {}).get('password')

    if not username or not password:
        return jsonify({"sucesso": False, "erro": "Usuário e senha são obrigatórios."}), 400

    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()

    if usuario and bcrypt.checkpw(password.encode('utf-8'), usuario['password_hash'].encode('utf-8')):
        session['usuario_id'] = usuario['id']
        session['username'] = usuario['username']
        session['role'] = usuario['role']
        return jsonify({"sucesso": True, "redirecionar": url_for('home_page')}), 200

    return jsonify({"sucesso": False, "erro": "Usuário ou senha incorretos."}), 401


# 2. API DE LOGOUT
@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({"sucesso": True, "redirecionar": url_for('login_page')}), 200


# 3. API DE CADASTRAR USUÁRIO (APENAS ADMIN)
@app.route('/api/usuarios', methods=['POST'])
def api_cadastrar_usuario():
    usuario_id = session.get('usuario_id')
    
    if not usuario_id:
        return jsonify({"sucesso": False, "erro": "Sessão expirada. Faça login novamente."}), 401

    # Busca o cargo atualizado direto no banco de dados para evitar sessões presas
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT role FROM usuarios WHERE id = %s", (usuario_id,))
    usuario_atual = cursor.fetchone()
    
    if not usuario_atual or usuario_atual['role'] != 'admin':
        cursor.close()
        conn.close()
        return jsonify({"sucesso": False, "erro": "Acesso negado. Apenas administradores."}), 403

    # Se passou na validação, coleta os dados para cadastrar o novo usuário
    username = request.form.get('username') or (request.get_json() or {}).get('username')
    password = request.form.get('password') or (request.get_json() or {}).get('password')
    role = request.form.get('role', 'usuario') or (request.get_json() or {}).get('role', 'usuario')

    if not username or not password:
        cursor.close()
        conn.close()
        return jsonify({"sucesso": False, "erro": "Campos obrigatórios ausentes."}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash, role) VALUES (%s, %s, %s)",
            (username, hashed_password, role)
        )
        conn.commit()
        return jsonify({"sucesso": True, "mensagem": "Usuário cadastrado com sucesso!"}), 201
    except mysql.connector.Error:
        conn.rollback()
        return jsonify({"sucesso": False, "erro": "Erro ao cadastrar usuário (nome já existente)."}), 409
    finally:
        cursor.close()
        conn.close()

# 4. API DE CADASTRAR PRODUTO (+ HISTÓRICO AUTOMÁTICO)
@app.route('/api/produtos', methods=['POST'])
def api_cadastrar_produto():
    if 'usuario_id' not in session:
        return jsonify({"sucesso": False, "erro": "Sessão expirada. Faça login novamente."}), 401

    dados = request.form or request.get_json() or {}
    nome = dados.get('nome')
    categoria = dados.get('categoria')
    quantidade = int(dados.get('quantidade', 0))
    foto = dados.get('foto', '')
    usuario_id = session.get('usuario_id')

    if not nome or not categoria:
        return jsonify({"sucesso": False, "erro": "Nome e categoria são obrigatórios."}), 400

    conn = banco_conexao()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO produtos (codigo, nome, categoria, quantidade, foto) VALUES (%s, %s, %s, %s, %s)",
            ('TEMP', nome, categoria, quantidade, foto)
        )
        produto_id = cursor.lastrowid
        codigo_auto = f"{produto_id:03d}"
        cursor.execute("UPDATE produtos SET codigo = %s WHERE id = %s", (codigo_auto, produto_id))

        if quantidade > 0:
            cursor.execute(
                "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, %s, %s)",
                (produto_id, usuario_id, 'entrada', quantidade)
            )

        conn.commit()
        return jsonify({"sucesso": True, "mensagem": "Produto cadastrado com sucesso!", "redirecionar": url_for('home_page')}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"sucesso": False, "erro": f"Erro no banco de dados: {err}"}), 500
    finally:
        cursor.close()
        conn.close()


# 5. API DE EDITAR PRODUTO (+ HISTÓRICO AUTOMÁTICO DE ENTRADA/SAÍDA)
@app.route('/api/produtosEditar', methods=['POST'])
def api_editar_produto():
    if 'usuario_id' not in session:
        return jsonify({"sucesso": False, "erro": "Sessão expirada. Faça login novamente."}), 401

    dados = request.form or request.get_json() or {}
    produto_id = dados.get('id')
    codigo = dados.get('codigo')
    nome = dados.get('nome')
    categoria = dados.get('categoria')
    nova_quantidade = int(dados.get('quantidade', 0))
    foto = dados.get('foto', '')
    usuario_id = session.get('usuario_id')

    if not produto_id or not nome:
        return jsonify({"sucesso": False, "erro": "ID e Nome do produto são obrigatórios."}), 400

    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT quantidade FROM produtos WHERE id = %s", (produto_id,))
        prod_atual = cursor.fetchone()
        
        if not prod_atual:
            return jsonify({"sucesso": False, "erro": "Produto não encontrado."}), 404
            
        qtd_antiga = prod_atual['quantidade']

        cursor.execute("""
            UPDATE produtos 
            SET codigo = %s, nome = %s, categoria = %s, quantidade = %s, foto = %s 
            WHERE id = %s
        """, (codigo, nome, categoria, nova_quantidade, foto, produto_id))

        diferenca = nova_quantidade - qtd_antiga
        if diferenca > 0:
            cursor.execute(
                "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, %s, %s)",
                (produto_id, usuario_id, 'entrada', diferenca)
            )
        elif diferenca < 0:
            cursor.execute(
                "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, %s, %s)",
                (produto_id, usuario_id, 'saida', abs(diferenca))
            )

        conn.commit()
        return jsonify({"sucesso": True, "mensagem": "Produto atualizado com sucesso!", "redirecionar": url_for('home_page')}), 200
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"sucesso": False, "erro": f"Erro ao editar: {err}"}), 500
    finally:
        cursor.close()
        conn.close()
# ==========================================
# EXECUÇÃO DO SERVIDOR
# ==========================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)