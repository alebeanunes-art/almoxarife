from flask import Flask, render_template, request, jsonify, session, redirect
import mysql.connector
import bcrypt


app = Flask(__name__)

app.secret_key = "chave-secreta"


# ============================================================
# CONEXÃO COM O BANCO
# ============================================================

def conectar_banco():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="sistema_estoque"
    )


# ============================================================
# ROTAS WEB / HTML
# ============================================================

@app.route("/")
def login():
    return render_template("login.html")


@app.route("/home")
def home():
    if "usuario" not in session:
        return redirect("/")

    return render_template("home.html")


@app.route("/estoque")
def estoque():
    if "usuario" not in session:
        return redirect("/")

    return render_template("estoque.html")


@app.route("/movimentacoes")
def movimentacoes():
    if "usuario" not in session:
        return redirect("/")

    return render_template("movimentacoes.html")


@app.route("/add-usuario")
def add_usuario():
    if "usuario" not in session:
        return redirect("/")

    if session["usuario"]["tipo"] != "admin":
        return redirect("/home")

    return render_template("add-usuario.html")


# ============================================================
# ROTAS API
# ============================================================

# LOGIN
@app.route("/api/login", methods=["POST"])
def api_login():

    dados = request.get_json()

    usuario = dados.get("usuario")
    senha = dados.get("senha")

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM usuarios WHERE usuario = %s",
        (usuario,)
    )

    usuario_db = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not usuario_db:
        return jsonify({
            "erro": "Usuário ou senha inválidos"
        }), 401

    senha_correta = bcrypt.checkpw(
        senha.encode("utf-8"),
        usuario_db["senha_hash"].encode("utf-8")
    )

    if not senha_correta:
        return jsonify({
            "erro": "Usuário ou senha inválidos"
        }), 401

    session["usuario"] = {
        "id": usuario_db["id"],
        "nome": usuario_db["nome"],
        "tipo": usuario_db["tipo"]
    }

    return jsonify({
        "mensagem": "Login realizado",
        "tipo": usuario_db["tipo"]
    })


# ESTOQUE
@app.route("/api/estoque", methods=["GET"])
def api_estoque():

    if "usuario" not in session:
        return jsonify({"erro": "Não autorizado"}), 401

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            nome,
            descricao,
            quantidade,
            estoque_minimo
        FROM produtos
        ORDER BY nome
    """)

    produtos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return jsonify(produtos)


# MOVIMENTAÇÕES
@app.route("/api/movimentacoes", methods=["GET"])
def api_movimentacoes():

    if "usuario" not in session:
        return jsonify({"erro": "Não autorizado"}), 401

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            m.id,
            p.nome AS produto,
            u.nome AS usuario,
            m.tipo,
            m.quantidade,
            m.data_movimentacao
        FROM movimentacoes m
        INNER JOIN produtos p
            ON m.produto_id = p.id
        INNER JOIN usuarios u
            ON m.usuario_id = u.id
        ORDER BY m.data_movimentacao DESC
    """)

    movimentacoes = cursor.fetchall()

    cursor.close()
    conexao.close()

    return jsonify(movimentacoes)


# ADICIONAR USUÁRIO
@app.route("/api/usuarios", methods=["POST"])
def api_usuarios():

    if "usuario" not in session:
        return jsonify({"erro": "Não autorizado"}), 401

    if session["usuario"]["tipo"] != "admin":
        return jsonify({"erro": "Acesso negado"}), 403

    dados = request.get_json()

    nome = dados.get("nome")
    usuario = dados.get("usuario")
    senha = dados.get("senha")
    tipo = dados.get("tipo", "usuario")

    senha_hash = bcrypt.hashpw(
        senha.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:

        cursor.execute("""
            INSERT INTO usuarios
            (nome, usuario, senha_hash, tipo)
            VALUES (%s, %s, %s, %s)
        """, (
            nome,
            usuario,
            senha_hash,
            tipo
        ))

        conexao.commit()

    except mysql.connector.IntegrityError:

        conexao.rollback()

        cursor.close()
        conexao.close()

        return jsonify({
            "erro": "Usuário já existe"
        }), 400

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Usuário cadastrado"
    }), 201


# REGISTRAR MOVIMENTAÇÃO
@app.route("/api/movimentacoes", methods=["POST"])
def api_nova_movimentacao():

    if "usuario" not in session:
        return jsonify({"erro": "Não autorizado"}), 401

    dados = request.get_json()

    produto_id = dados.get("produto_id")
    tipo = dados.get("tipo")
    quantidade = dados.get("quantidade")

    usuario_id = session["usuario"]["id"]

    if quantidade <= 0:
        return jsonify({
            "erro": "Quantidade inválida"
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute(
        "SELECT quantidade FROM produtos WHERE id = %s",
        (produto_id,)
    )

    produto = cursor.fetchone()

    if not produto:
        cursor.close()
        conexao.close()

        return jsonify({
            "erro": "Produto não encontrado"
        }), 404

    estoque = produto["quantidade"]

    if tipo == "saida":

        if estoque < quantidade:
            cursor.close()
            conexao.close()

            return jsonify({
                "erro": "Estoque insuficiente"
            }), 400

        cursor.execute("""
            UPDATE produtos
            SET quantidade = quantidade - %s
            WHERE id = %s
        """, (quantidade, produto_id))

    elif tipo == "entrada":

        cursor.execute("""
            UPDATE produtos
            SET quantidade = quantidade + %s
            WHERE id = %s
        """, (quantidade, produto_id))

    else:

        cursor.close()
        conexao.close()

        return jsonify({
            "erro": "Tipo inválido"
        }), 400

    cursor.execute("""
        INSERT INTO movimentacoes
        (produto_id, usuario_id, tipo, quantidade)
        VALUES (%s, %s, %s, %s)
    """, (
        produto_id,
        usuario_id,
        tipo,
        quantidade
    ))

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Movimentação registrada"
    }), 201


# LOGOUT
@app.route("/api/logout", methods=["POST"])
def api_logout():

    session.clear()

    return jsonify({
        "mensagem": "Logout realizado"
    })


# ============================================================
# INICIAR SERVIDOR
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)