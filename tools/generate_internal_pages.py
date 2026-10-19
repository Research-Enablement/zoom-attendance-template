#!/usr/bin/env python3
"""
Builds INTERNAL roster pages (with names). The output folder must be named
'internal' somewhere in its path so these never land next to public pages.

Usage:
    python3 tools/generate_internal_pages.py FINAL_WORKBOOK PROGRAM_NAME \
        --people-db master/master_people_db.csv --dept master/master_dept_to_parent.csv \
        --topics sessions.csv --out-dir reports/internal/data_workshop [--session-date YYYY-MM-DD]
"""

import argparse
import os
import sys

from session_stats import load_program_data, compute_session_stats
from render_internal_page import build_roster, render_internal_page


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("final_workbook")
    parser.add_argument("program_name")
    parser.add_argument("--people-db", required=True)
    parser.add_argument("--dept", required=True)
    parser.add_argument("--topics", default=None)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--dept-name", default="", help="Shown in the page footer")
    parser.add_argument("--no-topics", action="store_true",
                        help="Program has no topics: leave the topic off the page and skip the missing-topic note")
    parser.add_argument("--session-date", default=None)
    args = parser.parse_args()

    if "internal" not in os.path.normpath(args.out_dir).split(os.sep):
        sys.exit("ERROR: --out-dir must include an 'internal' folder, e.g. reports/internal/data_workshop")

    attendance_log, sessions_summary, people, dept, topics = load_program_data(
        args.final_workbook, args.people_db, args.dept, args.topics, program=args.program_name)

    all_dates = sorted(sessions_summary["session_date"].tolist())
    if args.session_date:
        if args.session_date not in all_dates:
            sys.exit(f"ERROR: {args.session_date} is not a session in {args.final_workbook}")
        dates = [args.session_date]
    else:
        dates = all_dates

    os.makedirs(args.out_dir, exist_ok=True)
    for date in dates:
        stats = compute_session_stats(date, attendance_log, sessions_summary, people, dept, topics)
        if args.no_topics:
            stats["topic"] = ""
        roster = build_roster(date, attendance_log, people, dept)
        if len(roster) != stats["total_attendees"]:
            print(f"WARNING {date}: roster has {len(roster)} rows but sessions_summary says {stats['total_attendees']}")
        page = render_internal_page(stats, roster, args.program_name,
                                    session_number=all_dates.index(date) + 1, total_in_series=len(all_dates),
                                    dept_name=args.dept_name)
        path = os.path.join(args.out_dir, f"session_{date}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"  {path}")
    print(f"Wrote {len(dates)} internal page(s). Do not publish this folder.")


if __name__ == "__main__":
    main()