@echo off
cd /d %~dp0
python -c "import sqlite3; conn=sqlite3.connect('./data/todos.db'); conn.execute('UPDATE reminder_config SET spreadsheet_token=NULL, spreadsheet_url=NULL, spreadsheet_sheet_id=NULL'); conn.commit(); conn.close(); print('[OK] spreadsheet binding cleared')"
python app.py
