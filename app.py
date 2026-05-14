import sqlite3
import os
from datetime import datetime
from flask import Flask, request, jsonify, g, send_from_directory

app = Flask(__name__, static_folder='static', static_url_path='')
DATABASE = os.path.join(os.path.dirname(__file__), 'data', 'calorie.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            meal_type TEXT NOT NULL,
            food_name TEXT NOT NULL,
            amount REAL NOT NULL,
            unit TEXT NOT NULL,
            kcal INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS custom_foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cal REAL NOT NULL,
            cat TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )''')
        db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('goal', '2000')")
        db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('created_at', ?)", (datetime.now().isoformat(),))
        db.commit()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/records', methods=['GET'])
def get_records():
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    db = get_db()
    rows = db.execute(
        'SELECT * FROM records WHERE date = ? ORDER BY created_at ASC', (date,)
    ).fetchall()
    result = {'早餐': [], '午餐': [], '晚餐': [], '加餐': []}
    for r in rows:
        mt = r['meal_type']
        if mt not in result:
            result[mt] = []
        result[mt].append({
            'id': r['id'],
            'name': r['food_name'],
            'amount': r['amount'],
            'unit': r['unit'],
            'kcal': r['kcal'],
            'time': r['created_at'][:16]
        })
    return jsonify(result)

@app.route('/api/records', methods=['POST'])
def add_record():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效请求'}), 400
    db = get_db()
    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    db.execute(
        'INSERT INTO records (date, meal_type, food_name, amount, unit, kcal, created_at) VALUES (?,?,?,?,?,?,?)',
        (data['date'], data['mealType'], data['name'], data['amount'], data['unit'], data['kcal'], now)
    )
    db.commit()
    return jsonify({'ok': True, 'id': db.execute('SELECT last_insert_rowid()').fetchone()[0]})

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    db = get_db()
    db.execute('DELETE FROM records WHERE id = ?', (record_id,))
    db.commit()
    return jsonify({'ok': True})

@app.route('/api/goal', methods=['GET'])
def get_goal():
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key='goal'").fetchone()
    return jsonify({'goal': int(row['value']) if row else 2000})

@app.route('/api/goal', methods=['PUT'])
def update_goal():
    data = request.get_json()
    val = int(data.get('goal', 2000))
    if val < 500:
        return jsonify({'error': '目标不能低于500'}), 400
    db = get_db()
    db.execute("UPDATE settings SET value = ? WHERE key='goal'", (str(val),))
    db.commit()
    return jsonify({'ok': True, 'goal': val})

@app.route('/api/custom-foods', methods=['GET'])
def get_custom_foods():
    db = get_db()
    rows = db.execute('SELECT * FROM custom_foods').fetchall()
    return jsonify([{'name': r['name'], 'cal': r['cal'], 'cat': r['cat']} for r in rows])

@app.route('/api/custom-foods', methods=['POST'])
def add_custom_food():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('cal'):
        return jsonify({'error': '请填写名称和热量'}), 400
    db = get_db()
    db.execute('INSERT INTO custom_foods (name, cal, cat) VALUES (?,?,?)',
               (data['name'], data['cal'], data.get('cat', '自定义')))
    db.commit()
    return jsonify({'ok': True})

if __name__ == '__main__':
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
