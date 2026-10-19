#!/usr/bin/env python3
"""
Generates HTML session page(s) for a program.

By default, builds every session. Pass --session-date to build just one
(e.g. after fixing that session's topic) without regenerating everything.

Topics, presenters and meeting length come from the data folder's sessions.csv
(columns: program, session_date, topic, presenter, length_minutes). run.py adds
a row for each new session. If a built session has no topic, a notice is printed
after the build.

Usage:
    python3 generate_session_pages.py FINAL_WORKBOOK PROGRAM_NAME --out-dir reports/data_workshop \\
        --people-db master/master_people_db.csv --dept master/master_dept_to_parent.csv \\
        --topics sessions.csv

    python3 generate_session_pages.py FINAL_WORKBOOK PROGRAM_NAME --out-dir reports/data_workshop \\
        --people-db master/master_people_db.csv --dept master/master_dept_to_parent.csv \\
        --topics sessions.csv --session-date 2026-08-20
"""

import argparse
import os
import sys

from session_stats import load_program_data, compute_session_stats
from render_session_page import render_session_page


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("final_workbook")
    parser.add_argument("program_name", help='Must match the "program" column in sessions.csv, e.g. "Data Workshop"')
    parser.add_argument("--people-db", required=True)
    parser.add_argument("--dept", required=True)
    parser.add_argument("--topics", default=None, help="Path to sessions.csv (topics, presenters, meeting length)")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--dept-name", default="", help="Shown in the page footer")
    parser.add_argument("--no-topics", action="store_true",
                        help="Program has no topics: leave the topic off the page and skip the missing-topic note")
    parser.add_argument("--session-date", default=None,
                         help="Build only this one session (YYYY-MM-DD) instead of the whole series")
    args = parser.parse_args()

    attendance_log, sessions_summary, people, dept, topics = load_program_data(
        args.final_workbook, args.people_db, args.dept, args.topics, program=args.program_name
    )

    all_dates = sorted(sessions_summary["session_date"].tolist())
    total_in_series = len(all_dates)

    if args.session_date:
        if args.session_date not in all_dates:
            sys.exit(f"ERROR: {args.session_date} is not a session in {args.final_workbook}")
        dates_to_build = [args.session_date]
    else:
        dates_to_build = all_dates

    os.makedirs(args.out_dir, exist_ok=True)

    written = []
    missing_topics = []
    for date in dates_to_build:
        session_number = all_dates.index(date) + 1  # position within the FULL series, even when building just one
        stats = compute_session_stats(date, attendance_log, sessions_summary, people, dept, topics)
        if args.no_topics:
            stats["topic"] = ""
        if args.topics and not args.no_topics and not stats["topic"]:
            missing_topics.append(date)
        html = render_session_page(stats, args.program_name, session_number=session_number,
                                   total_in_series=total_in_series, dept_name=args.dept_name)
        out_path = os.path.join(args.out_dir, f"session_{date}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        written.append(out_path)

    print(f"Wrote {len(written)} session page(s) to {args.out_dir}/")
    for path in written:
        print(f"  {path}")

    if missing_topics:
        print(f"\nNOTE: {len(missing_topics)} session(s) have no topic row for '{args.program_name}' in {args.topics}:")
        for date in missing_topics:
            print(f"  {date}")


if __name__ == "__main__":
    main()