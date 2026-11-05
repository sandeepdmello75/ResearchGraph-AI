import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")


class KnowledgeGraph:

    def __init__(self):
        self.driver = GraphDatabase.driver(
            URI,
            auth=(USERNAME, PASSWORD)
        )

    def verify_connection(self):
        self.driver.verify_connectivity()
        print("Connected to Neo4j successfully!")

    def close(self):
        self.driver.close()


if __name__ == "__main__":

    graph = KnowledgeGraph()

    try:
        graph.verify_connection()
    finally:
        graph.close()