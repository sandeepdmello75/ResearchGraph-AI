from neo4j import GraphDatabase

driver = GraphDatabase.driver("neo4j://127.0.0.1:7687", auth=("neo4j", "Dmello@2005"))

# Search for chunks mentioning a concept across papers
query = """
MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
WHERE e.name CONTAINS $concept
RETURN c.text AS ContextChunk, e.name AS Entity, c.document_id AS Paper
LIMIT 5
"""

with driver.session() as session:
    results = session.run(query, concept="Graph")  # Replace with a concept in your papers
    for record in results:
        print(f"Paper: {record['Paper']}\nChunk: {record['ContextChunk'][:150]}...\n---")

driver.close()