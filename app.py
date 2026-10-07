from flask import Flask, render_template, request, jsonify, redirect, url_for
import mysql.connector
import bcrypt

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'

# ==========================================
# CONEXÃO COM O BANCO DE DADOS
# ==========================================
def banco_conexao():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='almoxarife'
    )

# ==========================================
# ROTAS DAS PÁGINAS (HTML)
# ==========================================
@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        return redirect(url_for('home_page'))
    return render_template('login.html')

@app.route('/home')
def home_page():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()
    total_itens = sum(p['quantidade'] for p in produtos)
    cursor.close()
    conn.close()
    return render_template('home.html', produtos=produtos, total_itens=total_itens)

@app.route('/movimentacoes', methods=['GET', 'POST'])
def movimentacoes_page():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)

    # Processa o envio do formulário de movimentação
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        produto_id = request.form.get('produto_id')
        quantidade = int(request.form.get('quantidade'))
        usuario_id = 1 # ID fixo padrão (alterar quando implementar sessão)

        try:
            # 1. Registra a movimentação na tabela
            cursor.execute(
                "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, %s, %s)",
                (produto_id, usuario_id, tipo, quantidade)
            )
            # 2. Atualiza a quantidade do produto no estoque
            if tipo == 'entrada':
                cursor.execute("UPDATE produtos SET quantidade = quantidade + %s WHERE id = %s", (quantidade, produto_id))
            elif tipo == 'saida':
                cursor.execute("UPDATE produtos SET quantidade = quantidade - %s WHERE id = %s", (quantidade, produto_id))

            conn.commit()
        except mysql.connector.Error as err:
            conn.rollback()
            print(f"Erro: {err}")

        cursor.close()
        conn.close()
        return redirect(url_for('movimentacoes_page'))

    # Carrega dados para exibir na página (GET)
    cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()

    cursor.execute("""
        SELECT m.id, p.nome AS produto_nome, m.tipo, m.quantidade, m.data_movimentacao
        FROM movimentacoes m
        JOIN produtos p ON m.produto_id = p.id
        ORDER BY m.id DESC
    """)
    movimentacoes = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('movimentacoes.html', produtos=produtos, movimentacoes=movimentacoes)

@app.route('/estoque', methods=['GET', 'POST'])
def estoque_page():
    return render_template('estoque.html')

@app.route('/add-usuario', methods=['GET', 'POST'])
def add_usuario_page():
    return render_template('add-usuario.html')

# ==========================================
# API: AUTENTICAÇÃO E USUÁRIOS
# ==========================================
@app.route('/api/login', methods=['POST'])
def api_login():
    dados = request.get_json()
    username = dados.get('username')
    password = dados.get('password')

    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()

    if usuario and bcrypt.checkpw(password.encode('utf-8'), usuario['password_hash'].encode('utf-8')):
        return jsonify({"mensagem": "Login efetuado com sucesso!", "role": usuario['role']}), 200
    
    return jsonify({"erro": "Usuário ou senha incorretos"}), 401

@app.route('/api/usuarios', methods=['POST'])
def api_cadastrar_usuario():
    dados = request.get_json()
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
        return jsonify({"mensagem": "Usuário cadastrado com sucesso!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"erro": f"Erro no banco: {err}"}), 400
    finally:
        cursor.close()
        conn.close()

# ==========================================
# API: ESTOQUE E PRODUTOS
# ==========================================
@app.route('/api/produtos', methods=['GET'])
def api_listar_produtos():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(produtos), 200

# ==========================================
# API: MOVIMENTAÇÕES
# ==========================================
@app.route('/api/movimentacoes', methods=['POST'])
def api_registrar_movimentacao():
    dados = request.get_json()
    produto_id = dados.get('produto_id')
    usuario_id = dados.get('usuario_id')
    tipo = dados.get('tipo')
    quantidade = int(dados.get('quantidade'))

    conn = banco_conexao()
    cursor = conn.cursor()

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
        return jsonify({"mensagem": "Movimentação registrada com sucesso!"}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"erro": f"Erro ao movimentar: {err}"}), 400
    finally:
        cursor.close()
        conn.close()

# ==========================================
# INICIALIZAÇÃO DA APLICAÇÃO
# ==========================================
if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)