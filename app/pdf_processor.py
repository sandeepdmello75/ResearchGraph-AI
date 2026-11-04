import fitz

def extract_text(pdf_path):

    document = fitz.open(pdf_path)

    full_text = ""

    for page_number, page in enumerate(document):
        text = page.get_text()
        full_text += text + "\n"

    document.close()

    return full_text


if __name__ == "__main__":

    text = extract_text("documents/sample.pdf")

    print("PDF TEXT EXTRACTION SUCCESSFUL")
    print(text[:2000])