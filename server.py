from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
curr_user = {}

# Configuration
app.config['UPLOAD_FOLDER'] = 'assets/images'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database initialization
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firstname TEXT NOT NULL,
            lastname TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            avatar_url TEXT DEFAULT 'assets/avatars/avatar1.png',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT NOT NULL,
            image_url TEXT NOT NULL,
            status TEXT DEFAULT 'available',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
    ''')
    
    # Trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item1_id INTEGER NOT NULL,
            item2_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item1_id) REFERENCES items (id),
            FOREIGN KEY (item2_id) REFERENCES items (id),
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

BASE_URL = "https://zhmbn1l9-5000.inc1.devtunnels.ms/"  

@app.before_request
def log_request_info():
    print(f"Request from: {request.remote_addr}")
    print(f"Method: {request.method}")
    print(f"Path: {request.path}")


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Database helper functions
def get_user_by_email(email):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'firstname': user[1],
            'lastname': user[2],
            'email': user[3],
            'password': user[4],
            'created_at': user[5],
            'avatar_url': user[6]
        }
    return None

def get_user_by_id(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'firstname': user[1],
            'lastname': user[2],
            'email': user[3],
            'password': user[4],
            'created_at': user[5],
            'avatar_url': user[6]
        }
    return None

@app.route('/api/get-user', methods=['GET'])
def get_current_user():
    global curr_user
    if not curr_user:
        return jsonify({'error': 'User not logged in'}), 401

    try:
        # Get the complete user data from database
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, firstname, lastname, email, avatar_url, created_at 
            FROM users WHERE id = ?
        ''', (curr_user['id'],))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            user_data = {
                'id': user[0],
                'firstname': user[1],
                'lastname': user[2],
                'email': user[3],
                'avatar_url': f"{BASE_URL}/{user[4]}" if user[4].startswith('assets/') else user[4],
                'created_at': user[5]
            }
            return jsonify(user_data), 200
        else:
            return jsonify({'error': 'User not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# Routes
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        firstname = data.get('firstname')
        lastname = data.get('lastname')
        email = data.get('email')
        password = data.get('password')
        
        # Validation
        if not all([firstname, lastname, email, password]):
            return jsonify({'message': 'All fields are required'}), 400
        
        if len(password) < 6:
            return jsonify({'message': 'Password must be at least 6 characters'}), 400
        
        # Check if user already exists
        if get_user_by_email(email):
            return jsonify({'message': 'User already exists'}), 409
        
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (firstname, lastname, email, password)
            VALUES (?, ?, ?, ?)
        ''', (firstname, lastname, email, password))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'User created successfully'}), 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    global curr_user
    try:
        data = request.get_json()
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'message': 'Email and password are required'}), 400
        
        # Get user from database
        user = get_user_by_email(email)
        
        if not user:
            return jsonify({'message': 'Invalid credentials'}), 401
        
        # Verify password
        if user['password'] != password:
            return jsonify({'message': 'Invalid credentials'}), 401
        
        curr_user = user
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'firstname': user['firstname'],
                'lastname': user['lastname'],
                'email': user['email'],
                'avatar_url': user['avatar_url']
            }
        }), 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    global curr_user
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({'message': 'Email is required'}), 400
    
    user = get_user_by_email(email)
    curr_user = user
    if not user:
        return jsonify({'message': 'If the email exists, a reset link will be sent'}), 200
    
    return jsonify({'message': 'If the email exists, a reset link will be sent'}), 200

@app.route('/api/change-password', methods=['POST'])
def change_pwd():
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        global curr_user

        data = request.get_json()
        password = data.get('password')

        if not password or len(password) < 6:
            return jsonify({'message': 'Password must be at least 6 characters'}), 400

        email = curr_user.get('email')
        print(email)
        cursor.execute(
            'UPDATE users SET password = ? WHERE email = ?',
            (password, email)
        )

        conn.commit()
        return jsonify({'message': 'Password updated successfully'}), 200

    except Exception as e:
        return jsonify({'message': str(e)}), 500

    finally:
        conn.close()

# Add these imports at the top if not already present
import json
from datetime import datetime

# Chat messages table creation (add to init_db function)
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # ... existing tables ...
    
    # Chat messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id),
            FOREIGN KEY (trade_id) REFERENCES trades (id)
        )
    ''')
    
    # Trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item1_id INTEGER NOT NULL,
            item2_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item1_id) REFERENCES items (id),
            FOREIGN KEY (item2_id) REFERENCES items (id),
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Chat endpoints
@app.route('/api/chat/send', methods=['POST'])
def send_message():
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        receiver_id = data.get('receiver_id')
        message = data.get('message')
        if not all([trade_id, receiver_id, message]):
            return jsonify({'error': 'Missing required fields: trade_id, receiver_id, message'}), 400
        
        # Validate that the trade exists and user is part of it
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sender_id, receiver_id FROM trades WHERE id = ?
        ''', (trade_id,))
        
        trade = cursor.fetchone()
        
        if not trade:
            conn.close()
            return jsonify({'error': 'Trade not found'}), 404
        
        sender_id, trade_receiver_id = trade
        
        # Check if current user is part of this trade
        if curr_user['id'] not in [sender_id, trade_receiver_id]:
            conn.close()
            return jsonify({'error': 'Not authorized to send messages in this trade'}), 403
        print(trade_receiver_id)
        # Check if receiver_id is valid for this trade
        if int(receiver_id) not in [sender_id, trade_receiver_id]:
            conn.close()
            return jsonify({'error': 'Invalid receiver for this trade'}), 400
        
        # Insert message into database
        cursor.execute('''
            INSERT INTO chat_messages (trade_id, sender_id, receiver_id, message)
            VALUES (?, ?, ?, ?)
        ''', (trade_id, curr_user['id'], receiver_id, message.strip()))
        
        conn.commit()
        
        # Get the inserted message with additional details
        cursor.execute('''
            SELECT cm.*, u.firstname, u.lastname, u.avatar_url
            FROM chat_messages cm
            JOIN users u ON cm.sender_id = u.id
            WHERE cm.id = ?
        ''', (cursor.lastrowid,))
        
        message_data = cursor.fetchone()
        conn.close()
        
        if message_data:
            response_data = {
                'id': message_data[0],
                'trade_id': message_data[1],
                'sender_id': message_data[2],
                'receiver_id': message_data[3],
                'message': message_data[4],
                'timestamp': message_data[5],
                'is_read': bool(message_data[6]),
                'sender_name': f"{message_data[7]} {message_data[8]}",
                'sender_avatar': f"{BASE_URL}/{message_data[9]}" if message_data[9].startswith('assets/') else message_data[9]
            }
            
            return jsonify({'success': True, 'message': 'Message sent', 'data': response_data}), 200
        else:
            return jsonify({'error': 'Failed to retrieve sent message'}), 500
        
    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/chat/messages/<int:trade_id>', methods=['GET'])
def get_messages(trade_id):
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        # Validate that the user is part of this trade
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sender_id, receiver_id FROM trades WHERE id = ?
        ''', (trade_id,))
        
        trade = cursor.fetchone()
        
        if not trade:
            conn.close()
            return jsonify({'error': 'Trade not found'}), 404
        
        sender_id, receiver_id = trade
        
        if curr_user['id'] not in [sender_id, receiver_id]:
            conn.close()
            return jsonify({'error': 'Not authorized to view messages for this trade'}), 403
        
        # Get all messages for this trade
        cursor.execute('''
            SELECT cm.*, u.firstname, u.lastname, u.avatar_url
            FROM chat_messages cm
            JOIN users u ON cm.sender_id = u.id
            WHERE cm.trade_id = ?
            ORDER BY cm.timestamp ASC
        ''', (trade_id,))
        
        messages = cursor.fetchall()
        conn.close()
        
        messages_list = []
        for msg in messages:
            messages_list.append({
                'id': msg[0],
                'trade_id': msg[1],
                'sender_id': msg[2],
                'receiver_id': msg[3],
                'message': msg[4],
                'timestamp': msg[5],
                'is_read': bool(msg[6]),
                'sender_name': f"{msg[7]} {msg[8]}",
                'sender_avatar': f"{BASE_URL}/{msg[9]}" if msg[9].startswith('assets/') else msg[9]
            })
        
        return jsonify(messages_list), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_item_by_id(item_id):
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

@app.route('/api/trade/check', methods=['POST'])
def check_existing_trade():
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        requested_item_id = data.get('requested_item_id')
        receiver_id = data.get('receiver_id')
        print(receiver_id,requested_item_id)
        if not requested_item_id or not receiver_id:
            return jsonify({'error': 'Missing required fields'}), 400
        print(curr_user)
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
                # ✅ Check if a trade exists between these two users involving this requested item
        cursor.execute('''
            SELECT id, item1_id, item2_id, sender_id, receiver_id, status
            FROM trades
            WHERE (sender_id = ? OR receiver_id = ?)
            AND (item1_id = ? OR item2_id = ?)
            AND status IN ('pending', 'accepted')
        ''', (curr_user['id'], curr_user['id'], requested_item_id, requested_item_id))

        trade = cursor.fetchone()
        conn.close()
        print(trade)
        if trade:
            offered_item = get_item_by_id(trade[1])  # trade[1] = item1_id
            requested_item = get_item_by_id(trade[2])  # trade[2] = item2_id (optional)

            return jsonify({
                'exists': "True",
                'trade_id': str(trade[0]),
                'status': trade[5],
                'item1_id': str(trade[1]),
                'item2_id': str(trade[2]),
                'offered_item': offered_item,        # 👈 Full dict from items table
                'requested_item': requested_item     # 👈 optional, but useful
            }), 200
        else:
            return jsonify({'exists': False}), 200

    except Exception as e:
        print(str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/api/trade/create', methods=['POST'])
def create_trade():
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        data = request.get_json()
        offered_item_id = data.get('offered_item_id')
        requested_item_id = data.get('requested_item_id')
        receiver_id = data.get('receiver_id')
        print(offered_item_id,requested_item_id)
        
        if not all([offered_item_id, requested_item_id, receiver_id]):
            return jsonify({'error': 'Missing required fields: offered_item_id, requested_item_id, receiver_id'}), 400
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Verify items exist and are available
        cursor.execute('SELECT id, user_id, status FROM items WHERE id IN (?, ?)', 
                      (offered_item_id, requested_item_id))
        items = cursor.fetchall()
        if len(items) != 2:
            conn.close()
            return jsonify({'error': 'One or more items not found'}), 404
        
        offered_item = next((item for item in items if item[1] == curr_user['id']), None)
        requested_item = next((item for item in items if item[1] != curr_user['id']), None)

        # Validate both items
        if not offered_item or not requested_item:
            conn.close()
            return jsonify({'error': 'Invalid trade items or ownership mismatch'}), 400

        
        # Check if requested item belongs to the receiver
       
        if requested_item[1] != int(receiver_id):
            conn.close()
            return jsonify({'error': 'Requested item does not belong to the specified receiver'}), 400
        
        # Check if items are available
        print(offered_item,requested_item)
        if offered_item[2] != 'available' or requested_item[2] != 'available':
            conn.close()
            return jsonify({'error': 'One or both items are not available for trade'}), 400
        
        # Create new trade
        cursor.execute('''
            INSERT INTO trades (item1_id, item2_id, sender_id, receiver_id)
            VALUES (?, ?, ?, ?)
        ''', (offered_item_id, requested_item_id, curr_user['id'], receiver_id))
        
        trade_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'trade_id': trade_id,
            'message': 'Trade created successfully'
        }), 200
        
    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/trade/<int:trade_id>/status', methods=['POST'])
def update_trade_status(trade_id):
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        data = request.get_json()
        status = data.get('status')
        
        valid_statuses = ['accepted', 'declined', 'pending', 'completed', 'cancelled']
        if status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Check if trade exists and user has permission to update it
        cursor.execute('SELECT sender_id, receiver_id, status FROM trades WHERE id = ?', (trade_id,))
        trade = cursor.fetchone()
        
        if not trade:
            conn.close()
            return jsonify({'error': 'Trade not found'}), 404
        
        sender_id, receiver_id, current_status = trade
        
        # Check if current user is part of this trade
        if curr_user['id'] not in [sender_id, receiver_id]:
            conn.close()
            return jsonify({'error': 'Not authorized to update this trade'}), 403
        
        # Only receiver can accept/decline, sender can cancel
        if status in ['accepted', 'declined'] and curr_user['id'] != receiver_id:
            conn.close()
            return jsonify({'error': 'Only the receiver can accept or decline a trade'}), 403
        
        if status == 'cancelled' and curr_user['id'] != sender_id:
            conn.close()
            return jsonify({'error': 'Only the sender can cancel a trade'}), 403
        
        # Update trade status
        cursor.execute('UPDATE trades SET status = ? WHERE id = ?', (status, trade_id))
        
        # If accepted, mark items as traded
        if status == 'accepted':
            cursor.execute('SELECT item1_id, item2_id FROM trades WHERE id = ?', (trade_id,))
            trade_items = cursor.fetchone()
            
            if trade_items:
                cursor.execute('UPDATE items SET status = "traded" WHERE id IN (?, ?)', 
                              (trade_items[0], trade_items[1]))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Trade {status}',
            'status': status
        }), 200
        
    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/trade/<int:trade_id>', methods=['GET'])
def get_trade_details(trade_id):
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.id, t.status, t.created_at,
                   i1.id, i1.title, i1.image_url, i1.description, i1.category, i1.price, i1.imei,
                   i2.id, i2.title, i2.image_url, i2.description, i2.category, i2.price, i2.imei,
                   u1.id, u1.firstname, u1.lastname, u1.email, u1.avatar_url,
                   u2.id, u2.firstname, u2.lastname, u2.email, u2.avatar_url
            FROM trades t
            JOIN items i1 ON t.item1_id = i1.id
            JOIN items i2 ON t.item2_id = i2.id
            JOIN users u1 ON t.sender_id = u1.id
            JOIN users u2 ON t.receiver_id = u2.id
            WHERE t.id = ?
        ''', (trade_id,))
        
        trade = cursor.fetchone()
        conn.close()
        
        if not trade:
            return jsonify({'error': 'Trade not found'}), 404
        
        # Check if current user is part of this trade
        if curr_user['id'] not in [trade[17], trade[22]]:  # sender_id and receiver_id positions
            return jsonify({'error': 'Not authorized to view this trade'}), 403
        
        trade_data = {
            'id': trade[0],
            'status': trade[1],
            'created_at': trade[2],
            'item1': {
                'id': trade[3],
                'title': trade[4],
                'image_url': f"{BASE_URL}{trade[5]}",
                'description': trade[6],
                'category': trade[7],
                'price': trade[8],
                'imei': trade[9]
            },
            'item2': {
                'id': trade[10],
                'title': trade[11],
                'image_url': f"{BASE_URL}{trade[12]}" ,
                'description': trade[13],
                'category': trade[14],
                'price': trade[15],
                'imei': trade[16]
            },
            'sender': {
                'id': trade[17],
                'name': f"{trade[18]} {trade[19]}",
                'email': trade[20],
                'avatar_url': f"{BASE_URL}{trade[21]}"
            },
            'receiver': {
                'id': trade[22],
                'name': f"{trade[23]} {trade[24]}",
                'email': trade[25],
                'avatar_url': f"{BASE_URL}{trade[26]}"
            }
        }
        
        return jsonify(trade_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades/sent', methods=['GET'])
def get_sent_trades():
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT t.id, t.status, t.created_at,
                   i1.id, i1.title, i1.image_url, i1.description,
                   i2.id, i2.title, i2.image_url, i2.description,
                   u1.id, u1.firstname, u1.lastname, u1.avatar_url,
                   u2.id, u2.firstname, u2.lastname, u2.avatar_url
            FROM trades t
            JOIN items i1 ON t.item1_id = i1.id
            JOIN items i2 ON t.item2_id = i2.id
            JOIN users u1 ON t.sender_id = u1.id
            JOIN users u2 ON t.receiver_id = u2.id
            WHERE t.sender_id = ?
            ORDER BY t.created_at DESC
        ''', (curr_user['id'],))

        trades = cursor.fetchall()
        conn.close()

        result = []
        for tr in trades:
            result.append({
                'id': tr[0],
                'status': tr[1],
                'created_at': tr[2],
                'offered_item': {
                    'id': tr[3],
                    'title': tr[4],
                    'image_url': f"{BASE_URL}/{tr[5]}",
                    'description': tr[6],
                },
                'requested_item': {
                    'id': tr[7],
                    'title': tr[8],
                    'image_url': f"{BASE_URL}/{tr[9]}",
                    'description': tr[10],
                },
                'sender': {
                    'id': tr[11],
                    'name': f"{tr[12]} {tr[13]}",
                    'avatar_url': f"{BASE_URL}/{tr[14]}",
                },
                'receiver': {
                    'id': tr[15],
                    'name': f"{tr[16]} {tr[17]}",
                    'avatar_url': f"{BASE_URL}/{tr[18]}",
                }
            })

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trades/received', methods=['GET'])
def get_received_trades():
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT t.id, t.status, t.created_at,
                   i1.id, i1.title, i1.image_url, i1.description,
                   i2.id, i2.title, i2.image_url, i2.description,
                   u1.id, u1.firstname, u1.lastname, u1.avatar_url,
                   u2.id, u2.firstname, u2.lastname, u2.avatar_url
            FROM trades t
            JOIN items i1 ON t.item1_id = i1.id
            JOIN items i2 ON t.item2_id = i2.id
            JOIN users u1 ON t.sender_id = u1.id
            JOIN users u2 ON t.receiver_id = u2.id
            WHERE t.receiver_id = ?
            ORDER BY t.created_at DESC
        ''', (curr_user['id'],))

        trades = cursor.fetchall()
        conn.close()

        result = []
        for tr in trades:
            result.append({
                'id': tr[0],
                'status': tr[1],
                'created_at': tr[2],
                'offered_item': {
                    'id': tr[3],
                    'title': tr[4],
                    'image_url': f"{BASE_URL}/{tr[5]}",
                    'description': tr[6],
                },
                'requested_item': {
                    'id': tr[7],
                    'title': tr[8],
                    'image_url': f"{BASE_URL}/{tr[9]}",
                    'description': tr[10],
                },
                'sender': {
                    'id': tr[11],
                    'name': f"{tr[12]} {tr[13]}",
                    'avatar_url': f"{BASE_URL}/{tr[14]}",
                },
                'receiver': {
                    'id': tr[15],
                    'name': f"{tr[16]} {tr[17]}",
                    'avatar_url': f"{BASE_URL}/{tr[18]}",
                }
            })

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# Get user's items for trading
@app.route('/api/user/items', methods=['GET'])
def get_user_items_for_trade():
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM items 
            WHERE user_id = ? AND status = 'available'
            ORDER BY created_at DESC
        ''', (curr_user['id'],))
        
        items = cursor.fetchall()
        # cursor.execute('''
        #     sELECT sender_id from trades 
        #     WHERE reciever_id =?
        # ''',(curr_user["id"],))
        # requested_ids = cursor.fetchall()
        conn.close()
        # print(requested_ids)
        items_list = []
        for item in items:
            items_list.append({
                'id': item[0],
                'user_id': item[1],
                'title': item[2],
                'category': item[3],
                'price': item[4],
                'description': item[5],
                'image_url': f"{BASE_URL}/{item[6]}" if item[6].startswith('assets/') else item[6],
                'status': item[7],
                'created_at': item[8]
            })
        
        return jsonify(items_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# Add this route to serve avatar images
@app.route('/assets/avatars/png/<filename>')
def serve_avatar(filename):
    try:
        return send_from_directory('assets/avatars/png', filename)
    except FileNotFoundError:
        # Return a default avatar if the requested one doesn't exist
        return send_from_directory('assets/avatars/png', 'default_avatar.png')
    
# Add this new route to your server.py
@app.route('/api/items/others', methods=['GET'])
def get_others_items():
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        user_id = curr_user['id']
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT items.*, users.firstname, users.lastname, users.avatar_url 
            FROM items 
            JOIN users ON items.user_id = users.id 
            WHERE items.status = 'available' AND items.user_id != ?
            ORDER BY items.created_at DESC
        ''', (user_id,))
        items = cursor.fetchall()
        conn.close()
        
        items_list = []
        for item in items:
            items_list.append({
                'id': item[0],
                'user_id': item[1],
                'title': item[2],
                'category': item[3],
                'price': item[4],
                'description': item[5],
                'image_url': item[6],
                'status': item[7],
                'created_at': item[8],
                'user_firstname': item[9],
                'user_lastname': item[10],
                'user_avatar_url': item[11]
            })
        print(items_list)
        return jsonify(items_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# --- Get Available Avatars ---
@app.route('/avatars', methods=['GET'])
def get_avatars():
    folder = 'assets/avatars/png/'
    try:
        # Check if folder exists
        if not os.path.exists(folder):
            # Return default avatars if folder doesn't exist
            default_avatars = [
                {'id': 1, 'name': '3d_1.png', 'path': 'assets/avatars/png/3d_1.png'},
                {'id': 2, 'name': '3d_2.png', 'path': 'assets/avatars/png/3d_2.png'},
                {'id': 3, 'name': '3d_3.png', 'path': 'assets/avatars/png/3d_3.png'},
                {'id': 4, 'name': '3d_4.png', 'path': 'assets/avatars/png/3d_4.png'},
                {'id': 5, 'name': '3d_5.png', 'path': 'assets/avatars/png/3d_5.png'},
            ]
            return jsonify({
                'success': True,
                'avatars': default_avatars,
                'message': 'Using default avatars (folder not found)'
            })
        
        files = os.listdir(folder)
        png_files = [f for f in files if f.lower().endswith('.png')]
        
        avatars = [
            {
                'id': idx + 1,
                'name': filename,
                'path': os.path.join(folder, filename).replace('\\', '/')
            }
            for idx, filename in enumerate(png_files)
            if os.path.isfile(os.path.join(folder, filename))
        ]
        
        return jsonify({
            'success': True,
            'avatars': avatars
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to load avatars: {str(e)}'
        }), 500

# --- Update Avatar Only ---
@app.route('/update-avatar', methods=['POST'])
def update_avatar():
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        avatar_url = data.get('avatar_url')
        
        if not avatar_url:
            return jsonify({
                'success': False,
                'error': 'Avatar URL is required'
            }), 400
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        cursor.execute(
            'UPDATE users SET avatar_url = ? WHERE email = ?',
            (avatar_url, curr_user.get('email'))
        )
        conn.commit()
        conn.close()

        
        # Update current_user_info
        curr_user['avatar_url'] = avatar_url
        
        return jsonify({
            'success': True,
            'message': 'Avatar updated successfully',
            'avatar_url': avatar_url
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to update avatar: {str(e)}'
        }), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, firstname, lastname, email, created_at FROM users')
        users = cursor.fetchall()
        conn.close()
        
        users_list = []
        for user in users:
            users_list.append({
                'id': user[0],
                'firstname': user[1],
                'lastname': user[2],
                'email': user[3],
                'created_at': user[4]
            })
        
        return jsonify({'users': users_list}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# --- Item Management Routes ---
@app.route('/api/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Return the image URL
        image_url = f"/assets/images/{filename}"
        return jsonify({'imageUrl': image_url}), 200
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/items', methods=['POST'])
def create_item():
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'category', 'price', 'description', 'imageUrl']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        # Create new item
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO items (user_id, title, category, price, description, image_url)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            curr_user['id'],
            data['title'],
            data['category'],
            float(data['price']),
            data['description'],
            data['imageUrl']
        ))
        conn.commit()
        
        # Get the inserted item
        item_id = cursor.lastrowid
        cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
        item = cursor.fetchone()
        conn.close()
        
        if item:
            item_data = {
                'id': item[0],
                'user_id': item[1],
                'title': item[2],
                'category': item[3],
                'price': item[4],
                'description': item[5],
                'image_url': item[6],
                'status': item[7],
                'created_at': item[8]
            }
            return jsonify(item_data), 200
        else:
            return jsonify({'error': 'Failed to create item'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items', methods=['GET'])
def get_items():
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT items.*, users.firstname, users.lastname, users.avatar_url 
            FROM items 
            JOIN users ON items.user_id = users.id 
            WHERE items.status = 'available'
            ORDER BY items.created_at DESC
        ''')
        items = cursor.fetchall()
        conn.close()
        
        items_list = []
        for item in items:
            items_list.append({
                'id': item[0],
                'user_id': item[1],
                'title': item[2],
                'category': item[3],
                'price': item[4],
                'description': item[5],
                'image_url': item[6],
                'status': item[7],
                'created_at': item[8],
                'user_firstname': item[9],
                'user_lastname': item[10],
                'user_avatar_url': item[11]
            })
        
        return jsonify(items_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items/user/<user_id>', methods=['GET'])
def get_user_items(user_id):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM items WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        items = cursor.fetchall()
        conn.close()
        
        items_list = []
        for item in items:
            items_list.append({
                'id': item[0],
                'user_id': item[1],
                'title': item[2],
                'category': item[3],
                'price': item[4],
                'description': item[5],
                'image_url': item[6],
                'status': item[7],
                'created_at': item[8]
            })
        
        return jsonify(items_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items/<item_id>', methods=['GET'])
def get_item(item_id):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT items.*, users.firstname, users.lastname, users.avatar_url 
            FROM items 
            JOIN users ON items.user_id = users.id 
            WHERE items.id = ?
        ''', (item_id,))
        item = cursor.fetchone()
        conn.close()
        
        if item:
            item_data = {
                'id': item[0],
                'user_id': item[1],
                'title': item[2],
                'category': item[3],
                'price': item[4],
                'description': item[5],
                'image_url': item[6],
                'status': item[7],
                'created_at': item[8],
                'user_firstname': item[9],
                'user_lastname': item[10],
                'user_avatar_url': item[11]
            }
            return jsonify(item_data), 200
        else:
            return jsonify({'error': 'Item not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items/<item_id>', methods=['DELETE'])
def delete_item(item_id):
    global curr_user
    if not curr_user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Check if item belongs to current user
        cursor.execute('SELECT user_id FROM items WHERE id = ?', (item_id,))
        item = cursor.fetchone()
        
        if not item:
            return jsonify({'error': 'Item not found'}), 404
            
        if item[0] != curr_user['id']:
            return jsonify({'error': 'Not authorized to delete this item'}), 403
            
        # Delete the item
        cursor.execute('DELETE FROM items WHERE id = ?', (item_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Item deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/assets/images/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)