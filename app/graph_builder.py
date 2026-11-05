import os
import json
import re
import time
from pathlib import Path

import pymupdf
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


# =====================================
# 2. PDF TEXT EXTRACTION
# =====================================

def extract_pdf_text(pdf_path):

    document = pymupdf.open(pdf_path)

    try:
        full_text = "\n".join(
            page.get_text()
            for page in document
        )
    finally:
        document.close()

    return full_text


# =====================================
# 3. GEMINI KNOWLEDGE EXTRACTION
# =====================================

def extract_knowledge(paper_text):

    prompt = f"""
    Analyze this research paper.

    Return ONLY valid JSON in this format:

    {{
        "title": "Paper title",
        "authors": ["Author 1"],
        "domain": "Research domain",
        "concepts": [
            {{
                "name": "Computer Vision",
                "type": "Technology"
            }}
        ],
        "relationships": [
            {{
                "source": "Computer Vision",
                "target": "Sign Language Recognition"
            }}
        ]
    }}

    Instructions:
    - Extract only concepts supported by the paper.
    - Extract meaningful relationships.
    - Use consistent concept names.
    - Do not invent information.
    - Return valid JSON without Markdown.

    PAPER CONTENT:

    {paper_text[:20000]}
    """

    response = None

    for attempt in range(3):

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            break

        except Exception as error:

            if "503" in str(error) and attempt < 2:

                wait_time = 5 * (2 ** attempt)

                print(
                    f"Gemini unavailable. "
                    f"Retrying in {wait_time} seconds..."
                )

                time.sleep(wait_time)

            else:
                raise

    if response is None or not response.text:
        raise ValueError("Gemini returned an empty response")

    result = response.text.strip()

    result = re.sub(
        r"^```(?:json)?\s*",
        "",
        result
    )

    result = re.sub(
        r"\s*```$",
        "",
        result
    )

    knowledge = json.loads(result)

    required_fields = [
        "title",
        "authors",
        "domain",
        "concepts",
        "relationships"
    ]

    for field in required_fields:
        if field not in knowledge:
            raise ValueError(f"Missing JSON field: {field}")

    return knowledge


# =====================================
# 4. STORE KNOWLEDGE IN NEO4J
# =====================================

def store_knowledge(knowledge):

    with driver.session() as session:

        # Create or update paper using filename
        session.run(
            """
            MERGE (p:Paper {source_file: $source_file})
            SET p.title = $title,
                p.domain = $domain,
                p.authors = $authors
            """,
            source_file=knowledge["source_file"],
            title=knowledge["title"],
            domain=knowledge["domain"],
            authors=knowledge["authors"]
        )

        # Create concepts and connect them to paper
        session.run(
            """
            MATCH (p:Paper {source_file: $source_file})

            UNWIND $concepts AS item

            MERGE (c:Concept {name: item.name})
            SET c.type = item.type

            MERGE (p)-[:MENTIONS]->(c)
            """,
            source_file=knowledge["source_file"],
            concepts=knowledge["concepts"]
        )

        # Create concept-to-concept relationships
        session.run(
            """
            UNWIND $relationships AS rel

            MATCH (a:Concept {name: rel.source})
            MATCH (b:Concept {name: rel.target})

            MERGE (a)-[:RELATED_TO]->(b)
            """,
            relationships=knowledge["relationships"]
        )

    print("Knowledge successfully stored in Neo4j!")


# =====================================
# 5. PROCESS MULTIPLE PDF PAPERS
# =====================================

def process_all_papers():

    documents_folder = Path("documents")

    pdf_files = sorted(
        documents_folder.glob("*.pdf")
    )

    if not pdf_files:
        print("No PDF files found in documents folder.")
        return

    print(f"Found {len(pdf_files)} research papers.")

    successful = 0
    failed = 0

    try:

        driver.verify_connectivity()

        for pdf_path in pdf_files:

            print("\n" + "=" * 50)
            print(f"Processing: {pdf_path.name}")
            print("=" * 50)

            try:

                # Extract PDF
                paper_text = extract_pdf_text(
                    str(pdf_path)
                )

                if not paper_text.strip():
                    raise ValueError("PDF contains no extractable text")

                print("PDF extraction successful.")

                # Gemini analysis
                print("Extracting knowledge using Gemini...")

                knowledge = extract_knowledge(
                    paper_text
                )

                # Attach unique filename
                knowledge["source_file"] = pdf_path.name

                # Store in Neo4j
                print("Storing knowledge in Neo4j...")

                store_knowledge(knowledge)

                successful += 1

                print(
                    f"Successfully processed: {pdf_path.name}"
                )

                time.sleep(3)

            except Exception as error:

                failed += 1

                print(f"Failed: {pdf_path.name}")
                print("Reason:", error)

                continue

        print("\n" + "=" * 50)
        print("RESEARCHGRAPH AI - SUMMARY")
        print("=" * 50)

        print("Total papers:", len(pdf_files))
        print("Successful:", successful)
        print("Failed:", failed)

    finally:
        driver.close()


# =====================================
# 6. MAIN EXECUTION
# =====================================

if __name__ == "__main__":

    process_all_papers()