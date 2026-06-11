import os
import pandas as pd
from sqlalchemy import create_engine

def get_data_with_pandas():
    # 1. Create a "connection string" for SQLAlchemy
    # format: mysql+mysqlconnector://user:password@host:port/database
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT', '3306')
    db = os.getenv('DB_NAME')
    
    engine_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db}"
    engine = create_engine(engine_url)

    print(f"--- Fetching ps_supplier using Pandas ---")
    try:
        # 2. Use read_sql to get data directly into a DataFrame
        query = "SELECT * FROM ps_supplier LIMIT 10"
        df = pd.read_sql(query, engine)
        
        print("✅ SUCCESS! Here is the top of your data:")
        print(df.head())
        return df
    except Exception as e:
        print(f"❌ Pandas Error: {e}")

if __name__ == "__main__":
    get_data_with_pandas()
