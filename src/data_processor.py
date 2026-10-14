# Escribe una funcion llamada cargar_datos que reciba
# una ruta a un archivo CSV y devuelva un DataFrame de pandas.
# La funcion debe:
# - Verificar que el archivo existe.
# - Leer el CSV con pandas.
# - Convertir la columna ’fecha’ a tipo datetime.
# - Devolver el DataFrame limpio.
# - Incluir comentarios en espanol.
def cargar_datos(ruta_archivo):
    import os
    import pandas as pd

    # Verificar que el archivo existe
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"El archivo {ruta_archivo} no existe.")

    # Leer el CSV con pandas
    df = pd.read_csv(ruta_archivo)

    # Convertir la columna 'fecha' a tipo datetime
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    else:
        raise KeyError("La columna 'fecha' no se encuentra en el DataFrame.")

    # Devolver el DataFrame limpio
    return df

if __name__ == "__main__":
    df = cargar_datos("../data/raw/habitos.csv")
    print(df)
    print(df.describe())