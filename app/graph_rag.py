import os
import json
import re

from dotenv import load_dotenv
from google import genai
from neo4j import GraphDatabase


# =====================================
# 1. CONFIGURATION
# =====================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY missing in .env")

if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD]):
    raise ValueError("Neo4j credentials missing in .env")

client = genai.Client(api_key=GEMINI_API_KEY)

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
)

MODEL_NAME = "gemini-2.5-flash"


# =====================================
# 2. EXTRACT SEARCH CONCEPTS
# =====================================

def extract_search_terms(question):

    prompt = f"""
    Extract 3 to 8 important research concepts
    from the following question.

    Return ONLY valid JSON:

    {{
        "search_terms": [
            "Machine Learning",
            "Deep Learning"
        ]
    }}

    Do not answer the question.
    Extract meaningful technical terms only.

    Question: {question}
    """

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    result = response.text.strip()

    result = re.sub(r"^```(?:json)?\s*", "", result)
    result = re.sub(r"\s*```$", "", result)

    data = json.loads(result)

    terms = data.get("search_terms", [])

    if not terms:
        raise ValueError("No search concepts extracted.")

    return terms


# =====================================
# 3. RETRIEVE KNOWLEDGE FROM NEO4J
# =====================================

def retrieve_graph_context(search_terms):

    query = """
    MATCH (c:Concept)
    WHERE any(
        term IN $terms
        WHERE toLower(c.name) CONTAINS toLower(term)
        OR toLower(term) CONTAINS toLower(c.name)
    )

    MATCH (p:Paper)-[:MENTIONS]->(c)

    WITH
        p,
        collect(DISTINCT c.name) AS matched_concepts

    OPTIONAL MATCH (p)-[r:RELATED_TO]-(other:Paper)

    RETURN
        p.title AS title,
        p.source_file AS source_file,
        p.domain AS domain,
        matched_concepts,
        collect(DISTINCT CASE
            WHEN other IS NULL THEN null
            ELSE {
                title: other.title,
                source_file: other.source_file,
                shared_concepts: r.shared_concepts,
                shared_count: r.shared_count
            }
        END) AS related_papers

    LIMIT 15
    """

    with driver.session() as session:

        result = session.run(
            query,
            terms=search_terms
        )

        return [record.data() for record in result]


# =====================================
# 4. GENERATE RESEARCH ANSWER
# =====================================

def generate_answer(question, context):

    if not context:
        return (
            "I could not find matching research information "
            "in the current knowledge graph. Try a question "
            "using concepts present in your uploaded papers."
        )

    context_text = json.dumps(
        context,
        indent=2,
        ensure_ascii=False
    )

    prompt = f"""
    You are ResearchGraph AI, an intelligent
    academic research assistant.

    Answer the user's question using ONLY
    the retrieved research graph context.

    USER QUESTION:
    {question}

    RETRIEVED KNOWLEDGE GRAPH:
    {context_text}

    INSTRUCTIONS:

    1. Give a clear and structured answer.
    2. Identify relevant research papers.
    3. Explain shared concepts and relationships.
    4. Compare papers when appropriate.
    5. Mention source filenames as references.
    6. Do not invent research findings.
    7. If the graph does not contain enough
       evidence, clearly mention the limitation.
    """

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    return response.text


# =====================================
# 5. MAIN QUESTION-ANSWERING SYSTEM
# =====================================

def main():

    print("\n====================================")
    print("       RESEARCHGRAPH AI")
    print("       GraphRAG Assistant")
    print("====================================")

    driver.verify_connectivity()

    print("\nNeo4j connected successfully!")
    print("Gemini initialized successfully!")

    print("\nAsk questions about your research papers.")
    print("Type 'exit' to stop.\n")

    while True:

        question = input("\nYour question: ").strip()

        if question.lower() in ["exit", "quit"]:
            break

        if not question:
            print("Please enter a question.")
            continue

        try:

            print("\nUnderstanding your question...")

            search_terms = extract_search_terms(question)

            print("Research concepts:", search_terms)

            print("\nRetrieving graph knowledge...")

            context = retrieve_graph_context(search_terms)

            print("Retrieved paper records:", len(context))

            print("\nGenerating research answer...")

            answer = generate_answer(question, context)

            print("\n====================================")
            print("       RESEARCHGRAPH AI ANSWER")
            print("====================================")

            print(answer)

            print("\n====================================")

        except Exception as error:

            print("\nError:", error)


if __name__ == "__main__":

    try:
        main()

    finally:
        driver.close()