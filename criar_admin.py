import mysql.connector
import bcrypt

# Conecta ao banco
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='',
    database='almoxarife'
)
cursor = conn.cursor()

# Cria a senha criptografada para '1503'
senha_hash = bcrypt.hashpw('1503'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

try:
    # Insere o utilizador admin padrão
    cursor.execute(
        "INSERT INTO usuarios (username, password_hash, role) VALUES (%s, %s, %s)",
        ('alebeanunes@gmail.com', senha_hash, 'admin')
    )
    conn.commit()
    print("Utilizador 'alebeanunes@gmail.com' criado com sucesso!")
except mysql.connector.Error as err:
    print(f"Erro (talvez já exista): {err}")
finally:
    cursor.close()
    conn.close()