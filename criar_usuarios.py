import mysql.connector
import bcrypt


try:

    # CONEXÃO COM O BANCO
    conexao = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="sistema_estoque"
    )

    cursor = conexao.cursor()

    senha = "1234"


    # ADMIN
    senha_hash = bcrypt.hashpw(
        senha.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    cursor.execute("""
        INSERT INTO usuarios
        (nome, email, senha_hash, tipo)
        VALUES (%s, %s, %s, %s)
    """, (
        "Administrador",
        "admin@email.com",
        senha_hash,
        "admin"
    ))


    # USUÁRIO
    senha_hash = bcrypt.hashpw(
        senha.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    cursor.execute("""
        INSERT INTO usuarios
        (nome, email, senha_hash, tipo)
        VALUES (%s, %s, %s, %s)
    """, (
        "Usuário",
        "usuario@email.com",
        senha_hash,
        "usuario"
    ))


    conexao.commit()

    cursor.close()
    conexao.close()

    print("================================")
    print("USUÁRIOS CRIADOS COM SUCESSO!")
    print("================================")
    print("Admin:   admin@email.com")
    print("Usuário: usuario@email.com")
    print("Senha:   1234")


except Exception as erro:

    print("================================")
    print("ERRO AO CRIAR USUÁRIOS")
    print("================================")
    print(erro)