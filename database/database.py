import sqlite3

DATABASE_PATH = 'videos.db'

def create_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DATABASE_PATH)
    return conn

def create_table():
    """Cria a tabela de vídeos se ela ainda não existir."""
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            original_name TEXT NOT NULL,
            original_ext TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            duration_sec REAL NOT NULL,
            fps REAL NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            filter TEXT NOT NULL,
            created_at TEXT NOT NULL,
            path_original TEXT NOT NULL,
            path_processed TEXT NOT NULL
        );
    ''')
    conn.commit()
    conn.close()

# Exemplo de uso:
if __name__ == '__main__':
    create_table()
    print("Tabela 'videos' criada com sucesso.")