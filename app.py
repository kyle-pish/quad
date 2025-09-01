from flask import Flask, render_template, request, redirect, url_for, session
import bcrypt
import sqlite3
import os

app = Flask(__name__)

# Define the path to the SQLite database file
DATABASE_PATH = os.path.join(os.getcwd(), 'users.db')

app = Flask(__name__)
app.secret_key = os.urandom(24)

'''
create_connection()
function to create a connection to the users.db database

returns:
conn - a connection to the users.db database
'''
def create_connection():
    """Create a connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
    except sqlite3.Error as e:
        print(e)
    return conn


'''
create_table():
creates a users table in the database if one does not exist
'''
def create_table():
    """Create a table to store user information."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        username TEXT UNIQUE,
        password TEXT,
        age INTEGER,
        college TEXT
    )
''')

    conn.commit()
    conn.close()

'''
create_post_table():
creates a posts table in the users.db database if one does not exist
'''
def create_post_table():
    """Create a table to store the posts of users"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        post_content TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')


'''
create_friend_table():
creates a friendships table in the users.db database if one does not exist
'''
def create_friend_table():
    """Create a table to store friend relationships"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS friendships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1_id INTEGER,
        user2_id INTEGER,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY(user1_id) REFERENCES users(id),
        FOREIGN KEY(user2_id) REFERENCES users(id)
    )
''')
    conn.commit()
    conn.close()
    
'''
get_friends_posts(username):
retrieves all posts of frineds from the user.db database

params:
username - a string of a username that is in the user.db database
returns:
all_posts - a list of all posts from friends of [username] in the users.db data
'''
def get_friends_posts(username):
    all_posts = []
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    user_id = cursor.fetchone()
    user_id = user_id[0]
    print("USER ID: ", user_id)
    cursor.execute('SELECT user2_id FROM friendships WHERE user1_id = ?', (user_id,))
    friend_ids = cursor.fetchall()
    cursor.execute('SELECT user1_id FROM friendships WHERE user2_id = ?', (user_id,))
    friend_ids = friend_ids + cursor.fetchall()
    for friend in friend_ids:
        print("FRIENDS IDS: ", friend[0])
        friend_id = friend[0]
        cursor.execute('SELECT username FROM users WHERE id = ?', (friend_id,))
        friend_username = cursor.fetchone()
        print("FRIEND USERNAME: ", friend_username[0])
        friend_username = friend_username[0]
        cursor.execute('SELECT * FROM posts WHERE username = ? ORDER BY timestamp DESC', (friend_username,))
        all_posts = all_posts + cursor.fetchall()
        print("FRIENDS POSTS: ", all_posts)
    conn.close()
    return all_posts


@app.route('/')
def login():
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        import re
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        age = request.form['age']
        college = request.form.get('college', '')

        errors = []
        # Username validation
        if not (4 <= len(username) <= 32):
            errors.append("Username must be between 4 and 32 characters.")
        if not re.match(r'^[A-Za-z0-9_.-]+$', username):
            errors.append("Username can only contain letters, numbers, _, -, and .")

        # Password validation
        if len(password) < 12:
            errors.append("Password must be at least 12 characters long.")
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain a lowercase letter.")
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain an uppercase letter.")
        if not re.search(r'[0-9]', password):
            errors.append("Password must contain a number.")
        if not re.search(r'[^A-Za-z0-9]', password):
            errors.append("Password must contain a special character.")

        if errors:
            return render_template('signup.html', errors=errors)

        # Hash the password before storing
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        conn = create_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('INSERT INTO users (name, username, password, age, college) VALUES (?, ?, ?, ?, ?)',
                           (name, username, hashed_pw, age, college))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()
            return render_template('signup.html', error="Username already exists. Please choose a different one.")

    return render_template('signup.html')


@app.route('/home', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = create_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        if user and bcrypt.checkpw(password.encode('utf-8'), user[3]):
            # Successful login - set the session and redirect to home page
            session['username'] = username
            all_posts = get_friends_posts(username)
            return render_template('home.html', posts=all_posts)
        else:
            # Failed login - handle appropriately (redirect to login page, display error, etc.)
            return "Login failed. Invalid username or password."
        conn.close()

        

        if user:
            all_posts = get_friends_posts(username)
            # Successful login - set the session and redirect to home page
            session['username'] = username
            return render_template('home.html', posts=all_posts)
        else:
            # Failed login - handle appropriately (redirect to login page, display error, etc.)
            return "Login failed. Invalid username or password."

    # Check if the user is logged in using the session
    if 'username' in session:
        username = session['username']
        all_posts = get_friends_posts(username)
        return render_template('home.html', posts=all_posts)
    else:
        return redirect(url_for('login'))

#@app.route('/profile/<username>', methods=['GET'])
@app.route('/profile/<username>', methods=['GET'])
def profile(username):
    print("Username parameter:", username)
    if 'username' in session:
        if username:
            # Fetch user profile information from the database and pass it to the template
            conn = create_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user_data = cursor.fetchone()
            print(user_data)
            # Get the count of followed users for the logged-in user
            
            # Fetch user's friends
            cursor.execute('''
                SELECT u.*
                FROM users u
                INNER JOIN friendships f ON u.id = f.user2_id
                INNER JOIN users u2 ON f.user1_id = u2.id
                WHERE u2.username = ?
            ''', (username,))
            friends = cursor.fetchall()

            # Only show posts if friendship is accepted
            posts = []
            my_username = session['username']
            cursor.execute('SELECT id FROM users WHERE username = ?', (my_username,))
            my_id_row = cursor.fetchone()
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            other_id_row = cursor.fetchone()
            is_friend = False
            if my_id_row and other_id_row:
                my_id = my_id_row[0]
                other_id = other_id_row[0]
                cursor.execute('SELECT status FROM friendships WHERE ((user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)) AND status = "accepted"', (my_id, other_id, other_id, my_id))
                if cursor.fetchone():
                    is_friend = True
            if user_data:
                if is_friend or my_username == username:
                    cursor.execute('SELECT * FROM posts WHERE username = ? ORDER BY timestamp DESC', (username,))
                    posts = cursor.fetchall()
                    conn.close()
                    return render_template('profile.html', user=user_data, posts=posts, friends=friends)
                else:
                    conn.close()
                    return render_template('profile.html', user=user_data, posts=None, friends=friends, not_friends=True)
            else:
                conn.close()
                return "User data not found."
        else:
            return "Username not provided."
    else:
        return redirect(url_for('login'))
    
    
@app.route('/search', methods=['GET'])
def search():
    if 'username' in session:
        search_username = request.args.get('search_username')

        conn = create_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE username = ?', (search_username,))
        user_data = cursor.fetchone()
        conn.close()

        if user_data:
            return render_template('search.html', user_data=user_data)
        else:
            return render_template('search.html', user_not_found=True)

    return redirect(url_for('login'))


@app.route('/makepost', methods=['GET'])
def make_post():
    return render_template('makepost.html')

@app.route('/post', methods=['POST'])
def create_post():
    post = request.form.get('post')
    username = request.form.get('username')
    conn = create_connection()
    cursor = conn.cursor()

    # conn2 = create_connection()
    # cursor2 = conn2.cursor()

    # cursor2.execute('SELECT * FROM users WHERE username = ?', (username,))
    # user_data = cursor2.fetchone()

    # conn2.close()
    print("username:")
    print(username)
    print("post:")
    print(post)
    try:
        cursor.execute('INSERT INTO posts (username, post_content) VALUES (?, ?)', 
                        (username, post))

        conn.commit()
        conn.close()

        all_posts = get_friends_posts(username)

        return render_template('home.html', posts=all_posts)
    except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()
            return "Post could not be posted at this time"
    


@app.route('/addfriend', methods=['POST'])
def add_friend():
    if 'username' in session:
        friend_username = request.form.get('username')

        conn = create_connection()
        cursor = conn.cursor()

        # Get the IDs of the logged-in user and the user to be added as a friend
        cursor.execute('SELECT id FROM users WHERE username = ?', (session['username'],))
        user1_id = cursor.fetchone()[0]

        cursor.execute('SELECT id FROM users WHERE username = ?', (friend_username,))
        user2_id = cursor.fetchone()[0]

        # Check if the friendship already exists
        cursor.execute('SELECT * FROM friendships WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)',
                       (user1_id, user2_id, user2_id, user1_id))
        existing_friendship = cursor.fetchone()

        if existing_friendship:
            conn.close()
            return "Friend already added."

        # Add the friendship to the database
        cursor.execute('INSERT INTO friendships (user1_id, user2_id) VALUES (?, ?)', (user1_id, user2_id))
        conn.commit()
        conn.close()
        return "Friend added successfully."
    else:
        return redirect(url_for('login'))

    
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))



if __name__ == '__main__':
    create_table()  # Create the table when the app starts
    create_post_table() # Create the table for the posts
    create_friend_table()
    app.run(debug=True)
    #app.run(host='10.6.8.167', port=5000, debug=True)

