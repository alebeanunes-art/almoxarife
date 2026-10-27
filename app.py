from flask import Flask, request, jsonify, session
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
# 1. LOGIN (API)
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

# ==========================================
# 2. PRODUTOS (API)
# ==========================================

# Listar Produtos (GET)
@app.route('/api/produtos', methods=['GET'])
def api_listar_produtos():
    conn = banco_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produtos ORDER BY id DESC")
    produtos = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(produtos), 200

# Cadastrar Produto (+ Histórico automático) (POST)
@app.route('/api/produtos', methods=['POST'])
def api_cadastrar_produto():
    dados = request.get_json() or request.form
    nome = dados.get('nome')
    categoria = dados.get('categoria')
    quantidade = int(dados.get('quantidade', 0))
    foto = dados.get('foto', '')
    usuario_id = session.get('usuario_id', 1) # Fallback para testes diretos

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
        return jsonify({"sucesso": True, "mensagem": "Produto cadastrado com sucesso!", "id": produto_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"sucesso": False, "erro": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# Editar Produto (+ Histórico automático de entrada/saída) (POST)
@app.route('/api/produtosEditar', methods=['POST'])
def api_editar_produto():
    dados = request.get_json() or request.form
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
        return jsonify({"sucesso": True, "mensagem": "Produto atualizado com sucesso!"}), 200
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"sucesso": False, "erro": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ==========================================
# 3. MOVIMENTAÇÕES (API)
# ==========================================
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

# ==========================================
# 4. USUÁRIOS (API)
# ==========================================
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