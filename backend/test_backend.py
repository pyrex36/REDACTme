import pytest
import io
import fitz
from fastapi.testclient import TestClient
from main import app
from redactor import redact_pdf_bytes

client = TestClient(app)

def create_sample_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    doc.set_metadata({"title": "Secret Document"})
    
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_redact_endpoint_success():
    # Canadian SIN, US SSN, email, and phone
    text = "My SIN is 123-456-789. My SSN is 123-45-6789. Contact me at john.doe@example.com or 555-123-4567."
    pdf_bytes = create_sample_pdf(text)
    
    response = client.post(
        "/redact",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "X-Redaction-Count" in response.headers
    
    # Check that output is a valid PDF and PII is removed
    redacted_pdf = response.content
    doc = fitz.open(stream=redacted_pdf, filetype="pdf")
    redacted_text = ""
    for page in doc:
        redacted_text += page.get_text("text")
        
    assert "123-456-789" not in redacted_text
    assert "123-45-6789" not in redacted_text
    assert "john.doe@example.com" not in redacted_text
    
    # Metadata should be scrubbed
    assert doc.metadata.get("title") == ""

def test_redact_endpoint_invalid_file():
    response = client.post(
        "/redact",
        files={"file": ("test.txt", b"not a pdf", "text/plain")}
    )
    assert response.status_code == 415

def test_redactor_logic():
    text = "Email: secret@domain.com, SIN: 987-654-321, SSN: 987-65-4321, Name: Jane Smith"
    pdf_bytes = create_sample_pdf(text)
    
    redacted_bytes, summary = redact_pdf_bytes(pdf_bytes)
    
    assert summary["total"] >= 3
    assert "email" in summary
    assert "SIN" in summary
    assert "SSN" in summary
    
    doc = fitz.open(stream=redacted_bytes, filetype="pdf")
    redacted_text = ""
    for page in doc:
        redacted_text += page.get_text("text")
        
    assert "secret@domain.com" not in redacted_text
    assert "987-654-321" not in redacted_text
    assert "987-65-4321" not in redacted_text
