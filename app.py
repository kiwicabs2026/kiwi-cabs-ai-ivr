# Fix for line 1289 in app.py
# Replace the problematic code around line 1289 with this:

# Option 1: If you're returning a simple XML response
response = """<?xml version="1.0" encoding="UTF-8"?>
<response>
    <status>success</status>
    <message>Your message here</message>
</response>"""

# Option 2: If you're building a dynamic XML response
def create_xml_response(status, message):
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<response>
    <status>{status}</status>
    <message>{message}</message>
</response>"""
    return response

# Option 3: If you're working with Flask and need to return XML
from flask import Response

@app.route('/your-endpoint')
def your_function():
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<response>
    <status>success</status>
    <data>
        <item>Value 1</item>
        <item>Value 2</item>
    </data>
</response>"""
    
    return Response(xml_content, mimetype='application/xml')

# Option 4: If you're using a template or longer XML
def get_xml_template():
    template = """<?xml version="1.0" encoding="UTF-8"?>
<root xmlns="http://example.com/schema">
    <header>
        <timestamp>{timestamp}</timestamp>
        <version>1.0</version>
    </header>
    <body>
        <content>{content}</content>
    </body>
</root>"""
    return template

# Usage example:
# xml_response = get_xml_template().format(
#     timestamp=datetime.now().isoformat(),
#     content="Your content here"
# )