import psycopg2
from config.settings import PG_HOST, PG_PORT, PG_DBNAME, PG_USER, PG_PASSWORD

def get_connection():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DBNAME, user=PG_USER, password=PG_PASSWORD)
