import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from dotenv import load_dotenv
from pymongo import MongoClient
import pandas as pd

load_dotenv()
TOKEN = os.getenv("SPARK_TOKEN")

if not TOKEN:
    raise ValueError("SPARK_TOKEN wurde in der .env Datei nicht gefunden!")

os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = "spark-server.pem"
connection_string = f"sc://10.3.15.18:15011/;token={TOKEN};use_ssl=true"

spark = SparkSession.builder.remote(connection_string).getOrCreate()
print(f"Spark Version: {spark.version}")

mongo_client = MongoClient("mongodb://localhost:27017")
db = mongo_client["db_payment"]
payments_collection = db["payments"]

payment_docs = list(payments_collection.find({}, {"_id": 0}))

if not payment_docs:
    print("Keine Zahlungen in der Datenbank gefunden! Bitte führe erst ein paar Fahrten durch.")
    spark.stop()
    exit()

pdf = pd.DataFrame(payment_docs)
df = spark.createDataFrame(pdf)
print("\n--- Rohdaten ---")
df.show()

analytics_df = df.groupBy("status").agg(
    F.count("ride_id").alias("total_rides"),
    F.sum("amount").alias("total_revenue"),
    F.avg("amount").alias("average_price")
)

print("\n--- Berechnete Kennzahlen ---")
analytics_df.show()

print("Speichere Ergebnisse in MongoDB Collection 'analytics_results'...")
results_pandas = analytics_df.toPandas()
results_dict = results_pandas.to_dict(orient="records")

analytics_collection = db["analytics_results"]
analytics_collection.delete_many({})
analytics_collection.insert_many(results_dict)

print("Fertig! Big Data Job erfolgreich abgeschlossen.")
spark.stop()
