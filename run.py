#!/usr/bin/env python3
"""Guided runner. Start it with: python3 run.py"""

import csv
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.expanduser("~/.zoom_attendance_template.json")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REGISTRY_FILES = ["master_people_db.csv", "master_name_aliases.csv", "master_dept_to_parent.csv"]
SESSIONS_HEADER = ["program", "session_date", "topic", "presenter", "length_minutes"]
FOLDER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
DEFAULT_TITLE = "Program Attendance Overview"
DEFAULT_LENGTH = 60

# Filled from programs.json in the data folder: dept_name, title, programs.
# Each program: name, folder, topics, presenters, length, hidden.
CONFIG = {}
W = SimpleNamespace()
UPLOAD = []


def set_workspace(base):
    W.base = base
    W.master = os.path.join(base, "master")
    W.workbooks = os.path.join(base, "workbooks")
    W.converted = os.path.join(base, "converted")
    W.reports = os.path.join(base, "reports")
    W.sessions = os.path.join(base, "sessions.csv")
    W.people = os.path.join(W.master, "master_people_db.csv")
    W.aliases = os.path.join(W.master, "master_name_aliases.csv")
    W.dept = os.path.join(W.master, "master_dept_to_parent.csv")
    W.config = os.path.join(base, "programs.json")


def ask(prompt, default=""):
    try:
        answer = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    except EOFError:
        sys.exit("\nInput ended. Stopping.")
    return answer or default


def yes(prompt, default=True):
    answer = ask(f"{prompt} ({'Y/n' if default else 'y/N'})").lower()
    return default if not answer else answer.startswith("y")


def choose(prompt, options):
    print(f"\n{prompt}")
    for i, label in enumerate(options, 1):
        print(f"  {i}) {label}")
    while True:
        answer = ask("Number")
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1
        print("  Please type one of the numbers above.")


def clean_path(text):
    text = text.strip().strip("'\"").replace("\\ ", " ")
    return os.path.abspath(os.path.expanduser(text))


def pick(kind, prompt):
    """kind: file, files or folder. Returns a path (a list for files) or None if cancelled."""
    if not os.environ.get("ZA_NO_DIALOG"):
        if sys.platform == "darwin":
            if kind == "files":
                script = (f'set picked to choose file with prompt "{prompt}" with multiple selections allowed\n'
                          'set out to {}\nrepeat with p in picked\nset end of out to POSIX path of p\n'
                          "end repeat\nset AppleScript's text item delimiters to linefeed\nreturn out as text")
            else:
                script = f'POSIX path of (choose {"folder" if kind == "folder" else "file"} with prompt "{prompt}")'
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                paths = [p.strip() for p in r.stdout.strip().splitlines() if p.strip()]
                return paths if kind == "files" else paths[0]
            if "-128" in r.stderr:
                return None
        else:
            try:
                import tkinter
                from tkinter import filedialog
                root = tkinter.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                if kind == "folder":
                    chosen = filedialog.askdirectory(title=prompt)
                elif kind == "files":
                    chosen = list(filedialog.askopenfilenames(title=prompt))
                else:
                    chosen = filedialog.askopenfilename(title=prompt)
                root.destroy()
                return chosen or None
            except Exception:
                pass
    if kind == "files":
        print(f"{prompt}. Paste one location per line, then press Enter on an empty line.")
        paths = []
        while True:
            line = ask("Location")
            if not line:
                return paths or None
            paths.append(clean_path(line))
    answer = ask(f"{prompt}. Paste the location")
    return clean_path(answer) if answer else None


def run_tool(script, *args):
    cmd = [sys.executable, os.path.join("tools", script), *args]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    if out.strip():
        print(out.rstrip())
    return r.returncode, out


def open_file(path):
    if sys.platform == "darwin":
        subprocess.run(["open", path])
    elif sys.platform.startswith("win"):
        os.startfile(path)
    else:
        print(f"Open this yourself: {path}")


def build_structure():
    folders = [W.master, W.workbooks, W.reports] + [os.path.join(W.converted, p["folder"]) for p in all_programs()]
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
    if not os.path.exists(W.sessions):
        with open(W.sessions, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(SESSIONS_HEADER)
    seed = os.path.join(ROOT, "config", "master_dept_to_parent.csv")
    if not os.path.exists(W.dept) and os.path.exists(seed):
        shutil.copy(seed, W.dept)


def all_programs():
    return CONFIG.get("programs", [])


def visible_programs():
    return [p for p in all_programs() if not p.get("hidden")]


def load_config():
    CONFIG.clear()
    if os.path.exists(W.config):
        with open(W.config, encoding="utf-8") as f:
            CONFIG.update(json.load(f))
    CONFIG.setdefault("programs", [])


def save_config():
    with open(W.config, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, indent=2)


def name_taken(name, skip=None):
    return any(p["name"].lower() == name.lower() for p in all_programs() if p is not skip)


def ask_program_name(default="", skip=None):
    while True:
        name = ask("Program name, as it should appear on the pages", default)
        if not name:
            print("  Please type a name.")
        elif name_taken(name, skip):
            print("  There is already a program with that name (it may be hidden).")
        else:
            return name


def suggest_folder(name):
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "program"
    folder, n = base, 2
    while any(p["folder"] == folder for p in all_programs()):
        folder, n = f"{base}_{n}", n + 1
    return folder


def add_program():
    print("\nNew program")
    name = ask_program_name()
    while True:
        folder = ask("Short folder name (lowercase letters, numbers, _ or -)", suggest_folder(name)).lower()
        if not FOLDER_RE.match(folder):
            print("  Use only lowercase letters, numbers, _ and -, starting with a letter or number.")
        elif any(p["folder"] == folder for p in all_programs()):
            print("  Another program already uses that folder name.")
        else:
            break
    prog = {"name": name, "folder": folder,
            "topics": yes("Does each session have a topic?"),
            "presenters": yes("Does each session have presenters?"),
            "length": DEFAULT_LENGTH, "hidden": False}
    CONFIG["programs"].append(prog)
    save_config()
    os.makedirs(os.path.join(W.converted, folder), exist_ok=True)
    print(f"Added {name}.")
    return prog


def setup_department():
    print("\nFirst-time setup for this data folder. You can change all of this later from the menu.")
    CONFIG["dept_name"] = ask("Your department or unit name, shown on the pages")
    CONFIG["title"] = ask("Title for the overview dashboard", DEFAULT_TITLE)
    save_config()
    print("\nNow add the programs you track. You can add more later.")
    add_program()
    while yes("Add another program?", False):
        add_program()


def save_settings():
    with open(SETTINGS, "w") as f:
        json.dump({"workspace": W.base}, f)


def is_data_folder(path):
    return os.path.exists(os.path.join(path, "programs.json")) or any(
        os.path.isdir(os.path.join(path, d)) for d in ("converted", "master"))


def resolve_base(path):
    """If the chosen folder holds 'Zoom Attendance Data' (a ZIP unzips that way), use that one."""
    path = path.rstrip("/\\")
    if not is_data_folder(path):
        inner = os.path.join(path, "Zoom Attendance Data")
        if os.path.isdir(inner):
            return inner
    return path


def choose_workspace():
    while True:
        base = pick("folder", "Choose your data folder (or an empty folder to start a new one)")
        if base:
            base = resolve_base(base)
            if not is_data_folder(base):
                print(f"\n{base}\nis not a data folder yet.")
                if not yes("Set it up as a new, empty data folder?", True):
                    continue
            return base
        if not yes("No folder was chosen. Try again?"):
            sys.exit("Setup cancelled.")


def import_registry():
    paths = pick("files", "Choose the people registry files (up to three CSV files)")
    if not paths:
        print("Nothing chosen.")
        return
    copied = []
    for p in paths:
        name = os.path.basename(p)
        if name in REGISTRY_FILES:
            shutil.copy2(p, os.path.join(W.master, name))
            copied.append(name)
        else:
            print(f"  Skipped {name}: not one of {', '.join(REGISTRY_FILES)}")
    print(f"Added {len(copied)} registry file(s) to your data folder.")


def import_converted():
    prog = pick_program(allow_new=True)
    paths = pick("files", f"Choose the converted Zoom files for {prog['name']}")
    if not paths:
        print("Nothing chosen.")
        return
    target = os.path.join(W.converted, prog["folder"])
    added = skipped = 0
    for p in paths:
        dest = os.path.join(target, os.path.basename(p))
        if os.path.exists(dest) or not p.lower().endswith(".csv"):
            skipped += 1
        else:
            shutil.copy2(p, dest)
            added += 1
    print(f"Added {added} file(s) to {prog['name']}. Skipped {skipped} (already there or not a .csv).")


def open_workspace(base):
    set_workspace(base)
    load_config()
    if not all_programs():
        setup_department()
    build_structure()


def first_run():
    print("Welcome. All your attendance data lives in one data folder, kept outside this code folder.")
    print("If your team already has one, choose it. Otherwise choose or create an empty folder.")
    base = choose_workspace()
    open_workspace(base)
    save_settings()
    print(f"\nData folder ready: {W.base}")
    if not os.path.exists(W.people) and yes("No people registry was found in 'master'. "
                                             "Do you have registry files to add now?", False):
        import_registry()


def load_workspace():
    saved = ""
    try:
        with open(SETTINGS) as f:
            saved = json.load(f).get("workspace", "")
    except (OSError, ValueError):
        pass
    if saved and os.path.isdir(saved):
        open_workspace(saved)
    else:
        first_run()


def pick_program(allow_new=False):
    progs = visible_programs()
    if not progs and not allow_new:
        sys.exit("No programs yet. Add one with 'Manage programs and page titles'.")
    labels = [p["name"] for p in progs] + (["Add a new program"] if allow_new else [])
    idx = choose("Which program?", labels)
    return progs[idx] if idx < len(progs) else add_program()


def final_path(prog):
    return os.path.join(W.workbooks, f"{prog['folder']}_final.xlsx")


def cleanup_path(prog):
    return os.path.join(W.workbooks, f"{prog['folder']}_cleanup.xlsx")


def norm_date(text):
    text = str(text).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y"):
        try:
            return time.strftime("%Y-%m-%d", time.strptime(text, fmt))
        except ValueError:
            pass
    return None


def session_date_of(path):
    try:
        col = pd.read_csv(path, dtype=str).fillna("")["Join time"]
    except Exception:
        return None
    parsed = pd.to_datetime(col, format="%m/%d/%Y %I:%M:%S %p", errors="coerce")
    for fmt in ("%m/%d/%y %H:%M", None):
        missing = parsed.isna()
        if not missing.any():
            break
        parsed = parsed.where(~missing, pd.to_datetime(col[missing], format=fmt, errors="coerce"))
    dates = parsed.dt.strftime("%Y-%m-%d").dropna()
    return dates.mode()[0] if not dates.empty else None


def bring_in_file(prog, source):
    conv_dir = os.path.join(W.converted, prog["folder"])
    os.makedirs(conv_dir, exist_ok=True)
    target = os.path.join(conv_dir, os.path.basename(source))
    tmp = target + ".tmp"

    print("\nConverting the file to the standard shape...")
    rc, _ = run_tool("normalize_to_participants_report.py", source, "--out", tmp)
    if rc != 0 or not os.path.exists(tmp):
        sys.exit("The conversion failed. Nothing was changed.")

    date = session_date_of(tmp)
    while not date:
        date = norm_date(ask("Could not read the date from the file. Type the session date (YYYY-MM-DD)"))
    print(f"Session date: {date}")

    clashes = [f for f in glob.glob(os.path.join(conv_dir, "*.csv"))
               if f != target and session_date_of(f) == date]
    if os.path.exists(target):
        clashes.append(target)
    if clashes:
        print(f"A converted file for {date} already exists in {prog['folder']}:")
        for f in clashes:
            print(f"  {os.path.basename(f)}")
        if not yes("Replace it with this new file? (the old one is moved to converted/_replaced)", False):
            os.remove(tmp)
            sys.exit("Cancelled. Nothing was changed.")
        parking = os.path.join(W.converted, "_replaced")
        os.makedirs(parking, exist_ok=True)
        for f in clashes:
            shutil.move(f, os.path.join(parking, f"{int(time.time())}_{os.path.basename(f)}"))

    os.replace(tmp, target)
    print(f"Saved the converted file in {os.path.relpath(conv_dir, W.base)}. Your original was not moved or copied.")
    UPLOAD.append(target)
    return conv_dir, date


def prepare_cleanup(prog):
    cleanup, final = cleanup_path(prog), final_path(prog)
    if not os.path.exists(cleanup):
        return
    if os.path.exists(final) and os.path.getmtime(final) >= os.path.getmtime(cleanup):
        os.remove(cleanup)
        return
    print(f"\n{os.path.basename(cleanup)} is newer than the last final workbook, so it may hold fixes that were never compiled.")
    if not yes("Delete it and start fresh anyway?", False):
        sys.exit("Stopped. Compile it first, or move it out of the data folder.")
    os.remove(cleanup)


def inspect_cleanup(cleanup):
    xl = pd.ExcelFile(cleanup)
    unresolved = {}
    for sheet in xl.sheet_names:
        if DATE_RE.match(sheet.strip()):
            df = xl.parse(sheet, dtype=str).fillna("")
            if "person_id" in df.columns:
                n = int((df["person_id"].str.strip() == "").sum())
                if n:
                    unresolved[sheet] = n
    new_people = 0
    if "people_db" in xl.sheet_names and os.path.exists(W.people):
        ids = set(xl.parse("people_db", dtype=str).fillna("")["person_id"]) - {""}
        known = set(pd.read_csv(W.people, dtype=str).fillna("")["person_id"])
        new_people = len(ids - known)
    return unresolved, new_people


def build_cleanup(prog, conv_dir):
    cleanup = cleanup_path(prog)
    args = ["--raw-dir", conv_dir, "--out", cleanup]
    for flag, path in (("--people-db", W.people), ("--dept-parent", W.dept), ("--aliases", W.aliases)):
        if os.path.exists(path):
            args += [flag, path]
    print("\nBuilding the cleanup workbook (known people are filled in automatically)...")
    rc, _ = run_tool("init_workbook.py", *args)
    if rc != 0:
        sys.exit("Building the cleanup workbook failed. Stopping.")
    return cleanup


NOTE_ONLY = ("no parent_unit", "alias", "learned")


def blocking_qc(output):
    titles = []
    in_report = False
    for line in output.splitlines():
        if line.startswith("QC REPORT"):
            in_report = True
        elif in_report and line and not line.startswith((" ", "=")) and re.search(r"\(\d+\)\s*$", line):
            titles.append(line.strip())
    return [t for t in titles if not any(k in t.lower() for k in NOTE_ONLY)]


def review_loop(prog, cleanup):
    unresolved, new_people = inspect_cleanup(cleanup)
    print("\nWhat needs your attention in Excel:")
    if unresolved:
        print(f"  {sum(unresolved.values())} attendee row(s) have no person_id yet:")
        for sheet, n in sorted(unresolved.items()):
            print(f"    sheet {sheet}: {n}")
        print("  Give each one an existing person_id, or add them as a new row in the people_db sheet.")
    if new_people:
        print(f"  {new_people} new person(s) were added to people_db. Fill in their department and status.")
    if not unresolved and not new_people:
        print("  Nothing. Everyone was matched automatically.")
    if (unresolved or new_people) and yes("Open the workbook in Excel now?"):
        open_file(cleanup)

    final = final_path(prog)
    while True:
        if unresolved or new_people:
            ask("Save and close Excel, then press Enter to continue")
        print("\nCompiling...")
        rc, out = run_tool("recompile_workbook.py", cleanup, "--out", final)
        blocking = blocking_qc(out)
        if rc == 0 and not blocking:
            if "QC REPORT" in out:
                print("\nThe items above are notes only, so the run continues.")
            return
        print("\nThe compile finished with problems that need fixing: " + "; ".join(blocking or ["compile error"]))
        if not yes("Fix them in the workbook and compile again?"):
            sys.exit("Stopped before updating the shared registry or building pages.")
        unresolved = new_people = 1


def refresh_registry(prog):
    print("\nUpdating the shared people registry and mailing list...")
    rc, _ = run_tool("refresh_master.py", final_path(prog), "--data-dir", W.master)
    if rc != 0:
        sys.exit("The registry refresh was refused (see above). Nothing was changed. Stopping.")


def read_sessions():
    rows, header = [], list(SESSIONS_HEADER)
    if os.path.exists(W.sessions):
        with open(W.sessions, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or header
            rows = list(reader)
    header += [h for h in SESSIONS_HEADER if h not in header]
    return rows, header


def write_sessions(rows, header):
    while True:
        try:
            with open(W.sessions, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=header, restval="")
                writer.writeheader()
                writer.writerows(rows)
            return
        except PermissionError:
            ask("sessions.csv is open in another program (probably Excel). Close it, then press Enter")


def ensure_session_info(prog, date):
    """Asks for whatever this session is missing: topic, presenters, meeting length."""
    rows, header = read_sessions()
    row = next((r for r in rows if r.get("program", "").strip().lower() == prog["name"].lower()
                and norm_date(r.get("session_date", "")) == date), None)
    if row is None:
        row = {"program": prog["name"], "session_date": date}
        rows.append(row)
    changed = False
    if prog["topics"] and not row.get("topic", "").strip():
        row["topic"] = ask(f"\nTopic for {prog['name']} on {date} (Enter to skip)")
        changed = changed or bool(row["topic"])
    if prog["presenters"] and not row.get("presenter", "").strip():
        row["presenter"] = ask("Presenter name(s), separated by commas (Enter to skip)")
        changed = changed or bool(row["presenter"])
    if not row.get("length_minutes", "").strip():
        while True:
            text = ask(f"How long was the {date} meeting, in minutes?", str(prog.get("length", DEFAULT_LENGTH)))
            if text.isdigit() and int(text) > 0:
                break
            print("  Please type a whole number of minutes, like 60.")
        row["length_minutes"] = text
        prog["length"] = int(text)
        save_config()
        changed = True
    if changed:
        write_sessions(rows, header)
        print("Saved to sessions.csv in your data folder.")


def build_pages(prog, date, which):
    made = []
    base = [final_path(prog), prog["name"], "--people-db", W.people, "--dept", W.dept,
            "--topics", W.sessions, "--dept-name", CONFIG.get("dept_name", "")]
    if not prog["topics"]:
        base.append("--no-topics")
    kinds = {"public": ("generate_session_pages.py", os.path.join(W.reports, prog["folder"])),
             "internal": ("generate_internal_pages.py", os.path.join(W.reports, "internal", prog["folder"]))}
    for kind in (["public", "internal"] if which == 2 else [["public", "internal"][which]]):
        script, out_dir = kinds[kind]
        print(f"\nBuilding the {kind} page...")
        rc, _ = run_tool(script, *base, "--out-dir", out_dir, "--session-date", date)
        if rc != 0:
            print(f"The {kind} page failed. See the message above.")
        else:
            made.append(os.path.join(out_dir, f"session_{date}.html"))
    return made


def pick_page_kind():
    return choose("Which page?", ["Public page", "Internal page (with names)", "Both"])


def build_aggregate():
    args = []
    for prog in visible_programs():
        if not os.path.exists(final_path(prog)):
            print(f"Skipping {prog['name']}: no final workbook yet.")
            continue
        spec = f"{prog['name']}={final_path(prog)}"
        if os.path.isdir(os.path.join(W.reports, prog["folder"])):
            spec += f"={prog['folder']}"
        args += ["--program", spec]
    if not args:
        sys.exit("No final workbooks found yet. Add a Zoom file first.")
    out = os.path.join(W.reports, "aggregate.html")
    print("\nBuilding the aggregate dashboard...")
    rc, _ = run_tool("generate_aggregate_dashboard.py", *args, "--people-db", W.people, "--dept", W.dept,
                     "--topics", W.sessions, "--out", out,
                     "--dept-name", CONFIG.get("dept_name", ""), "--title", CONFIG.get("title") or DEFAULT_TITLE)
    return [out] if rc == 0 else []


def upload_reminder():
    if not UPLOAD:
        return
    print("\nIf your team keeps a shared copy of the data folder, upload these to it:")
    for p in UPLOAD:
        print(f"  {os.path.relpath(p, W.base)}")
    print("  the files in master (they changed if anyone new was added)")
    print("  sessions.csv and programs.json")
    print("Then delete the raw Zoom file you downloaded.")


def finish(paths):
    upload_reminder()
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        return
    print("\nDone. Files:")
    for p in paths:
        print(f"  {os.path.relpath(p, W.base)}")
    if yes("Open them now?"):
        for p in paths:
            open_file(p)


def flow_new_file():
    if not os.path.exists(W.people) and not yes(
            "No people registry was found in your data folder, so everyone will be treated as new. "
            "If your team already has one, stop and use 'Add existing files' first. "
            "If this is your first file ever, that is expected. Continue?", False):
        sys.exit("Stopped.")
    source = None
    while not source:
        source = pick("file", "Choose the new Zoom file")
        if not source:
            sys.exit("No file chosen.")
        if not (os.path.isfile(source) and source.lower().endswith(".csv")):
            print("  That is not a .csv file that exists. Try again.")
            source = None
    prog = pick_program(allow_new=True)
    prepare_cleanup(prog)
    conv_dir, date = bring_in_file(prog, source)
    cleanup = build_cleanup(prog, conv_dir)
    review_loop(prog, cleanup)
    refresh_registry(prog)
    ensure_session_info(prog, date)
    paths = build_pages(prog, date, pick_page_kind())
    if yes("\nRebuild the aggregate dashboard too?", False):
        paths += build_aggregate()
    finish(paths)


def flow_existing():
    prog = pick_program()
    final = final_path(prog)
    if not os.path.exists(final):
        sys.exit(f"No data for {prog['name']} yet. Add a Zoom file first.")
    dates = sorted(pd.read_excel(final, sheet_name="sessions_summary", dtype=str)["session_date"], reverse=True)
    shown = dates[:12]
    idx = choose("Which session?", shown + (["A different date"] if len(dates) > len(shown) else []))
    if idx < len(shown):
        date = shown[idx]
    else:
        date = ask("Session date (YYYY-MM-DD)")
        if date not in dates:
            sys.exit(f"{date} is not a session for {prog['name']}.")
    ensure_session_info(prog, date)
    finish(build_pages(prog, date, pick_page_kind()))


def flow_import():
    kind = choose("What do you want to add?", ["People registry files", "Converted Zoom files for a program"])
    import_registry() if kind == 0 else import_converted()


def flow_workspace():
    print(f"\nYour data folder is:\n  {W.base}")
    if yes("Open it?"):
        open_file(W.base)
    if yes("Switch to a different data folder?", False):
        open_workspace(choose_workspace())
        save_settings()
        print(f"Now using: {W.base}")


def rename_program():
    progs = all_programs()
    prog = progs[choose("Rename which program?", [p["name"] + (" (hidden)" if p.get("hidden") else "") for p in progs])]
    old = prog["name"]
    new = ask_program_name(old, skip=prog)
    if new == old:
        return
    rows, header = read_sessions()
    moved = 0
    for r in rows:
        if r.get("program", "").strip().lower() == old.lower():
            r["program"] = new
            moved += 1
    write_sessions(rows, header)
    prog["name"] = new
    save_config()
    print(f"Renamed {old} to {new}. Updated {moved} row(s) in sessions.csv. Its files did not move.")
    print("Rebuild its pages to show the new name.")


def set_hidden(hide):
    progs = [p for p in all_programs() if bool(p.get("hidden")) != hide]
    if not progs:
        print("No programs to " + ("hide." if hide else "unhide."))
        return
    prog = progs[choose("Which program?", [p["name"] for p in progs])]
    prog["hidden"] = hide
    save_config()
    if hide:
        print(f"{prog['name']} is hidden from the menus and the overview. Its data and pages were not touched.")
    else:
        print(f"{prog['name']} is back in the menus.")


def edit_program_settings():
    progs = all_programs()
    prog = progs[choose("Which program?", [p["name"] for p in progs])]
    prog["topics"] = yes("Does each session have a topic?", prog["topics"])
    prog["presenters"] = yes("Does each session have presenters?", prog["presenters"])
    save_config()
    print("Saved.")


def edit_titles():
    CONFIG["dept_name"] = ask("Department or unit name", CONFIG.get("dept_name", ""))
    CONFIG["title"] = ask("Overview dashboard title", CONFIG.get("title") or DEFAULT_TITLE)
    save_config()
    print("Saved. Rebuild pages to show the change.")


def flow_manage():
    while True:
        print("\nPrograms:")
        for p in all_programs():
            extras = [x for x, on in (("topics", p["topics"]), ("presenters", p["presenters"]),
                                      ("hidden", p.get("hidden"))) if on]
            print(f"  {p['name']}  [folder: {p['folder']}{'; ' + ', '.join(extras) if extras else ''}]")
        actions = [("Add a program", add_program), ("Rename a program", rename_program),
                   ("Change whether a program has topics or presenters", edit_program_settings),
                   ("Hide a program", lambda: set_hidden(True)), ("Unhide a program", lambda: set_hidden(False)),
                   ("Change the department name or dashboard title", edit_titles), ("Done", None)]
        action = actions[choose("What do you want to change?", [a for a, _ in actions])][1]
        if action is None:
            return
        action()


def main():
    os.chdir(ROOT)
    load_workspace()
    choice = choose("What do you want to do?", [
        "One session dashboard, from a NEW Zoom file",
        "One session dashboard, from data I already have",
        "The aggregate dashboard (all programs)",
        "Manage programs and page titles",
        "Add existing files (people registry or converted Zoom files)",
        "Show or change my data folder",
    ])
    [flow_new_file, flow_existing, lambda: finish(build_aggregate()), flow_manage, flow_import,
     flow_workspace][choice]()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nStopped.")