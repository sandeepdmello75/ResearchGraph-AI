import os
from dotenv import load_dotenv
from google import genai

from app.pdf_processor import extract_text

# Load API key
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("Gemini API key not found in .env")

# Initialize Gemini
client = genai.Client(api_key=api_key)


def analyze_research_paper(pdf_path):

    print("\nReading research paper...")

    paper_text = extract_text(pdf_path)

    if not paper_text.strip():
        raise ValueError("No text extracted from PDF.")

    print("Sending paper to Gemini AI...")

    prompt = f"""
    You are an expert AI research analyst.

    Analyze the following research paper.

    Provide the results in these sections:

    1. Paper Title
    2. Authors
    3. Research Domain
    4. Problem Statement
    5. Research Objectives
    6. Methodologies Used
    7. Key Findings
    8. Limitations
    9. Future Research Opportunities
    10. Important Technical Concepts

    Only use information supported by the paper.
    If information is unavailable, explicitly say so.
    Do not invent findings or references.

    RESEARCH PAPER:

    {paper_text[:25000]}
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text


if __name__ == "__main__":

    result = analyze_research_paper("documents/sample.pdf")

    print("\n========== RESEARCHGRAPH AI ==========")
    import re

clean_result = re.sub(r"#{1,6}\s*", "", result)
clean_result = clean_result.replace("**", "")
clean_result = clean_result.replace("*", "")

print(clean_result)