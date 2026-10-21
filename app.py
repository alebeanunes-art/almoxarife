from flask import Flask, render_template, request, jsonify, redirect, url_for
import mysql.connector
import bcrypt

app = Flask(__name__)
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
            return redirect(url_for('home_page'))
        
        return render_template('login.html', erro="Usuário ou senha incorretos.")

    return render_template('login.html')

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

# 3. TELA DE MOVIMENTAÇÕES
@app.route('/movimentacoes', methods=['GET', 'POST'])
def movimentacoes_page():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)

    # PROCESSA NOVA MOVIMENTAÇÃO (POST)
    if request.method == 'POST':
        produto_id = request.form.get('produto_id')
        tipo = request.form.get('tipo')
        quantidade = int(request.form.get('quantidade', 0))
        usuario_id = 1  # ID padrão até implementar a sessão

        try:
            # Insere no histórico
            cursor.execute(
                "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, %s, %s)",
                (produto_id, usuario_id, tipo, quantidade)
            )
            # Atualiza a quantidade do produto
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

    # CARREGA TABELAS (GET)
    cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()

    cursor.execute("""
        SELECT m.id, p.nome AS produto_nome, p.foto AS produto_foto, m.tipo, m.quantidade, m.data_movimentacao, u.username
        FROM movimentacoes m
        JOIN produtos p ON m.produto_id = p.id
        JOIN usuarios u ON m.usuario_id = u.id
        ORDER BY m.id DESC
    """)
    movimentacoes = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('movimentacoes.html', produtos=produtos, movimentacoes=movimentacoes)

# 4. TELA DE CADASTRO DE USUÁRIO
@app.route('/add-usuario', methods=['GET', 'POST'])
def add_usuario_page():
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
# ROTAS DE API (PRODUTOS)
# ==========================================

# CADASTRAR NOVO PRODUTO (CÓDIGO AUTOMÁTICO)
@app.route('/api/produtos', methods=['POST'])
def api_cadastrar_produto():
    nome = request.form.get('nome')
    categoria = request.form.get('categoria')
    quantidade = request.form.get('quantidade', 0)
    foto = request.form.get('foto', '')

    conn = banco_conexao()
    cursor = conn.cursor()
    try:
        # 1. Insere o produto com um código temporário
        cursor.execute(
            "INSERT INTO produtos (codigo, nome, categoria, quantidade, foto) VALUES (%s, %s, %s, %s, %s)",
            ('TEMP', nome, categoria, quantidade, foto)
        )
        produto_id = cursor.lastrowid # Pega o ID que o MySQL gerou automaticamente

        # 2. Gera o código formatado (ex: #001, #002)
        codigo_auto = f"{produto_id:03d}"

        # 3. Atualiza o produto com o código final
        cursor.execute("UPDATE produtos SET codigo = %s WHERE id = %s", (codigo_auto, produto_id))
        
        conn.commit()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Erro ao salvar produto: {err}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('home_page'))

# EDITAR PRODUTO EXISTENTE
@app.route('/movimentacoes', methods=['GET', 'POST'])
def movimentacoes_page():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        produto_id = request.form.get('produto_id')
        tipo = request.form.get('tipo')
        quantidade = int(request.form.get('quantidade', 0))
        usuario_id = 1  # ID padrão de usuário

        try:
            # 1. Registra no histórico
            cursor.execute(
                "INSERT INTO movimentacoes (produto_id, usuario_id, tipo, quantidade) VALUES (%s, %s, %s, %s)",
                (produto_id, usuario_id, tipo, quantidade)
            )
            # 2. Atualiza a quantidade do produto
            if tipo == 'entrada':
                cursor.execute("UPDATE produtos SET quantidade = quantidade + %s WHERE id = %s", (quantidade, produto_id))
            elif tipo == 'saida':
                cursor.execute("UPDATE produtos SET quantidade = quantidade - %s WHERE id = %s", (quantidade, produto_id))

            # ESSENCIAL: Salva as alterações no MySQL
            conn.commit()
        except mysql.connector.Error as err:
            conn.rollback()
            print(f"Erro ao salvar movimentação: {err}")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('movimentacoes_page'))
# ==========================================
# EXECUÇÃO DO SERVIDOR
# ==========================================
if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)