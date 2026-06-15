import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# Define custom canvas to draw header, footer, and page numbers dynamically
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_page_decorations(page_count)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#4A5568"))
        
        # Header (Top of every page)
        self.drawString(54, 750, "PolicyPilot | Corporate Policy Manual")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 742, 558, 742)
        
        # Footer (Bottom of every page)
        self.line(54, 55, 558, 55)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 40, page_str)
        self.drawString(54, 40, "CONFIDENTIAL - INTERNAL USE ONLY")
        self.restoreState()


def create_policy_pdf(filename, title, content):
    """
    Creates a styled multi-page PDF document.
    """
    doc_path = Path("data/policies") / filename
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Page Margins
    doc = SimpleDocTemplate(
        str(doc_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1E3A8A"), # Navy blue
        spaceAfter=15
    )
    
    heading_style = ParagraphStyle(
        'DocHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#2563EB"), # Blue
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"), # Charcoal
        spaceAfter=10
    )
    
    story = []
    
    # Add Title
    story.append(Spacer(1, 10))
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 15))
    
    # Parse and build structure
    for section in content:
        if section.get("type") == "heading":
            story.append(Paragraph(section["text"], heading_style))
        elif section.get("type") == "body":
            story.append(Paragraph(section["text"], body_style))
        elif section.get("type") == "spacer":
            story.append(Spacer(1, section["height"]))
        elif section.get("type") == "page_break":
            story.append(PageBreak())
            
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Created: {doc_path}")


# Define Synthetic Document Data
POLICIES = {
    "leave_policy.pdf": {
        "title": "HR-01: Employee Leave and Time-Off Policy",
        "content": [
            {"type": "heading", "text": "1.0 Purpose and Scope"},
            {"type": "body", "text": "This document outlines the standard leave policies for all full-time and part-time employees. PolicyPilot values employee well-being and provides a comprehensive range of paid and unpaid time-off options to support work-life balance, medical recovery, and personal commitments."},
            
            {"type": "heading", "text": "2.0 Annual Leave"},
            {"type": "body", "text": "Full-time employees are eligible for 20 working days of paid Annual Leave per calendar year. Annual Leave accrues monthly at a rate of 1.67 days per fully completed calendar month of service. Part-time employees accrue Annual Leave on a pro-rata basis corresponding to their working hours."},
            {"type": "body", "text": "Employees are encouraged to take their annual leave within the year it is accrued. A maximum of 5 unused leave days can be carried forward to the next calendar year. Any carried-forward leave must be utilized before March 31st of the new year, or it will be automatically forfeited. Prior approval of at least two weeks from the reporting manager is mandatory for leave requests exceeding 3 consecutive business days."},
            
            {"type": "page_break"}, # Page 2
            
            {"type": "heading", "text": "3.0 Sick Leave"},
            {"type": "body", "text": "PolicyPilot provides 10 days of paid Sick Leave per year to cover personal illness, injury, or medical appointments. Sick leave is credited upfront on January 1st of each calendar year. Unused sick leave does not carry forward to the next year and cannot be cashed out upon termination."},
            {"type": "body", "text": "If an employee is absent due to illness for more than 2 consecutive business days, they must submit a valid medical certificate from a licensed physician to the HR portal on their day of return. Employees must notify their supervisor via Slack or email by 9:00 AM on each day of sick leave absence."},
            
            {"type": "heading", "text": "4.0 Parental and Family Leave"},
            {"type": "body", "text": "To support new parents, the company offers paid Parental Leave. Female employees who have completed at least 12 months of continuous service are entitled to 12 weeks of fully paid Maternity Leave. Male employees with equivalent tenure are entitled to 4 weeks of fully paid Paternity Leave. Parental leave applies to the birth of a child, adoption, or foster placement, and must be taken within the first 6 months of the child's arrival."},
            
            {"type": "page_break"}, # Page 3
            
            {"type": "heading", "text": "5.0 Bereavement Leave"},
            {"type": "body", "text": "In the unfortunate event of the death of an immediate family member, employees are entitled to up to 5 consecutive business days of paid Bereavement Leave. Immediate family members include a spouse, domestic partner, child, parent, or sibling. For extended family members (grandparents, aunts, uncles, in-laws), employees are entitled to up to 3 consecutive business days of paid leave. Additional unpaid time-off or annual leave may be requested if travel is required."},
            
            {"type": "heading", "text": "6.0 Leave Without Pay (LWOP)"},
            {"type": "body", "text": "Under special circumstances, employees may request Leave Without Pay (LWOP) for up to 30 calendar days. LWOP will only be considered after all accrued annual leave has been fully exhausted. Requests for LWOP must be submitted in writing and require written approval from both the employee's direct manager and the HR Director. During LWOP, health insurance benefits remain active, but accrual of annual leave and seniority will be suspended."}
        ]
    },
    
    "it_policy.pdf": {
        "title": "IT-02: Hardware and Asset Management Policy",
        "content": [
            {"type": "heading", "text": "1.0 Equipment Allocation and Ownership"},
            {"type": "body", "text": "All hardware assets, including laptops, monitors, mobile devices, and peripherals supplied by PolicyPilot remain the sole property of the company. Upon joining, full-time employees are allocated a standard hardware kit consisting of one high-performance laptop (typically a 16-inch Apple MacBook Pro or Lenovo ThinkPad T16), a 27-inch external monitor, and a wireless keyboard and mouse. Hardware is configured with standard security protocols before distribution."},
            
            {"type": "heading", "text": "2.0 Hardware Replacement Cycle"},
            {"type": "body", "text": "Laptops are scheduled for hardware replacement every 3 years of active service. External monitors, keyboards, mice, and docking stations are replaced on a 5-year cycle. Employees who experience hardware malfunctions or severe performance degradation before the cycle end date should file a troubleshooting ticket via the IT Helpdesk. Replacement approvals for early upgrades are subject to IT Director clearance."},
            
            {"type": "page_break"}, # Page 2
            
            {"type": "heading", "text": "3.0 Software and Application Requests"},
            {"type": "body", "text": "Employees must not install unauthorized or unlicensed software on company-issued laptops. All software requests must be submitted through the IT Service Catalog. Standard software tools (Slack, Microsoft Office, Google Workspace, Zoom) are pre-installed. Premium software licenses (e.g., Adobe Creative Cloud, JetBrains IDEs) require manager approval and budget allocation before IT provisioning. The IT department conducts quarterly automated scans of all devices; unauthorized software will be flagged and remotely uninstalled."},
            
            {"type": "heading", "text": "4.0 Password and Access Security"},
            {"type": "body", "text": "Passwords for corporate accounts must be a minimum of 14 characters, combining uppercase and lowercase letters, numbers, and special characters. Passwords must be updated every 90 days, and reuse of the last five passwords is prohibited. Multi-factor Authentication (MFA) via Duo Mobile or Google Authenticator is mandatory for accessing all corporate portals, including email, VPN, and HR portals. Passwords must never be written down or shared with colleagues."},
            
            {"type": "page_break"}, # Page 3
            
            {"type": "heading", "text": "5.0 Lost, Stolen, or Damaged Devices"},
            {"type": "body", "text": "If a company-issued device is lost or stolen, the employee must report the incident to the IT Security team at security@policypilot.com within 2 hours of discovery. This is critical to enable immediate remote data wipe commands. In the case of theft, the employee must also file a police report within 24 hours and send a copy of the official police report to HR. If hardware damage occurs due to gross negligence, the employee may be held financially responsible for repair or replacement costs."}
        ]
    },
    
    "expense_policy.pdf": {
        "title": "FIN-03: Travel and Expense Reimbursement Policy",
        "content": [
            {"type": "heading", "text": "1.0 Travel Authorization and Booking"},
            {"type": "body", "text": "All corporate travel must be pre-approved in writing by the department head at least 14 days prior to departure. All flight bookings must be made through the company's designated travel management portal (Concur). Employees must book economy class tickets for all domestic flights. Business class bookings are strictly prohibited for domestic routes but may be permitted for international flights exceeding 8 hours of continuous travel, subject to prior VP approval."},
            
            {"type": "heading", "text": "2.0 Hotel and Lodging Guidelines"},
            {"type": "body", "text": "Hotel reservations must be booked within corporate rate thresholds. The maximum allowable room rate is $150 per night (excluding taxes) for domestic locations, and $250 per night (excluding taxes) for international destinations. Standard single rooms should be selected. If lodging cannot be secured within these limits due to high-demand events (e.g., conferences), written approval from the Finance Director must be attached to the expense report."},
            
            {"type": "page_break"}, # Page 2
            
            {"type": "heading", "text": "3.0 Meals and Incidentals"},
            {"type": "body", "text": "The company provides a daily meal and incidental allowance (per diem) to cover food, beverages, and minor tips during business travel. The per diem rate is $50 per day for domestic travel and $80 per day for international travel. Employees do not need to submit individual receipts for meals if claiming the standard per diem. If choosing actual expense reimbursement instead of per diem, itemized receipts are required for all meals, and alcohol expenses are not eligible for reimbursement."},
            
            {"type": "heading", "text": "4.0 Submission Deadlines and Receipts"},
            {"type": "body", "text": "All expense claims, including travel, meals, and business entertainment, must be submitted in the Concur portal within 30 days of incurring the expense. Late submissions exceeding 60 days will be rejected, and the employee will bear the cost. Itemized receipts are mandatory for all individual transactions above $25. Credit card slips or bank statements are not accepted as valid proof of purchase. Approvals follow a standard workflow: manager approval under $500, Director approval up to $2000, and VP approval for expenses over $2000."}
        ]
    },
    
    "code_of_conduct.pdf": {
        "title": "HR-04: Corporate Code of Conduct and Ethics",
        "content": [
            {"type": "heading", "text": "1.0 Professional Integrity and Diversity"},
            {"type": "body", "text": "PolicyPilot is committed to fostering a diverse, inclusive, and professional work environment. We maintain a zero-tolerance policy for any form of harassment, discrimination, or bullying based on race, gender, religion, age, sexual orientation, disability, or national origin. Employees must treat all colleagues, contractors, and clients with respect. Violation of this policy will lead to immediate disciplinary action, up to and including termination of employment."},
            
            {"type": "heading", "text": "2.0 Conflict of Interest"},
            {"type": "body", "text": "Employees must avoid situations where their personal interests conflict, or appear to conflict, with the interests of PolicyPilot. A conflict of interest arises when an employee's external activities, relationships, or financial investments influence their professional judgment. Employees must declare any secondary employment, board memberships, or significant financial interest in competitors, vendors, or clients via the HR portal. Prior written approval from the Ethics Committee is required before engaging in secondary employment."},
            
            {"type": "page_break"}, # Page 2
            
            {"type": "heading", "text": "3.0 Confidentiality and Data Protection"},
            {"type": "body", "text": "Employees have access to proprietary software, customer databases, trade secrets, and financial projections. All such information must be kept strictly confidential and must never be shared outside the company without explicit authorization. Confidential data must not be stored on personal clouds, personal USB drives, or personal devices. Access credentials (passwords, API keys) must be protected and never exposed in public repositories or unauthorized chat channels."},
            
            {"type": "heading", "text": "4.0 Gifts, Hospitality, and Bribery"},
            {"type": "body", "text": "To prevent corruption and maintain objective business relationships, employees must not offer, accept, or solicit any bribes, kickbacks, or inappropriate gifts. Employees are permitted to accept minor promotional items (pens, notebooks) or business meals valued under $50. Gifts, entertainment, or hospitality valued above $50 from existing or potential clients, vendors, or suppliers must be declined or declared to the Compliance Team at compliance@policypilot.com."},
            
            {"type": "page_break"}, # Page 3
            
            {"type": "heading", "text": "5.0 Whistleblower Protection and Reporting"},
            {"type": "body", "text": "PolicyPilot encourages employees to report any suspected ethical breaches, financial fraud, security violations, or policy infractions. Reports can be filed anonymously through the Compliance Hotline at 1-800-555-CODE or by email to ethics@policypilot.com. The company guarantees absolute protection against retaliation, demotion, or harassment for whistleblowers reporting in good faith. False accusations made maliciously, however, will result in disciplinary action."}
        ]
    },
    
    "wfh_policy.pdf": {
        "title": "HR-05: Remote and Hybrid Work Policy",
        "content": [
            {"type": "heading", "text": "1.0 Hybrid Work Schedule and Eligibility"},
            {"type": "body", "text": "PolicyPilot supports a hybrid working arrangement. Full-time employees are eligible for the hybrid model after completing their 3-month probation period, subject to manager approval. Under this policy, employees are required to work from the corporate office for a minimum of 2 days per week, and are permitted to work from home for up to 3 days per week. Core working hours are designated as 10:00 AM to 4:00 PM local time. Employees must be available for meetings and collaboration during these hours."},
            
            {"type": "heading", "text": "2.0 Home Office Equipment Allowance"},
            {"type": "body", "text": "To ensure employees have a safe, ergonomic, and productive work environment at home, the company provides a one-time Home Office Equipment Allowance of up to $500. This allowance can be used to purchase an ergonomic office chair, desk, external keyboard, mouse, and noise-canceling headphones. Receipts must be submitted through the expense portal within 60 days of purchase under the 'WFH Allowance' category. Equipment purchased remains the property of the company and must be returned if employment ends within 12 months."},
            
            {"type": "page_break"}, # Page 2
            
            {"type": "heading", "text": "3.0 Internet and Utilities Allowance"},
            {"type": "body", "text": "To offset the cost of home high-speed broadband, the company offers a recurring monthly internet allowance of $50. Employees must submit their monthly internet bill as proof of active service via the expense portal by the 5th of the following month. The allowance is not paid automatically and cannot be backdated for more than 2 months. Mobile hotspots or cell phone data plans are not eligible for reimbursement under this utility allowance."},
            
            {"type": "heading", "text": "4.0 Network and Information Security"},
            {"type": "body", "text": "Working from home exposes corporate systems to domestic network risks. Employees must connect their company laptops only to secure, password-protected home Wi-Fi networks (minimum WPA2 security, WPA3 preferred). Using public, unsecured Wi-Fi networks (e.g., in coffee shops or hotels) without an active corporate VPN is strictly prohibited. The corporate VPN must remain active during all working hours. Employees must ensure that household members do not access or use company laptops, and that corporate screens are locked when away from the workspace."},
            
            {"type": "page_break"}, # Page 3
            
            {"type": "heading", "text": "5.0 Performance, Health, and Safety"},
            {"type": "body", "text": "Hybrid work performance is measured based on deliverables and adherence to deadlines. Employees must maintain the same levels of productivity as in the office. They are also responsible for maintaining a safe workspace free of hazards. PolicyPilot is not responsible for injuries occurring in the home workspace outside of designated core working hours or in areas unrelated to direct work duties."}
        ]
    }
}

if __name__ == "__main__":
    print("Generating synthetic policy PDF documents...")
    for filename, data in POLICIES.items():
        create_policy_pdf(filename, data["title"], data["content"])
    print("All synthetic PDFs generated successfully.")
