from flask import Flask, render_template, request, redirect, url_for, session
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
# ROTAS DE API (PRODUTOS E MOVIMENTAÇÕES AUTOMÁTICAS)
# ==========================================

# CADASTRAR PRODUTO
@app.route('/api/produtos', methods=['POST'])
def api_cadastrar_produto():
    nome = request.form.get('nome')
    categoria = request.form.get('categoria')
    quantidade = int(request.form.get('quantidade', 0))
    foto = request.form.get('foto', '')
    usuario_id = session.get('usuario_id', 1)

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
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Erro ao salvar produto: {err}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('home_page'))

# EDITAR PRODUTO
@app.route('/api/produtos/editar', methods=['POST'])
def api_editar_produto():
    produto_id = request.form.get('id')
    codigo = request.form.get('codigo')
    nome = request.form.get('nome')
    categoria = request.form.get('categoria')
    nova_quantidade = int(request.form.get('quantidade', 0))
    foto = request.form.get('foto', '')
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
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Erro ao editar produto: {err}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('home_page'))

# ==========================================
# EXECUÇÃO DO SERVIDOR
# ==========================================
if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)