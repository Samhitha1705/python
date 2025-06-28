from flask import Flask, request, render_template, redirect, send_file, url_for, flash, jsonify
import os
import uuid
import csv
import shutil
import subprocess
import requests
from requests.auth import HTTPBasicAuth
from utils.file_utils import create_splunk_app, extract_zip, rezip_app, save_file, is_valid_splunk_conf
from email.message import EmailMessage
import smtplib

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure secret in prod

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
APPS_DIR = r'C:\Program Files\Splunk\etc\apps'
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)

SPLUNK_HOST = '127.0.0.1'
SPLUNK_PORT = '8089'
SPLUNK_USER = 'sammi17'
SPLUNK_PASSWORD = 'Sreelatha@171519'


def splunk_session():
    session = requests.Session()
    session.auth = HTTPBasicAuth(SPLUNK_USER, SPLUNK_PASSWORD)
    session.verify = False  # Disable SSL verification for self-signed certs (not recommended in prod)
    return session


def create_splunk_index(new_index_name):
    url = f'https://{SPLUNK_HOST}:{SPLUNK_PORT}/services/data/indexes'
    try:
        session = splunk_session()
        response = session.post(url, data={'name': new_index_name})
        response.raise_for_status()
        return True, None
    except Exception as e:
        return False, str(e)


# @app.route('/')
# def home():
#     return render_template('forms.html')


@app.route('/splunk_indexes')
def splunk_indexes():
    try:
        session = splunk_session()
        url = f'https://{SPLUNK_HOST}:{SPLUNK_PORT}/services/data/indexes?output_mode=json'
        response = session.get(url)
        response.raise_for_status()
        indexes = [
            entry['name']
            for entry in response.json().get('entry', [])
            if not entry['content'].get('disabled', False)
        ]
        return jsonify(indexes)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

import os
from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
import pandas as pd
from werkzeug.utils import secure_filename

from datetime import datetime

# Create a unique app_id using app name and current month-year
timestamp = datetime.now().strftime('%b_%Y').lower()  # e.g. 'jun_2025'

# Set the upload folder and allowed file extensions
UPLOAD_FOLDER = 'apps'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'your_secret_key'  # To enable flash messages

# Check if the file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Route to handle form submission
from datetime import datetime
import pprint
def safe_get(val):
    if pd.isna(val):
        return ""
    return str(val).strip()
import logging
import os
from datetime import datetime
from flask import flash, redirect, request, url_for

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # or INFO, depending on how verbose you want it

@app.route('/create_app', methods=['GET', 'POST'])
def create_app():
    app_name = request.form.get('app_name') or "app"
    index_name = request.form.get('new_index_name') or "default_index"

    timestamp = datetime.now().strftime("%b_%Y")
    app_id = f"{app_name.replace(' ', '_')}_{timestamp}"

    logger.info(f"Received request to create app: {app_id}")
    print("Received POST request at /create_app")

    # Print all form fields
    print("Form data:")
    for key, value in request.form.items():
        print(f"  {key}: {value}")

    # Print any uploaded files info
    print("Files:")
    for file_key in request.files:
        file = request.files[file_key]
        print(f"  {file_key}: {file.filename}")


    sources = []

    inputs_entry_mode = request.form.get("inputs_entry_mode", "manual")
    logger.debug(f"Inputs entry mode: {inputs_entry_mode}")

    if inputs_entry_mode == 'file':
        file = request.files.get('inputs_file_upload')
        if not file or file.filename == '':
            logger.error("No file selected for inputs.conf upload")
            flash('No file selected for inputs.conf', 'error')
            return redirect(request.url)

        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(file_path)
                logger.info(f"Saved inputs.conf upload to {file_path}")
            except Exception as e:
                logger.error(f"Failed to save uploaded file: {e}")
                flash('Failed to save uploaded file', 'error')
                return redirect(request.url)

            try:
                if filename.endswith('.csv'):
                    df = pd.read_csv(file_path)
                else:
                    df = pd.read_excel(file_path)
                logger.info(f"Loaded inputs.conf file into DataFrame, rows: {len(df)}")
            except Exception as e:
                logger.error(f"Failed to read uploaded file as DataFrame: {e}")
                flash('Invalid file format', 'error')
                return redirect(request.url)

            for _, row in df.iterrows():
                sources.append({
                    'config_type': 'inputs',
                    'stanza_type': safe_get(row.get('stanza_type')),
                    'stanza_value': safe_get(row.get('stanza_value')),
                    'ip_value': safe_get(row.get('ip_value')),
                    'log_path': safe_get(row.get('log_path')),
                    'log_file': safe_get(row.get('log_file')),
                    'source_type': safe_get(row.get('source_type')),
                    'index_name': safe_get(row.get('index_name')),
                })
        else:
            logger.error("Invalid file type for inputs.conf")
            flash('Invalid file type for inputs.conf', 'error')
            return redirect(request.url)
    else:
        try:
            count = int(request.form.get("me_count", "1"))
        except Exception as e:
            logger.warning(f"Invalid me_count value, defaulting to 1: {e}")
            count = 1

        for i in range(1, count + 1):
            sources.append({
                'config_type': 'inputs',
                'stanza_type': request.form.get(f"source{i}_stanza_type"),
                'stanza_value': request.form.get(f"source{i}_stanza_value"),
                'ip_value': request.form.get(f"source{i}_ip_value"),
                'log_path': request.form.get(f"source{i}_log_path"),
                'log_file': request.form.get(f"source{i}_log_file"),
                'source_type': request.form.get(f"source{i}_source_type"),
                'index_name': request.form.get(f"source{i}_index_name"),
            })

    sources = [s for s in sources if s.get("config_type") == "inputs"]

    app_path = os.path.join(app.config['UPLOAD_FOLDER'], app_id)
    logger.info(f"Creating splunk app at {app_path} with {len(sources)} inputs")
    try:
        create_splunk_app(app_path, app_name, index_name, sources)
    except Exception as e:
        logger.error(f"Error creating Splunk app: {e}")
        flash("Failed to create app", "error")
        return redirect(request.url)

    flash('inputs.conf created successfully!', 'success')
    logger.info(f"App created successfully: {app_id}")
    return redirect(url_for('browse_files', app_id=app_id))


def create_splunk_app(path, app_name, index_name, sources=None):
    logger.debug(f"Creating app folder structure at {path}")
    os.makedirs(path, exist_ok=True)
    folders = ['default', 'local', 'metadata', 'bin']
    for folder in folders:
        folder_path = os.path.join(path, folder)
        os.makedirs(folder_path, exist_ok=True)
        logger.debug(f"Created folder: {folder_path}")

    readme_path = os.path.join(path, 'README.txt')
    with open(readme_path, 'w') as f:
        f.write(f"App: {app_name}\nIndex: {index_name}\n")
    logger.debug(f"Wrote README.txt at {readme_path}")

    app_conf_path = os.path.join(path, 'default', 'app.conf')
    with open(app_conf_path, 'w') as f:
        f.write(f"""[install]
state = enabled

[ui]
is_visible = true
label = {app_name}

[launcher]
author = Auto Generator
description = Splunk app created via UI
version = 1.0.0
""")
    logger.debug(f"Wrote app.conf at {app_conf_path}")

    default_conf_path = os.path.join(path, 'default', 'default.conf')
    with open(default_conf_path, 'w') as f:
        f.write(f"""[install]
is_configured = 1

[ui]
is_visible = 1
label = {app_name}

[launcher]
author = {app_name}
version = 1.0.0
description = Auto-generated default.conf for {app_name}
""")
    logger.debug(f"Wrote default.conf at {default_conf_path}")

    if not sources:
        logger.info("No sources provided, skipping inputs.conf creation")
        return

    grouped = {}
    for row in sources:
        ctype = (row.get("config_type") or "default").strip().lower()
        grouped.setdefault(ctype, []).append(row)

    for conf_type, rows in grouped.items():
        conf_path = os.path.join(path, 'default', f"{conf_type}.conf")
        stanzas = {}

        for row in rows:
            stanza_type = (row.get("stanza_type") or "").strip().lower()
            stanza_value = (row.get("stanza_value") or "").strip()

            keys = [k.strip() for k in str(row.get("key") or "").split(',') if k.strip()]
            values = [v.strip() for v in str(row.get("value") or "").split(',') if v.strip()]

            if conf_type == "inputs" and stanza_type == "monitor":
                stanza = f"monitor://{stanza_value}"
            elif stanza_type and stanza_value:
                stanza = f"{stanza_type}://{stanza_value}"
            else:
                stanza = stanza_value

            if stanza not in stanzas:
                stanzas[stanza] = {}

            for k, v in zip(keys, values):
                stanzas[stanza][k] = v

            if conf_type == "inputs":
                extra_fields = {
                    "ip_address": row.get("ip_value", "").strip(),
                    "log_path": row.get("log_path", "").strip(),
                    "log_file": row.get("log_file", "").strip(),
                    "sourcetype": row.get("source_type", "").strip(),
                    "index": row.get("index_name", "").strip(),
                }

                for ek, ev in extra_fields.items():
                    if ev:
                        stanzas[stanza][ek] = ev

        os.makedirs(os.path.dirname(conf_path), exist_ok=True)
        with open(conf_path, 'w') as f:
            for stanza, kvs in stanzas.items():
                f.write(f"[{stanza}]\n")
                for k, v in kvs.items():
                    f.write(f"{k} = {v}\n")
                f.write("\n")
        logger.info(f"Wrote {conf_type}.conf at {conf_path}")

# Route to handle file browsing and openingimport os
import logging
from flask import request, render_template, flash

# Set up basic logging config (adjust level as needed)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.route('/edit/<app_id>/browse', defaults={'folder_path': ''})
@app.route('/edit/<app_id>/browse/<path:folder_path>')
def browse_files(app_id, folder_path):
    logger.info(f"browse_files called with app_id={app_id}, folder_path={folder_path}")
    app_root = os.path.join(app.config['UPLOAD_FOLDER'], app_id)

    current_folder = os.path.join(app_root, folder_path)

    if not os.path.exists(current_folder):
        logger.error(f"Folder not found: {current_folder}")
        flash('Folder not found', 'error')
        return render_template('forms.html', enumerate=enumerate)

    folders = []
    files = []

    if os.path.isdir(current_folder):
        logger.debug(f"Listing directory: {current_folder}")
        for entry in os.listdir(current_folder):
            full_path = os.path.join(current_folder, entry)
            rel_path = os.path.relpath(full_path, app_root)
            logger.debug(f"Found entry: {entry} (rel_path: {rel_path})")

            if os.path.isdir(full_path):
                folders.append({'name': entry, 'full_path': rel_path})
                logger.debug(f"Added folder: {entry}")
            elif os.path.isfile(full_path):
                files.append({'name': entry, 'full_path': rel_path})
                logger.debug(f"Added file: {entry}")
    else:
        logger.debug(f"Current path is a file: {current_folder}")
        files.append({'name': os.path.basename(current_folder), 'full_path': folder_path})

    selected_file = None
    content = None
    if folder_path and os.path.isfile(current_folder):
        logger.info(f"Reading file content: {current_folder}")
        try:
            with open(current_folder, 'r') as file:
                content = file.read()
            selected_file = folder_path
        except Exception as e:
            logger.error(f"Error reading file {current_folder}: {e}")
            flash(f"Failed to read file: {e}", "error")

    parent_path = os.path.dirname(folder_path) if folder_path else None
    readonly = request.args.get('readonly', 'false').lower() == 'true'

    logger.info(f"Rendering s1_editor.html with {len(folders)} folders and {len(files)} files")
    return render_template('s1_editor.html',
                           app_id=app_id,
                           folders=folders,
                           files=files,
                           current_path=folder_path,
                           parent_path=parent_path,
                           selected_file=selected_file,
                           content=content,
                           readonly=readonly)


# @app.route('/')
# def home():
#     return render_template('s1_index.html')


from flask import Flask, request, render_template
import os
import re
from datetime import datetime
import pytz
from tzlocal import get_localzone

 
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
 
uploaded_filename = ""
log_lines = []
event_policy = "auto"
regex_pattern = ""
timestamp_policy = "auto"
name_value_pairs = [("CHARSET", "UTF-8")]
 
TIMEZONE_OPTIONS = [
    ("UTC", "UTC"),
    ("America/Los_Angeles", "(GMT-08:00) Tijuana, Baja California"),
    ("America/New_York", "(GMT-05:00) New York"),
    ("Europe/London", "(GMT+00:00) London"),
    ("Asia/Tokyo", "(GMT+09:00) Tokyo"),
    ("Australia/Sydney", "(GMT+10:00) Sydney"),
]
 
CHARSET_OPTIONS = [
    "UTF-8", "ISO-8859-1", "US-ASCII", "UTF-16", "WINDOWS-1252", "SHIFT_JIS", "GB2312",
    "EUC-KR", "ISO-2022-JP", "KOI8-R", "ISO-8859-2", "ISO-8859-5", "ISO-8859-15", "MACROMAN",
    "IBM866", "BIG5", "EUC-JP", "TIS-620", "ISO-2022-KR", "ISO-8859-7", "ISO-8859-8",
    "WINDOWS-1251", "WINDOWS-1253", "WINDOWS-1254", "WINDOWS-1255", "WINDOWS-1256", "WINDOWS-1257"
]
 
def extract_datetime(line, time_prefix=""):
    if time_prefix and line.startswith(time_prefix):
        line = line[len(time_prefix):]
 
    dt_regex = re.compile(r'(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}(?:\.\d+)?(?:\s*[AP]M)?(?:\s+\w+)?)', re.IGNORECASE)
    match = dt_regex.search(line)
    if match:
        return match.group(1).strip()
 
    date_pattern = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')
    time_pattern = re.compile(r'\b\d{1,2}:\d{2}(?::\d{2}(\.\d+)?)?\s?(AM|PM)?\b', re.IGNORECASE)
    date_match = date_pattern.search(line)
    time_match = time_pattern.search(line)
    current_date = datetime.now().strftime('%m/%d/%Y')
 
    if date_match and time_match:
        return f"{date_match.group(0)} {time_match.group(0)}"
    elif date_match:
        return f"{date_match.group(0)} {datetime.now().strftime('%I:%M:%S %p')}"
    elif time_match:
        return f"{current_date} {time_match.group(0)}"
    else:
        return ""
 
def update_key_value(pairs, key, value):
    """Update or add a key-value pair uniquely in pairs list."""
    pairs = [p for p in pairs if p[0] != key]
    if value:
        pairs.append((key, value))
    return pairs
 
def update_should_linemerge(pairs, event_policy):
    should_merge = "true" if event_policy == "auto" else "false"
    return update_key_value(pairs, "SHOULD_LINEMERGE", should_merge)
 
def convert_to_timezone_fixed_time(dt_str, tz_name, time_format="%Y-%m-%d %H:%M:%S"):
    formats = [
        "%m/%d/%Y %I:%M:%S %p %Z",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S %Z",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y %H:%M",
    ]
 
    dt = None
    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            break
        except ValueError:
            continue
    if not dt:
        return dt_str
 
    utc = pytz.utc
    if dt.tzinfo is None:
        try:
            dt = utc.localize(dt)
        except Exception:
            pass
 
    try:
        target_tz = pytz.timezone(tz_name) if tz_name else get_localzone()
    except Exception:
        target_tz = utc
 
    dt_converted = dt.astimezone(target_tz)
    return dt_converted.strftime(time_format)
 
@app.route('/', methods=['GET', 'POST'])
def home():
    global uploaded_filename, log_lines, event_policy, regex_pattern, timestamp_policy, name_value_pairs
 
    combined_log = ""
    table_data = []
    selected_timezone = ""
    timestamp_format = "%Y-%m-%d %H:%M:%S"
    timestamp_prefix = ""
    lookahead = "128"
 
    if request.method == 'POST':
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename:
            uploaded_filename = uploaded_file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_filename)
            uploaded_file.save(filepath)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                log_lines = f.read().splitlines()
 
        event_policy = request.form.get('event_policy', event_policy)
        regex_pattern = request.form.get('regex_pattern', regex_pattern)
        timestamp_policy = request.form.get('timestamp_policy', timestamp_policy)
 
        # Parse name-value pairs from form input fields (name_0, value_0, etc.)
        name_value_pairs = []
        name_keys = sorted(
            [key for key in request.form if key.startswith('name_')],
            key=lambda k: int(k.split('_')[1])
        )
        for name_key in name_keys:
            idx = name_key.split('_')[1]
            name = request.form.get(name_key, '').strip()
            value = request.form.get(f'value_{idx}', '').strip()
            if name:
                name_value_pairs.append((name, value))
 
        # Always update REGEX_PATTERN if regex event policy
        name_value_pairs = [p for p in name_value_pairs if p[0] != "REGEX_PATTERN"]
        if event_policy == 'regex' and regex_pattern:
            name_value_pairs.append(("REGEX_PATTERN", regex_pattern))
 
        # Advanced timestamp settings
        if timestamp_policy == 'advanced':
            selected_timezone = request.form.get('timezone_select', "")
            timestamp_format = request.form.get('timestamp_format', "").strip()
            timestamp_prefix = request.form.get('timestamp_prefix', "").strip()
            lookahead = request.form.get('lookahead', "128").strip()
 
            # Remove old timestamp related keys
            for key in ("TIMEZONE", "TIME_FORMAT", "TIME_PREFIX", "MAX_TIMESTAMP_LOOKAHEAD"):
                name_value_pairs = [p for p in name_value_pairs if p[0] != key]
 
            # Add updated timestamp settings
            if selected_timezone:
                name_value_pairs.append(("TIMEZONE", selected_timezone))
            if timestamp_format:
                name_value_pairs.append(("TIME_FORMAT", timestamp_format))
            if timestamp_prefix:
                name_value_pairs.append(("TIME_PREFIX", timestamp_prefix))
            if lookahead:
                name_value_pairs.append(("MAX_TIMESTAMP_LOOKAHEAD", lookahead))
 
        # Always add/update DATETIME_CONFIG
        name_value_pairs = update_key_value(name_value_pairs, "DATETIME_CONFIG", timestamp_policy)
 
        # Add default props (replace if exists)
        default_props = [
            ("CHARSET", "UTF-8"),
            ("TRUNCATE", "10000"),
            ("NO_BINARY_CHECK", "true"),
            ("SHOULD_WRAP", "true"),
            ("LINE_BREAKER", r"([\r\n]+)")
        ]
        for key, value in default_props:
            name_value_pairs = update_key_value(name_value_pairs, key, value)
 
        # Add line merge config based on event policy
        name_value_pairs = update_should_linemerge(name_value_pairs, event_policy)
 
    # Extract values for UI population
    regex_from_pairs = ""
    for k, v in name_value_pairs:
        if k == "REGEX_PATTERN":
            regex_from_pairs = v
        elif k == "TIMEZONE":
            selected_timezone = v
        elif k == "TIME_FORMAT":
            timestamp_format = v
        elif k == "TIME_PREFIX":
            timestamp_prefix = v
        elif k == "MAX_TIMESTAMP_LOOKAHEAD":
            lookahead = v
 
    # Process logs for display
    if event_policy == 'auto':
        combined_log = "\n".join(log_lines)
 
    elif event_policy == 'every_line':
        for line in log_lines:
            dt_raw = extract_datetime(line, timestamp_prefix)
            if not dt_raw:
                base_dt = datetime.now().strftime('%m/%d/%Y 08:00:00 AM')
                dt = convert_to_timezone_fixed_time(base_dt, selected_timezone, timestamp_format) \
                    if timestamp_policy == 'advanced' else \
                    (datetime.now().strftime(timestamp_format) if timestamp_policy == 'current_time' else "")
            else:
                dt = convert_to_timezone_fixed_time(dt_raw, selected_timezone, timestamp_format) \
                    if timestamp_policy == 'advanced' else \
                    (datetime.now().strftime(timestamp_format) if timestamp_policy == 'current_time' else dt_raw)
            table_data.append({'datetime': dt, 'log': line})
 
    elif event_policy == 'regex' and regex_from_pairs:
        try:
            regex = re.compile(regex_from_pairs)
            for line in log_lines:
                if regex.search(line):
                    dt_raw = extract_datetime(line, timestamp_prefix)
                    dt = datetime.now().strftime(timestamp_format) \
                        if timestamp_policy == 'current_time' else \
                        (convert_to_timezone_fixed_time(dt_raw, selected_timezone, timestamp_format)
                         if timestamp_policy == 'advanced' else dt_raw)
                    table_data.append({'datetime': dt, 'log': line})
        except re.error:
            table_data = []
 
    show_advanced = (timestamp_policy == 'advanced')
 
    return render_template('forms.html',
                           uploaded_filename=uploaded_filename,
                           event_policy=event_policy,
                           combined_log=combined_log,
                           table_data=table_data,
                           regex_pattern=regex_from_pairs,
                           timestamp_policy=timestamp_policy,
                           name_value_pairs=name_value_pairs,
                           charset_options=CHARSET_OPTIONS,
                           
                           show_advanced=show_advanced,
                           timezone_options=TIMEZONE_OPTIONS,
                           selected_timezone=selected_timezone,
                           timestamp_format=timestamp_format,
                           timestamp_prefix=timestamp_prefix,
                           lookahead=lookahead,
                           enumerate=enumerate)


# @app.route('/')
# def index():
#     return render_template('s1_index.html',enumerate=enumerate)
# @app.route('/create_app', methods=['POST'])
# def create_app():
#     app_name = request.form.get('app_name')
#     index_name = request.form.get('index_name') or request.form.get('new_index_name')
#     me_count = request.form.get('me_count')

#     if not app_name or not index_name:
#         flash('App name and index name are required.', 'error')
#         return redirect(url_for('index'))

#     # If user wants to create a new index, try to create it in Splunk
#     if request.form.get('new_index_name'):
#         success, error = create_splunk_index(index_name)
#         if not success:
#             flash(f"Failed to create index: {error}", 'error')
#             return redirect(url_for('index'))

#     sources = []

#     if me_count is None:
#         flash('Please specify how many sources.', 'error')
#         return redirect(url_for('index'))

#     if me_count.isdigit():
#         count = int(me_count)
#         for i in range(1, count + 1):
#             source_name = request.form.get(f'source{i}_name')
#             log_path = request.form.get(f'source{i}_logpath')
#             if not source_name or not log_path:
#                 flash(f'Missing source name or log path for source {i}.', 'error')
#                 return redirect(url_for('index'))
#             sources.append({'name': source_name.strip(), 'logpath': log_path.strip()})

#     elif me_count == 'more':
#         file = request.files.get('me_file_upload')
#         if not file:
#             flash('Please upload a file with source data.', 'error')
#             return redirect(url_for('index'))

#         filename = file.filename.lower()
#         try:
#             if filename.endswith('.csv'):
#                 file_contents = file.read().decode('utf-8').splitlines()
#                 reader = csv.DictReader(file_contents)
#                 for row in reader:
#                     source_name = row.get('Source Name') or row.get('source_name') or row.get('sourceName')
#                     log_path = row.get('Log Path') or row.get('log_path') or row.get('logPath')
#                     if source_name and log_path:
#                         sources.append({'name': source_name.strip(), 'logpath': log_path.strip()})
#             else:
#                 flash('Unsupported file type. Please upload a CSV file.', 'error')
#                 return redirect(url_for('index'))

#             if not sources:
#                 flash('No valid source data found in the uploaded file.', 'error')
#                 return redirect(url_for('index'))
#         except Exception as e:
#             flash(f'Failed to process uploaded file: {str(e)}', 'error')
#             return redirect(url_for('index'))

#     else:
#         flash('Invalid sources count selection.', 'error')
#         return redirect(url_for('index'))

#     app_id = app_name
#     app_path = os.path.join(APPS_DIR, app_id)

#     create_splunk_app(app_path, app_name, index_name, sources=sources)

#     return redirect(url_for('browse_files', app_id=app_id))


@app.route('/upload_zip', methods=['POST'])
def upload_zip():
    uploaded_file = request.files.get('zip_file')
    if uploaded_file and uploaded_file.filename.endswith('.zip'):
        app_id = str(uuid.uuid4())
        app_path = os.path.join(APPS_DIR, app_id)
        os.makedirs(app_path, exist_ok=True)
        extract_zip(uploaded_file, app_path)
        return redirect(url_for('browse_files', app_id=app_id))
    flash('Please upload a valid .zip file', 'error')
    return redirect(url_for('index'))


# @app.route('/edit/<app_id>/browse', defaults={'folder_path': ''})
# @app.route('/edit/<app_id>/browse/<path:folder_path>')
# def browse_files(app_id, folder_path):
#     app_root = os.path.join(APPS_DIR, app_id)
#     current_folder = os.path.join(app_root, folder_path)

#     if not os.path.exists(current_folder):
#         flash('Folder not found', 'error')
#         return redirect(url_for('index'))

#     folders = []
#     files = []

#     for entry in os.listdir(current_folder):
#         full_path = os.path.join(current_folder, entry)
#         rel_path = os.path.relpath(full_path, app_root)
#         if os.path.isdir(full_path):
#             folders.append({'name': entry, 'full_path': rel_path})
#         else:
#             files.append({'name': entry, 'full_path': rel_path})

#     parent_path = os.path.dirname(folder_path) if folder_path else None

#     return render_template('s1_editor.html',
#                            app_id=app_id,
#                            folders=folders,
#                            files=files,
#                            current_path=folder_path,
#                            parent_path=parent_path,
#                            selected_file=None)
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO
import os
import subprocess
import smtplib
import shutil
from email.message import EmailMessage
import secrets
import re
from datetime import datetime  # <-- Added import

app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

APPS_DIR = r'C:\Your\SplunkAppsDir'  # <-- Replace with your actual Splunk Apps directory

# In-memory state (use a DB in production)
app_states = {}
from datetime import datetime

@app.route('/validate/<app_id>', methods=['GET', 'POST'])
def validation_workflow(app_id):
    stage_raw = request.args.get('stage')
    decision = request.args.get('decision')

    try:
        stage = int(stage_raw)
    except (TypeError, ValueError):
        stage = 1

    state = app_states.get(app_id, {'stage': stage, 'decision': decision, 'logs': ''})
    app_path = os.path.join(APPS_DIR, app_id)

    if stage == 2:
        logs = run_btool_check(app_path)
        state['logs'] = logs
        state['stage'] = 2

    elif stage == 3:
        logs = send_email_notification(app_id)
        state['logs'] = logs
        state['stage'] = 4  # ✅ Immediately move to Stage 4
        state['decision'] = None  # ✅ Reset decision
        state['logs'] += "\n\n⏳ Awaiting approver action..."

    elif stage == 4:
        if decision == "approve":
            logs = deploy_splunk_app(app_id, app_path)
            state.update({
                'logs': logs,
                'decision': 'approve',
                'stage': 4,
                'decision_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        elif decision == "reject":
            logs = "Deployment rejected."
            state.update({
                'logs': logs,
                'decision': 'reject',
                'stage': 4,
                'decision_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            app_states[app_id] = state
            return render_template(
                's1_flow.html',
                app_id=app_id,
                btool_logs=state['logs'],
                stage=state['stage'],
                decision=state.get('decision'),
                decision_time=state.get('decision_time'),
                reason=state.get('reason'),
                enumerate=enumerate
            )

        else:
            state.update({
                'logs': "⏳ Waiting for approver to take action...",
                'stage': 4
            })

    elif stage == 5:
        # ❌ If the app was rejected, do NOT proceed to stage 5
        if state.get('decision') == 'reject':
            state['logs'] += "\n\n🚫 App was rejected. Workflow halted at Stage 4."
            state['stage'] = 4
        else:
            logs = get_internal_logs()
            state['logs'] = logs
            state['stage'] = 5
        
    else:
        state['logs'] = "Unknown stage."
        state['stage'] = stage

    app_states[app_id] = state

    return render_template(
    's1_flow.html',
    app_id=app_id,
    btool_logs=state['logs'],
    stage=state['stage'],
    decision=state.get('decision'),
    decision_time=state.get('decision_time'),
    reason=state.get('reason'),  # ✅ ADD THIS
    enumerate=enumerate
)

@app.route('/dashboard/<app_id>')
def view_dashboard(app_id):
    return render_template('splunk_editor.html', app_id=app_id)

temp_logs = []
@app.route('/store_temp_logs', methods=['POST'])
def store_temp_logs():
    global temp_logs
    data = request.get_json()
    temp_logs = data.get('logs', [])
    print("🔥 Logs stored temporarily in backend:")
    for line in temp_logs:
        print(line)
    return jsonify({'message': 'Logs stored temporarily', 'count': len(temp_logs)})


@app.route('/apply_advanced_settings', methods=['POST'])
def apply_advanced_settings():
    data = request.get_json()
    logs = data.get('logs', [])
    charset = data.get('charset')
    datetime_config = data.get('datetime_config')
    should_linemerge = data.get('should_linemerge')
    line_breaker = data.get('line_breaker')
    no_binary_check = data.get('no_binary_check')

    # Apply logic based on advanced settings
    modified_logs = []

    for line in logs:
        # CHARSET logic (mock — actual charset handling is backend I/O level)
        if charset.lower() == 'utf-8':
            line = line.encode('utf-8', errors='ignore').decode('utf-8')

        # DATETIME_CONFIG logic (mock replacement example)
        if datetime_config and datetime_config.lower() != 'none':
            line = line.replace(datetime_config, '[datetime_config]')

        # SHOULD_LINEMERGE logic
        if should_linemerge == 'false':
            line = line.replace('\\n', '\n')

        # LINE_BREAKER logic
        if line_breaker:
            import re
            parts = re.split(line_breaker, line)
            line = ' | '.join(parts)

        # NO_BINARY_CHECK mock
        if no_binary_check == 'true':
            line = ''.join(filter(lambda x: x.isprintable(), line))

        modified_logs.append(line)

    return jsonify({'modified_logs': modified_logs})


@app.route('/approve/<app_id>', methods=['GET'])
def approve_from_email(app_id):
    token = request.args.get('token')
    state = app_states.get(app_id)

    if not state or token != state.get('token') or state.get('used'):
        return "<h3>🔒 This approval link has already been used or is invalid.</h3>"

    app_path = os.path.join(APPS_DIR, app_id)
    logs = deploy_splunk_app(app_id, app_path)
    state.update({
        'decision': 'approve',
        'logs': logs,
        'stage': 5,
        'used': True,
        'decision_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Save approval time
    })

    socketio.emit('decision_update', {'app_id': app_id, 'decision': 'approve', 'logs': logs})
    return f"<h3>✅ App '{app_id}' Approved.</h3><p>You can now close this window.</p>"


@app.route('/reject/<app_id>', methods=['GET', 'POST'])
def reject_from_email(app_id):
    token = request.args.get('token')
    state = app_states.get(app_id)

    if not state or token != state.get('token') or state.get('used'):
        return "<h3>🔒 This rejection link has already been used or is invalid.</h3>"

    if request.method == 'POST':
        reason = request.form.get('reason', '').strip()
        if not reason:
            return "<h3>⚠️ Please provide a reason.</h3>"

        state.update({
    'decision': 'reject',
    'logs': f"Deployment rejected. Reason: {reason}",
    'reason': reason,  # ✅ Store reason
    'stage': 5,
    'used': True,
    'decision_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
})


        socketio.emit('decision_update', {'app_id': app_id, 'decision': 'reject', 'logs': state['logs']})
        return f"<h3>❌ App '{app_id}' Rejected.</h3><p>Reason: {reason}</p><p>You can now close this window.</p>"

    return f"""
    <h3>Reject App '{app_id}'</h3>
    <form method="post">
        <label for="reason">Reason for rejection:</label><br>
        <textarea name="reason" rows="4" cols="50" required></textarea><br><br>
        <button type="submit">Submit</button>
    </form>
    """


def send_email_notification(app_id):
    try:
        token = secrets.token_urlsafe(16)
        state = app_states.setdefault(app_id, {'stage': 3, 'logs': '', 'decision': None})
        state.update({'token': token, 'used': False})

        approve_url = f"http://127.0.0.1:5000/approve/{app_id}?token={token}"
        reject_url = f"http://127.0.0.1:5000/reject/{app_id}?token={token}"
        dashboard_url = f"http://127.0.0.1:5000/edit/{app_id}/browse?readonly=true"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>🚀 Splunk App '{app_id}' Validation</h2>

            <p>Click below to review or edit the app in the dashboard:</p>
            <a href="{dashboard_url}" style="padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px;">🛠️ Open Dashboard</a>

            <hr style="margin: 20px 0;">

            <p>Or directly approve or reject this app deployment:</p>
            <a href="{approve_url}" style="padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px;">✅ Approve</a>
            <a href="{reject_url}" style="padding: 10px 20px; background: #dc3545; color: white; text-decoration: none; border-radius: 5px; margin-left: 10px;">❌ Reject</a>

            <p style="margin-top: 20px;"><em>Note: These links are valid for a single use only.</em></p>
        </body>
        </html>
        """


        msg = EmailMessage()
        msg['Subject'] = f'Splunk App {app_id} - Approval Needed'
        msg['From'] = 'vedasamhitha1978@gmail.com'
        msg['To'] = 'veda@middlewaretalents.com'
        msg.set_content("Your email client does not support HTML.")
        msg.add_alternative(html_content, subtype='html')

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login('vedasamhitha1978@gmail.com', 'xtas edoa xzxb gkbg')  # Use App Password
            server.send_message(msg)

        return "✅ Email sent with approval and rejection options."
    except Exception as e:
        return f"❌ Failed to send email: {str(e)}"


def run_btool_check(app_dir):
    app_name = os.path.basename(app_dir)
    conf_dirs = [os.path.join(app_dir, 'default'), os.path.join(app_dir, 'local')]
    output = ""
    for conf_dir in conf_dirs:
        if not os.path.exists(conf_dir):
            continue
        for conf_file in os.listdir(conf_dir):
            if conf_file.endswith('.conf'):
                conf_name = conf_file.replace('.conf', '')
                try:
                    cmd = [r'C:\Program Files\Splunk\bin\splunk.exe', 'btool', conf_name, 'list', '--debug', f'--app={app_name}']
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    output += f"=== {conf_name}.conf ===\n"
                    output += result.stdout if result.returncode == 0 else result.stderr
                    output += "\n\n"
                except Exception as e:
                    output += f"Error running btool for {conf_name}: {str(e)}\n\n"
    return output.strip()


@app.route('/schedule_deployment/<app_id>', methods=['POST'])
def schedule_deployment(app_id):
    schedule_date = request.form.get('schedule_date')
    schedule_time = request.form.get('schedule_time')

    if not schedule_date or not schedule_time:
        flash('Please select both date and time for scheduling.', 'error')
        return redirect(url_for('validation_workflow', app_id=app_id, stage=5))

    # 📝 You can store this in DB or config for later scheduling
    scheduled_datetime = f"{schedule_date} {schedule_time}"
    print(f"Scheduled deployment for {app_id} at {scheduled_datetime}")

    flash(f"✅ Deployment scheduled for: {scheduled_datetime}", 'success')
    return redirect(url_for('validation_workflow', app_id=app_id, stage=6))


def deploy_splunk_app(app_id, app_path):
    try:
        dest_path = os.path.join(r'C:\Program Files\Splunk\etc\apps', app_id)
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)
        shutil.copytree(app_path, dest_path)
        return f"✅ App '{app_id}' deployed successfully."
    except Exception as e:
        return f"❌ Deployment failed: {str(e)}"


def get_internal_logs():
    log_path = r'C:\Program Files\Splunk\var\log\splunk\splunkd.log'
    try:
        with open(log_path, 'r') as f:
            return f.read()[-3000:]
    except Exception as e:
        return f"❌ Could not read internal logs: {str(e)}"


# Optional: dummy routes for home and file browser


# @app.route('/browse/<app_id>')
# def browse_files(app_id):
#     return f"📁 File browser for app: {app_id}"




# @app.route('/edit/<app_id>/<path:file_path>', methods=['GET', 'POST'])
# def edit_file(app_id, file_path):
#     file_path = file_path.replace("\\", "/")
#     full_path = os.path.join(APPS_DIR, app_id, file_path)

#     if not os.path.exists(full_path):
#         flash('File not found', 'error')
#         return redirect(url_for('browse_files', app_id=app_id, folder_path=os.path.dirname(file_path)))

#     validation_message = None
#     recommendations = []

#     if request.method == 'POST':
#         content = request.form['content']

#         if full_path.endswith('.conf'):
#             is_valid, validation_message = is_valid_splunk_conf(content)
#             if not is_valid:
#                 flash(validation_message, 'error')
#                 return redirect(url_for('edit_file', app_id=app_id, file_path=file_path))

#         save_file(full_path, content)
#         flash('File saved successfully!', 'success')
#         return redirect(url_for('s1_flow', app_id=app_id))

#     with open(full_path, 'r', encoding='utf-8') as f:
#         content = f.read()

#     if os.path.basename(full_path) == 'inputs.conf':
#         if '[monitor://' not in content:
#             recommendations.append("⚠️ You haven't defined any `[monitor://...]` stanzas.")
#         if 'index =' not in content:
#             recommendations.append("💡 Add `index = your_index_name` to send data to a Splunk index.")
#         if 'disabled = 0' not in content:
#             recommendations.append("📝 Use `disabled = 0` to ensure the input is enabled.")

#     mode = request.args.get('mode', 'read')
#     read_only = (mode != 'edit')

#     app_root = os.path.join(APPS_DIR, app_id)
#     current_path = os.path.dirname(file_path)
#     parent_path = os.path.dirname(current_path) if current_path else None

#     folders, files = [], []
#     current_folder = os.path.join(app_root, current_path)
#     for entry in os.listdir(current_folder):
#         full_entry_path = os.path.join(current_folder, entry)
#         rel_path = os.path.relpath(full_entry_path, app_root)
#         if os.path.isdir(full_entry_path):
#             folders.append({'name': entry, 'full_path': rel_path})
#         else:
#             files.append({'name': entry, 'full_path': rel_path})

#     return render_template('s1_editor.html',
#                            app_id=app_id,
#                            selected_file=file_path,
#                            content=content,
#                            read_only=read_only,
#                            current_path=current_path,
#                            parent_path=parent_path,
#                            folders=folders,
#                            files=files,
#                            validation_message=validation_message,
#                            recommendations=recommendations)
# @app.route('/s1_flow/<app_id>')
# def s1_flow(app_id):
#     return render_template('s1_flow.html', app_id=app_id)

import posixpath

@app.route('/edit/<app_id>/<path:file_path>', methods=['GET', 'POST'])
def edit_file(app_id, file_path):
    file_path = file_path.replace("\\", "/")
    file_path = posixpath.normpath(file_path)

    full_path = os.path.abspath(os.path.join(APPS_DIR, app_id, file_path))
    app_root = os.path.abspath(os.path.join(APPS_DIR, app_id))

    if not full_path.startswith(app_root):
        flash("Access denied", "error")
        return redirect(url_for('browse_files', app_id=app_id))

    if not os.path.exists(full_path):
        flash('File not found', 'error')
        folder_path = posixpath.dirname(file_path)
        return redirect(url_for('browse_files', app_id=app_id, folder_path=folder_path))

    validation_message = None
    recommendations = []

    if request.method == 'POST':
        content = request.form['content']

        if full_path.endswith('.conf'):
            is_valid, validation_message = is_valid_splunk_conf(content)
            if not is_valid:
                flash(validation_message, 'error')
                return redirect(url_for('edit_file', app_id=app_id, file_path=file_path))

        save_file(full_path, content)
        flash('File saved successfully!', 'success')

        # ✅ Correct redirect
        return redirect(url_for('s1_flow', app_id=app_id))

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if os.path.basename(full_path) == 'inputs.conf':
        if '[monitor://' not in content:
            recommendations.append("⚠️ You haven't defined any `[monitor://...]` stanzas.")
        if 'index =' not in content:
            recommendations.append("💡 Add `index = your_index_name` to send data to a Splunk index.")
        if 'disabled = 0' not in content:
            recommendations.append("📝 Use `disabled = 0` to ensure the input is enabled.")

    current_path = posixpath.dirname(file_path)
    parent_path = posixpath.dirname(current_path) if current_path else None

    folders, files = [], []
    current_folder = os.path.join(app_root, current_path.replace("/", os.sep))
    for entry in os.listdir(current_folder):
        full_entry_path = os.path.join(current_folder, entry)
        rel_path = os.path.relpath(full_entry_path, app_root).replace("\\", "/")
        if os.path.isdir(full_entry_path):
            folders.append({'name': entry, 'full_path': rel_path})
        else:
            files.append({'name': entry, 'full_path': rel_path})

    return render_template('s1_editor.html',
                           app_id=app_id,
                           selected_file=file_path,
                           content=content,
                           read_only=(request.args.get('mode', 'read') != 'edit'),
                           current_path=current_path,
                           parent_path=parent_path,
                           folders=folders,
                           files=files,
                           validation_message=validation_message,
                           recommendations=recommendations)

# ✅ FIXED: This no longer redirects to itself
@app.route('/s1_flow/<app_id>')
def s1_flow(app_id):
    return render_template('s1_flow.html', app_id=app_id, stage=1, btool_logs=None)




@app.route('/download/<app_id>')
def download_app(app_id):
    app_path = os.path.join(APPS_DIR, app_id)
    zip_path = os.path.join(UPLOADS_DIR, f'{app_id}.zip')

    if os.path.exists(zip_path):
        os.remove(zip_path)

    rezip_app(app_path, zip_path)

    return send_file(zip_path, as_attachment=True)


if __name__ == '__main__':
    # app.run(debug=True, port=5000)
    socketio.run(app, debug=True ,port=5000)
