

 
from flask import Flask, request, render_template
import os
import re
from datetime import datetime
import pytz
from tzlocal import get_localzone
 
app = Flask(__name__)
 
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
 
    return render_template('props.html',
                           uploaded_filename=uploaded_filename,
                           event_policy=event_policy,
                           combined_log=combined_log,
                           table_data=table_data,
                           regex_pattern=regex_from_pairs,
                           timestamp_policy=timestamp_policy,
                           name_value_pairs=name_value_pairs,
                           charset_options=CHARSET_OPTIONS,
                           enumerate=enumerate,
                           show_advanced=show_advanced,
                           timezone_options=TIMEZONE_OPTIONS,
                           selected_timezone=selected_timezone,
                           timestamp_format=timestamp_format,
                           timestamp_prefix=timestamp_prefix,
                           lookahead=lookahead)
 
 
if __name__ == "__main__":
    app.run(debug=True,port=5001)
 
 