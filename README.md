# Zoom Attendance Dashboards

Turns Zoom attendance exports into dashboard pages for each session, plus one overview of all your programs. Built at the University of Illinois Urbana-Champaign for any campus unit that runs recurring Zoom sessions. It runs on a Mac.

You decide what your programs are. The tool asks for them the first time you run it, and you can add, rename or hide programs later.

Attendee data never goes in this repository. The repo holds code only. Your data lives in a separate **data folder** that you choose, and each department keeps its own.

## How it works (one minute version)

1. You download an attendance file from Zoom.
2. `run.py` converts it into one standard shape and files it with that program's other sessions.
3. It rebuilds that program's data from all of its sessions. People it already knows are matched automatically, using your people registry. You only deal with people it has not seen before.
4. It builds the dashboard page you asked for.

The people registry is a few files that remember who each person is (their ID, department and status), so nobody is resolved twice. It starts empty and fills in as you go.

## What you need

- A Mac
- Python 3. To check, open Terminal and run `python3 --version`. If it says "command not found", install it from [python.org](https://www.python.org/downloads/).
- Excel, to fix the few people the tool cannot match on its own
- Zoom access to your meetings' attendance reports

You do not need Git.

## One-time setup

### 1. Get the code

On this repo's GitHub page, click **Code**, then **Download ZIP**. Unzip it and put the folder somewhere permanent, such as your Documents folder.

### 2. Start the program

Double-click `Start.command`. A Terminal window opens and the program runs there. The first time, it installs what it needs, which takes a minute and needs internet.

If macOS says it cannot open the file:

- **Older macOS:** right-click `Start.command`, choose **Open**, then **Open** again.
- **macOS Sequoia and later:** click **Done**, open **System Settings → Privacy & Security**, scroll down to the message about `Start.command`, and click **Open Anyway**.

**The terminal way:** open Terminal, go into the code folder, and run the launcher:

```
cd ~/Documents/zoom-attendance-template
./Start.command
```

If it says `permission denied`, run `chmod +x Start.command` once, then try again.

Or do each step yourself. The first three lines are only needed the first time:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

After that, `source .venv/bin/activate` and then `python3 run.py` is enough.

### 3. Choose your data folder

A window asks you to choose your data folder. If you do not see it, it may be behind Terminal. Check the Dock or press Cmd+Tab.

- **First time for your department:** make a new, empty folder (for example `Zoom Attendance Data` in Documents) and choose it.
- **Your team already has one:** choose that folder.

The data folder must not be inside the code folder, so updating the code never touches your data.

### 4. Set up your department

For a new data folder, the program asks:

- your department or unit name, shown on the pages
- a title for the overview dashboard. Press Enter to keep the suggested one, or type your own.
- your programs. For each one:
  - **name**, as it should appear on the pages
  - **short folder name**, used for its files (it suggests one)
  - whether sessions have a **topic**
  - whether sessions have **presenters**

These are saved in `programs.json` in your data folder. You can change them later with **Manage programs and page titles**.

The data folder ends up looking like this:

```
Zoom Attendance Data/
    programs.json   your department name, titles and programs
    sessions.csv    topic, presenters and meeting length for each session
    converted/      converted Zoom files, one folder per program
    master/         the people registry and the department-to-college list
    workbooks/      the Excel files it builds
    reports/        the dashboard pages
```

These files contain real names and emails, so do not email them or post them anywhere public.

It remembers which data folder you chose. Replacing the code with a newer download does not change that.

## Which Zoom file to download

The tool accepts these Zoom exports and converts each one into the same shape:

- the **participants report** for a meeting (best: has real join and leave times)
- the **usage report**
- the **meeting list details** file

Download it as a CSV.

<!-- Add step-by-step Zoom download instructions here. -->

## Adding a new Zoom file

1. Download the attendance file from Zoom. Save it anywhere.
2. Start the program and choose **1) One session dashboard, from a NEW Zoom file**.
3. A file picker opens. Click the file.
4. Choose the program, or **Add a new program**.
5. The program converts the file, rebuilds the program's data, and tells you what needs your attention in Excel:
   - **Nothing:** everyone was matched. It carries on by itself.
   - **People with no person_id:** attendees with no email that the program could not match by name. Open the workbook when it offers.
     - If you recognize the person, type their existing ID from the `people_db` sheet into the `person_id` column.
     - If they are new, add a row to the `people_db` sheet with a new, unused ID (one higher than the largest existing ID), their name, and their department and status if you know them. Then type that ID in the `person_id` column.
   - **New people added to people_db:** fill in their department and status.
   - Save the workbook, close Excel, and press Enter.
6. It asks for whatever this session is missing:
   - the topic and presenters, if the program uses them (separate several presenters with commas)
   - **how long the meeting was, in minutes.** It suggests the last length you used, so usually you just press Enter.
7. Choose which page to build: public, internal, or both.
8. Open the page when it offers.
9. Delete the raw file you downloaded from Zoom.

The meeting length decides what counts as staying for most of a session. For a 60 minute meeting, that is 50 minutes or more, and under 25 minutes is a brief check-in. Other lengths scale the same way, so for a 90 minute meeting it is 75 minutes and 38 minutes.

Pages are saved in `reports/` inside the data folder:

| Page | Where |
| --- | --- |
| Public session page | `reports/<folder name>/session_YYYY-MM-DD.html` |
| Internal session page (has names) | `reports/internal/<folder name>/session_YYYY-MM-DD.html` |
| Overview of all programs | `reports/aggregate.html` |

Never publish or share anything under `reports/internal`. It lists attendee names.

### One person runs it at a time

The people registry changes every time someone runs the program, and new people get the next ID in order. If two people each add new people from their own copies, they will give the same ID to different people. So only one person in your department should run the program.

If your team keeps a shared copy of the data folder (on Teams, Box or similar), download a fresh copy right before you start and upload your changes right after. The program lists what changed at the end.

## Other menu choices

- **2) One session dashboard, from data I already have:** pick the program, the session and the page type.
- **3) The aggregate dashboard:** an overview of every program that has data. Hidden programs are left out.
- **4) Manage programs and page titles:**
  - add a program
  - rename a program. Only the name on the pages changes. Its files stay where they are, and its topics are kept. Rebuild its pages afterward.
  - change whether a program has topics or presenters
  - hide a program you no longer run. It disappears from the menus and the overview, but its data and pages are kept. You can unhide it.
  - change the department name or dashboard title
- **5) Add existing files:** add registry files or converted Zoom files with a file picker.
- **6) Show or change my data folder:** see where your files are, open the folder, or switch to a different one.

## Departments and colleges

The pages group attendees by college or unit, using `master/master_dept_to_parent.csv`. Each row is one department and the college or unit it belongs to. A new data folder gets a starter copy covering UIUC departments. If someone's department is not in the list, the pages show the department itself. Add rows to the file when you see that.

## Updating the program

Download a new ZIP from GitHub and replace the code folder. Your data folder is separate, so nothing else needs to move. Only update when there is a change you need.

## If something stops

| What you see | What it means | What to do |
| --- | --- | --- |
| A converted file for this date already exists | That session is already in the data | Say no to leave it alone, or yes to replace it. The old one is moved to `converted/_replaced`, not deleted. |
| `...cleanup.xlsx is newer than the last final workbook` | An earlier run was left unfinished and may hold fixes | Say no. Finish that run first, or move the file out of `workbooks/`. |
| QC report with unresolved rows, duplicate IDs or unknown IDs | Something in the workbook needs fixing | Fix it in Excel, save, and let the program compile again. |
| Stopped before updating the registry or building pages | You chose not to fix the problems this time | Nothing was saved. Run it again with the same Zoom file, say yes when it asks to replace that date's file, and fix the rows when Excel opens. |
| QC notes about departments with no parent unit or new aliases | Information only | The run continues. Add the department to `master_dept_to_parent.csv` when you can. |
| Registry refresh refused | The new workbook is missing people who are already in the registry, usually because files are missing from `converted` | Do not force it. Check that your converted folders are complete, then run again. |
| No people registry was found | Normal before your first file. Otherwise, files are missing from `master` | For your first file, continue. Otherwise use **Add existing files**. |
| sessions.csv is open in another program | Excel has the file open | Close it in Excel and press Enter. |
| The conversion failed | The file has a shape the converter does not recognize | Check it is one of the Zoom files listed above. If it is, report it (see below). |

Notes on file types:

- The usage report has no real join and leave times, so the program approximates them from each person's total time. It says so when it converts one.
- Time in session is always accurate. Anything that depends on exact join and leave times is not.

## Problems and questions

Open an issue on this repo's **Issues** tab. Describe what you did and copy the message the program showed. Never attach data files or paste attendee names.

## What is in the repo

```
Start.command                       double-click launcher
run.py                              the guided program
tools/                              the scripts run.py uses
config/master_dept_to_parent.csv    starter department-to-college list
requirements.txt                    the Python packages it needs
```

Attendee data is never stored here. The `.gitignore` blocks spreadsheets and CSV files (other than `config/`) as a safeguard.