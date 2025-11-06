"""
PDF Visualizer - Test harness for previewing badge layouts without printing.
Run this script directly to generate test PDFs with various text lengths.
"""

from pathlib import Path
from models import TicketPayload
from pdf_generator import generate_ticket_pdf


# --- TEST HARNESS ---
if __name__ == "__main__":
    print("🎨 PDF Visualizer - Generating test badges...\n")
    
    # Test Case 1: EXTREME - Very long everything
    extreme_case = TicketPayload(
        ticket_id="TEST-001",
        name="Associate Professor Dr. Chin Pei Yee",
        company="UMS INDUSTRY & COMMUNITY NETWORK",
        title="DEPUTY DIRECTOR, CENTRE FOR INDUSTRIAL COLLABORATION AND ENGAGEMENT",
        ticket_type="VIP",
    )

    # Test Case 2: LONG - Realistic long names from the image
    long_case = TicketPayload(
        ticket_id="TEST-002",
        name="Rosnih Binti Othman",
        company="SABAH MAJU JAYA SEKRETARIAT",
        title="PENGARAH SEKRETARIAT SABAH MAJU JAYA, JABATAN KETUA MENTERI SABAH",
        ticket_type="VIP",
    )
    
    # Test Case 3: MEDIUM - Moderate length
    medium_case = TicketPayload(
        ticket_id="TEST-003",
        name="Andy Lee Chen Hiung",
        company="UMS Faculty of Business Economics and Accountancy",
        title="Director of Accounting Centre",
        ticket_type="INVITED DELEGATE",
    )

    # Test Case 4: SHORT - Normal short names
    short_case = TicketPayload(
        ticket_id="TEST-004",
        name="Fiona Tan",
        company="Jesselton Pixel",
        title="Software Engineer",
        ticket_type="Delegate",
    )

    # Generate all test PDFs
    test_cases = [
        ("preview_extreme_long.pdf", extreme_case, "EXTREME - All very long text"),
        ("preview_long.pdf", long_case, "LONG - Realistic long text"),
        ("preview_medium.pdf", medium_case, "MEDIUM - Moderate length"),
        ("preview_short.pdf", short_case, "SHORT - Normal length"),
    ]
    
    for filename, data, description in test_cases:
        output_path = Path(filename)
        generate_ticket_pdf(output_path, data)
        print(f"✅ {description}")
        print(f"   📄 {output_path.resolve()}\n")
    
    print("=" * 60)
    print("🎉 All test PDFs generated successfully!")
    print("=" * 60)
    print("\n💡 Open the PDF files to preview the layout changes.")
    print("   The ticket type stays fixed at the bottom while")
    print("   the name/company/title adjust spacing automatically.")
