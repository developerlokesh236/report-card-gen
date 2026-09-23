# Report Card Generator

Web app jo subjects ke naam aur marks se report card banata hai: total, percentage, grade aur pass/fail ke saath.

## Features
- Subjects ki sankhya aur naam/marks dynamic form se daalna
- Har subject ka percent, grade, pass/fail (pass marks: 33%)
- Overall total, percentage aur final result
- Create, view, edit, delete
- Report card ko HTML file ke roop mein download ya print/PDF karna

## Tech stack
- Frontend: HTML, CSS, JavaScript
- Backend: Python, Flask
- Database: SQLite (SQL queries, Python ka built-in sqlite3)

## Run karne ke steps
```bash
pip install -r requirements.txt
python app.py
```
Phir browser mein kholein: http://localhost:5000

## Folder structure
```
├── app.py             # backend + SQL queries + REST API
├── requirements.txt
├── data/              # SQLite database file yahan ban jati hai
└── public/
    ├── index.html
    ├── style.css
    └── script.js
```

## API
| Method | Route | Kaam |
|--------|-------|------|
| GET | /api/reports | Saare reports |
| POST | /api/reports | Naya report |
| PUT | /api/reports/:id | Report edit |
| DELETE | /api/reports/:id | Report delete |
| GET | /api/reports/:id/view | Report card dekhna |
| GET | /api/reports/:id/download | Report card download |
