from pyspark.sql import SparkSession
import os

# custom CA certificate
os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = "spark-server.pem"

# The connection string uses the 'sc://' scheme.
# Format: sc://<host>:<port>/;token=<auth_token>
# Port: 1501<GROUP_NUMBER> (e.g., 15011 for group 1, 15012 for group 2, etc.)
connection_string = "sc://10.3.15.18:<REPLACE_WITH_GROUP_PORT>/;token=<REPLACE_WITH_TOKEN>;use_ssl=true"

# Initialize the Spark Session via Spark Connect
spark = SparkSession.builder \
    .remote(connection_string) \
    .getOrCreate()

# --- Test the Connection ---

# 1. Print the Spark version
print(f"Connected to Spark version: {spark.version}")

# 2. Create a simple DataFrame and show it
data = [("Alice", 28), ("Bob", 35), ("Charlie", 22)]
columns = ["Name", "Age"]

df = spark.createDataFrame(data, columns)

print("\nSample DataFrame:")
df.show()

# Clean up the session when done
spark.stop()