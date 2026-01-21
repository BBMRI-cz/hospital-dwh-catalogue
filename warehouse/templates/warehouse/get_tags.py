import psycopg2
import json
import re
from decouple import config

def generate_tags(text):
    """Generuje klíčová slova na základě názvu nebo popisu."""
    words = re.findall(r'\b\w+\b', text.lower())
    common_words = {"the", "of", "and", "in", "to", "for", "by", "with", "on", "at", "from", "a", "an"}
    tags = [word for word in words if word not in common_words and len(word) > 2]
    return list(set(tags))

def get_metadata(conn):
    metadata = {}

    with conn.cursor() as cur:
        # Získání seznamu schémat
        cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('information_schema', 'pg_catalog');")
        schemas = [row[0] for row in cur.fetchall()]

        for schema in schemas:
            metadata[schema] = {}
            # Získání seznamu tabulek pro každé schéma
            cur.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}';")
            tables = [row[0] for row in cur.fetchall()]

            for table in tables:
                metadata[schema][table] = {"tags": generate_tags(table), "columns": []}

                # Získání sloupců a jejich datových typů
                cur.execute(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = '{schema}' AND table_name = '{table}';
                """)
                columns = cur.fetchall()

                for column_name, data_type in columns:
                    tags = generate_tags(column_name)
                    metadata[schema][table]["columns"].append({
                        "name": column_name,
                        "type": data_type,
                        "tags": tags
                    })

    return metadata

def save_metadata(metadata, filename="metadata.json"):
    """Uložení metadat do JSON souboru."""
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=4, ensure_ascii=False)
    print(f"Metadata byla úspěšně uložena do souboru {filename}")

def main():
    # Připojení k databázi pomocí proměnných prostředí
    conn = psycopg2.connect(
        dbname=config('METADATA_DB_NAME'),
        user=config('METADATA_DB_USER'),
        password=config('METADATA_DB_PASSWORD'),
        host=config('METADATA_DB_HOST'),
        port=config('METADATA_DB_PORT', default='5432')
    )

    try:
        metadata = get_metadata(conn)
        save_metadata(metadata)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
