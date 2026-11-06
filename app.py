from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_cors import CORS
import mysql.connector
import bcrypt

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = 'senai_almoxarifado_chave'

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
            session['usuario_id'] = usuario['id']
            session['username'] = usuario['username']
            session['role'] = usuario['role']
            return redirect(url_for('home_page'))
        
        return render_template('login.html', erro="Usuário ou senha incorretos.")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

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

@app.route('/add-usuario')
def add_usuario_page():
    if session.get('role') != 'admin':
        return redirect(url_for('home_page'))
    return render_template('add-usuario.html')


# ==========================================
# ROTAS DE API (JSON)
# ==========================================
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

    if usuario and bcrypt.checkpw(password.encode('utf-8'), usuario['password_hash'].encode('utf-8')):
        session['usuario_id'] = usuario['id']
        session['username'] = usuario['username']
        session['role'] = usuario['role']
        return jsonify({
            "sucesso": True,
            "mensagem": "Login efetuado com sucesso!",
            "usuario": {"id": usuario['id'], "username": usuario['username'], "role": usuario['role']}
        }), 200

    return jsonify({"sucesso": False, "erro": "Usuário ou senha incorretos."}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({"sucesso": True, "mensagem": "Logout efetuado com sucesso!"}), 200

@app.route('/api/produtos', methods=['GET'])
def api_listar_produtos():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produtos ORDER BY id DESC")
    produtos = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(produtos), 200

@app.route('/api/produtos', methods=['POST'])
def api_cadastrar_produto():
    # Verifica se a requisição veio em JSON ou de um formulário HTML comum
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
        
        # Se for formulário HTML, redireciona de volta para a home. Se for API/JSON, retorna JSON.
        if not request.is_json:
            return redirect(url_for('home_page'))
            
        return jsonify({"sucesso": True, "mensagem": "Produto cadastrado com sucesso!", "id": produto_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"sucesso": False, "erro": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/produtosEditar', methods=['POST'])
def api_editar_produto():
    # Trata de forma segura se veio via JSON ou Formulário HTML
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

        diferenca = nova_quantidade - qtd_antiga
        if diferenca != 0:
            tipo = 'entrada' if diferenca > 0 else 'saida'
            cursor.execute(
                "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, %s, %s)",
                (produto_id, usuario_id, tipo, abs(diferenca))
            )

        conn.commit()

        # Se for um formulário HTML tradicional, redireciona de volta para a home. Se for API, retorna JSON.
        if not request.is_json:
            return redirect(url_for('home_page'))

        return jsonify({"sucesso": True, "mensagem": "Produto atualizado com sucesso!"}), 200
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"sucesso": False, "erro": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

        
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

@app.route('/api/usuarios', methods=['POST'])
def api_cadastrar_usuario():
    dados = request.get_json() or request.form
    username = dados.get('username')
    password = dados.get('password')
    role = dados.get('role', 'usuario')

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)