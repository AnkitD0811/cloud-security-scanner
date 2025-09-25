import json
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# Load the JSON content
with open('security_report.json', 'r') as file:
    data = json.load(file)

# Create PDF
pdf_file = "iac_security_report.pdf"
doc = SimpleDocTemplate(pdf_file, pagesize=A4)
styles = getSampleStyleSheet()
elements = []

# Title
title_style = styles['Title']
elements.append(Paragraph(data['report_title'], title_style))
elements.append(Spacer(1, 20))

# Summary
summary_style = styles['Heading2']
elements.append(Paragraph("Summary", summary_style))
elements.append(Paragraph(data['summary'], styles['BodyText']))
elements.append(Spacer(1, 20))

# Issues
issue_style = styles['Heading3']
bullet_style = ParagraphStyle(name='Bullet', leftIndent=20, bulletIndent=10)

for idx, issue in enumerate(data['issues'], 1):
    elements.append(Paragraph(f"Issue {idx}: {issue['issue_name']}", issue_style))
    elements.append(Paragraph(f"<b>Severity:</b> {issue['severity']}", styles['BodyText']))
    
    elements.append(Paragraph("<b>Possible Problems:</b>", styles['BodyText']))
    for problem in issue['possible_problems']:
        elements.append(Paragraph(f"• {problem}", bullet_style))
    
    elements.append(Paragraph("<b>Recommended Remedies:</b>", styles['BodyText']))
    for remedy in issue['remedies']:
        elements.append(Paragraph(f"• {remedy}", bullet_style))
    
    elements.append(Spacer(1, 15))

# Build PDF
doc.build(elements)

print(f"PDF report generated successfully: {pdf_file}")
