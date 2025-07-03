import os

import zipfile
 
# Define the folder structure and content

file_structure = {

    "hello_app/default/app.conf": """[install]

is_configured = 1
 
[ui]

is_visible = true

label = Hello App
 
[launcher]

author = Middleware Talents

version = 1.0.0

description = A simple Splunk app that says Hello.

""",

    "hello_app/default/inputs.conf": """[script://./bin/hello.py]

disabled = false

interval = 60

sourcetype = hello:log

index = main

""",

    "hello_app/metadata/default.meta": """[]

access = read : [ * ], write : [ admin ]

export = system

""",

    "hello_app/bin/hello.py": """import time

print("Hello from Splunk! Timestamp:", time.strftime("%Y-%m-%d %H:%M:%S"))

""",

    "hello_app/README": "This is a complete Splunk Hello App with a UI view.",

    "hello_app/templates/hello.html": """<!DOCTYPE html>
<html>
<head>
<title>Hello Splunk App</title>
</head>
<body>
<h1>Hello from your Splunk App UI!</h1>
<p>This is a custom HTML view served by Splunk.</p>
</body>
</html>

""",

    "hello_app/default/data/ui/views/hello.xml": """<view template="dashboard.html" type="html">
<label>Hello UI</label>
<html>
<![CDATA[
<h1>Hello from your Splunk UI View!</h1>
<p>This is a custom Splunk HTML-based view.</p>

    ]]>
</html>
</view>

""",

    "hello_app/default/data/ui/nav/default.xml": """<nav>
<view name="hello" />
</nav>

"""

}
 
# Create the ZIP file

zip_filename = "hello_app.zip"

with zipfile.ZipFile(zip_filename, 'w') as zipf:

    for filepath, content in file_structure.items():

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'w') as f:

            f.write(content)

        zipf.write(filepath)

        os.remove(filepath)  # Clean up after zipping
 
print("✅ hello_app.zip created successfully!")

 