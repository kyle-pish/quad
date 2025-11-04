from flask import Flask, render_template, request, redirect, url_for, session, jsonify
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


@app.context_processor
def inject_unread_notifications():
    """Inject unread notification count into all templates as `unread_notifications`."""
    try:
        if 'username' not in session:
            return {}
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (session['username'],))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {}
        user_id = row[0]
        cursor.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0', (user_id,))
        count = cursor.fetchone()[0] or 0
        conn.close()
        return {'unread_notifications': count}
    except Exception:
        # If anything fails, don't break template rendering
        return {'unread_notifications': 0}


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
        username TEXT UNIQUE COLLATE NOCASE,
        password TEXT,
        age INTEGER,
        college TEXT,
        pfp TEXT DEFAULT ''
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
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        group_name TEXT DEFAULT NULL
    )
    ''')
    conn.commit()
    conn.close()


def ensure_posts_group_column():
    """Ensure the posts table has the group_name column (for existing DBs)."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(posts)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'group_name' not in cols:
        try:
            cursor.execute('ALTER TABLE posts ADD COLUMN group_name TEXT DEFAULT NULL')
            conn.commit()
        except sqlite3.DatabaseError:
            pass
    conn.close()


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
create_notifications_table():
creates a notifications table in the users.db database if one does not exist
'''
def create_notifications_table():
    """Create a table to store notifications for users"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        message TEXT,
        is_read INTEGER DEFAULT 0,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')
    conn.commit()
    conn.close()

def create_likes_table():
    """Create a table to store likes on posts"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        post_id INTEGER NOT NULL,
        UNIQUE(user_id, post_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(post_id) REFERENCES posts(id)
    )
    ''')
    conn.commit()
    conn.close()

def create_comments_table():
    """Create a table to store comments on posts"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(post_id) REFERENCES posts(id)
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
    """Retrieve posts from both mutual friends and the logged-in user, sorted by timestamp.
    
    Args:
        username: The logged-in user's username
    Returns:
        List of posts from mutual friends and the user's own posts, sorted by timestamp
    """
    all_posts = []
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (username,))
    user_id = cursor.fetchone()[0]

    # First, get mutual friends (users who have added each other)
    cursor.execute('''
        SELECT u.username FROM users u
        WHERE u.id != ? AND EXISTS (
            SELECT 1 FROM friendships f1 WHERE f1.user1_id = ? AND f1.user2_id = u.id
        ) AND EXISTS (
            SELECT 1 FROM friendships f2 WHERE f2.user1_id = u.id AND f2.user2_id = ?
        )
    ''', (user_id, user_id, user_id))
    mutual_friends = [friend[0] for friend in cursor.fetchall()]
    
    # Include the user's own username in the list of usernames to fetch posts from
    usernames_to_fetch = mutual_friends + [username]
    
    # Fetch posts for all usernames (friends + self)
    for username_to_fetch in usernames_to_fetch:
        # Exclude posts that belong to a group (group_name not empty) from the home/friends feed
        cursor.execute('SELECT * FROM posts WHERE username = ? COLLATE NOCASE AND (group_name IS NULL OR group_name = "")', (username_to_fetch,))
        posts = cursor.fetchall()
        for post in posts:
            post_id = post[0]
            cursor.execute('SELECT COUNT(*) FROM likes WHERE post_id = ?', (post_id,))
            like_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM comments WHERE post_id = ?', (post_id,))
            comment_count = cursor.fetchone()[0]
            cursor.execute('SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?', (user_id, post_id))
            liked = cursor.fetchone() is not None
            all_posts.append({
                'id': post[0],
                'username': post[1],
                'post_content': post[2],
                'timestamp': post[3],
                'like_count': like_count,
                'comment_count': comment_count,
                'liked': liked
            })
    
    # Sort all posts by timestamp, newest first
    all_posts.sort(key=lambda p: p['timestamp'], reverse=True)
    
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
        pfp = request.form.get('pfp', '')

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
            cursor.execute('INSERT INTO users (name, username, password, age, college, pfp) VALUES (?, ?, ?, ?, ?, ?)',
                           (name, username, hashed_pw, age, college, pfp))
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

        # Perform case-insensitive lookup for login
        cursor.execute('SELECT * FROM users WHERE username = ? COLLATE NOCASE', (username,))
        user = cursor.fetchone()
        if user and bcrypt.checkpw(password.encode('utf-8'), user[3]):
            # Successful login - set the session to the stored username (preserve original casing)
            stored_username = user[2]
            stored_pfp = user[6] if len(user) > 6 else ''
            session['username'] = stored_username
            session['pfp'] = stored_pfp
            all_posts = get_friends_posts(stored_username)
            return render_template('home.html', posts=all_posts)
        else:
            # Failed login - show error on login page
            conn.close()
            return render_template('login.html', error="Invalid username or password.", username=username)

        

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
        # ensure pfp is available in session
        if 'pfp' not in session:
            conn = create_connection()
            cur = conn.cursor()
            cur.execute('SELECT pfp FROM users WHERE username = ? COLLATE NOCASE', (username,))
            row = cur.fetchone()
            if row:
                session['pfp'] = row[0]
            conn.close()
        all_posts = get_friends_posts(username)
        return render_template('home.html', posts=all_posts)
    else:
        return redirect(url_for('login'))


@app.route('/group')
def group_page():
    """Show the community page for the logged-in user's school/group."""
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    conn = create_connection()
    cursor = conn.cursor()
    # get user's college/school
    cursor.execute('SELECT college, id FROM users WHERE username = ? COLLATE NOCASE', (username,))
    row = cursor.fetchone()
    if not row or not row[0]:
        conn.close()
        return render_template('group.html', posts=[], group_name=None, message='No school associated with your account.')
    default_group = row[0]
    user_id = row[1]

    # allow overriding via query param (when navigating from groups list)
    group_name = request.args.get('group') or default_group

    # fetch posts that belong to this group
    cursor.execute('SELECT * FROM posts WHERE group_name = ? ORDER BY timestamp DESC', (group_name,))
    posts_raw = cursor.fetchall()
    posts = []
    for post in posts_raw:
        post_id = post[0]
        cursor.execute('SELECT COUNT(*) FROM likes WHERE post_id = ?', (post_id,))
        like_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM comments WHERE post_id = ?', (post_id,))
        comment_count = cursor.fetchone()[0]
        cursor.execute('SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?', (user_id, post_id))
        liked = cursor.fetchone() is not None
        posts.append({
            'id': post[0],
            'username': post[1],
            'post_content': post[2],
            'timestamp': post[3],
            'like_count': like_count,
            'comment_count': comment_count,
            'liked': liked
        })
    conn.close()
    # Reuse the home template so group pages display exactly like the home feed
    return render_template('home.html', posts=posts, group_view=True, group_name=group_name)


@app.route('/groups')
def groups_page():
    """Show a list of groups the current user belongs to."""
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    conn = create_connection()
    cursor = conn.cursor()

    groups = []
    # primary group: the user's college
    cursor.execute('SELECT college FROM users WHERE username = ? COLLATE NOCASE', (username,))
    row = cursor.fetchone()
    if row and row[0]:
        college = row[0]
        # member count = users with same college
        cursor.execute('SELECT COUNT(*) FROM users WHERE college = ?', (college,))
        member_count = cursor.fetchone()[0] or 0
        # post count = posts with this group_name
        cursor.execute('SELECT COUNT(*) FROM posts WHERE group_name = ?', (college,))
        post_count = cursor.fetchone()[0] or 0
        groups.append({ 'name': college, 'description': f'Community for {college} students', 'member_count': member_count, 'post_count': post_count })

    # also include any other distinct groups the user has posted to
    cursor.execute('SELECT DISTINCT group_name FROM posts WHERE username = ? AND group_name IS NOT NULL AND group_name != ""', (username,))
    for (gname,) in cursor.fetchall():
        if not gname:
            continue
        if any(g['name'] == gname for g in groups):
            continue
        cursor.execute('SELECT COUNT(*) FROM users WHERE college = ?', (gname,))
        member_count = cursor.fetchone()[0] or 0
        cursor.execute('SELECT COUNT(*) FROM posts WHERE group_name = ?', (gname,))
        post_count = cursor.fetchone()[0] or 0
        groups.append({ 'name': gname, 'description': f'Community: {gname}', 'member_count': member_count, 'post_count': post_count })

    conn.close()
    return render_template('groups.html', groups=groups)

#@app.route('/profile/<username>', methods=['GET'])
@app.route('/profile/<username>', methods=['GET'])
def profile(username):
    print("Username parameter:", username)
    if 'username' in session:
        if username:
            # Fetch user profile information from the database and pass it to the template
            conn = create_connection()
            cursor = conn.cursor()

            # Case-insensitive profile lookup
            cursor.execute('SELECT * FROM users WHERE username = ? COLLATE NOCASE', (username,))
            user_data = cursor.fetchone()
            print(user_data)
            # Get the count of followed users for the logged-in user
            
            # Fetch mutual friends only
            cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (username,))
            user_id = cursor.fetchone()[0]
            cursor.execute('''
                SELECT u.* FROM users u
                WHERE u.id != ? AND EXISTS (
                    SELECT 1 FROM friendships f1 WHERE f1.user1_id = ? AND f1.user2_id = u.id
                ) AND EXISTS (
                    SELECT 1 FROM friendships f2 WHERE f2.user1_id = u.id AND f2.user2_id = ?
                )
            ''', (user_id, user_id, user_id))
            friends = cursor.fetchall()

            # Only show posts if friendship is accepted
            posts = []
            my_username = session['username']
            cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (my_username,))
            my_id_row = cursor.fetchone()
            cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (username,))
            other_id_row = cursor.fetchone()
            is_friend = False
            if my_id_row and other_id_row:
                my_id = my_id_row[0]
                other_id = other_id_row[0]
                cursor.execute('SELECT status FROM friendships WHERE ((user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)) AND status = "accepted"', (my_id, other_id, other_id, my_id))
                if cursor.fetchone():
                    is_friend = True
            if user_data:
                # Determine viewer's and owner's college to decide whether to show group posts
                cursor.execute('SELECT college FROM users WHERE username = ? COLLATE NOCASE', (my_username,))
                viewer_college_row = cursor.fetchone()
                viewer_college = viewer_college_row[0] if viewer_college_row else None
                owner_college = user_data[5] if len(user_data) > 5 else None

                # If friend, owner, or same-college viewer, allow group posts as well
                if is_friend or my_username == username or (viewer_college and owner_college and viewer_college == owner_college):
                    cursor.execute('SELECT * FROM posts WHERE username = ? ORDER BY timestamp DESC', (user_data[2],))
                else:
                    # Exclude group posts when viewer isn't authorized
                    cursor.execute('SELECT * FROM posts WHERE username = ? AND (group_name IS NULL OR group_name = "") ORDER BY timestamp DESC', (user_data[2],))

                posts_raw = cursor.fetchall()
                posts = []
                for post in posts_raw:
                    post_id = post[0]
                    cursor.execute('SELECT COUNT(*) FROM likes WHERE post_id = ?', (post_id,))
                    like_count = cursor.fetchone()[0]
                    cursor.execute('SELECT COUNT(*) FROM comments WHERE post_id = ?', (post_id,))
                    comment_count = cursor.fetchone()[0]
                    # post tuple: (id, username, post_content, timestamp, group_name)
                    group_name = post[4] if len(post) > 4 else None
                    # store group_name alongside other values
                    posts.append((post[0], post[1], post[2], post[3], like_count, group_name))
                conn.close()
                # convert posts to include comment count
                posts_with_counts = []
                for p in posts:
                    # p is (id, username, content, timestamp, like_count, group_name)
                    cursor_conn = create_connection()
                    cur = cursor_conn.cursor()
                    cur.execute('SELECT COUNT(*) FROM comments WHERE post_id = ?', (p[0],))
                    cc = cur.fetchone()[0]
                    cursor_conn.close()
                    # final tuple: (id, username, content, timestamp, like_count, comment_count, group_name)
                    posts_with_counts.append((p[0], p[1], p[2], p[3], p[4], cc, p[5]))
                return render_template('profile.html', user=user_data, posts=posts_with_counts, friends=friends)
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

        # Case-insensitive search lookup (but return stored-case username/display info)
        cursor.execute('SELECT * FROM users WHERE username = ? COLLATE NOCASE', (search_username,))
        user_data = cursor.fetchone()

        friend_status = None
        if user_data:
            # Get IDs (case-insensitive)
            cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (session['username'],))
            my_id_row = cursor.fetchone()
            cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (search_username,))
            other_id_row = cursor.fetchone()
            if my_id_row and other_id_row:
                my_id = my_id_row[0]
                other_id = other_id_row[0]
                # Check if current user has added searched user
                cursor.execute('SELECT * FROM friendships WHERE user1_id = ? AND user2_id = ?', (my_id, other_id))
                added = cursor.fetchone()
                # Check if searched user has added current user
                cursor.execute('SELECT * FROM friendships WHERE user1_id = ? AND user2_id = ?', (other_id, my_id))
                added_back = cursor.fetchone()
                if added and added_back:
                    friend_status = 'friends'
                elif added:
                    friend_status = 'pending'
                else:
                    friend_status = None
            conn.close()
            return render_template('search.html', user_data=user_data, friend_status=friend_status)
        else:
            conn.close()
            return render_template('search.html', user_not_found=True)
    return redirect(url_for('login'))


@app.route('/makepost', methods=['GET'])
def make_post():
    scope = request.args.get('scope', 'friends')
    return render_template('makepost.html', scope=scope)

@app.route('/post', methods=['POST'])
def create_post():
    post = request.form.get('post')
    username = request.form.get('username')
    scope = request.form.get('scope')  # 'friends' or 'group'
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
    # Determine whether this post should be a group post
    group_name = None
    if scope == 'group':
        # look up user's college/school and set as group
        cursor.execute('SELECT college FROM users WHERE username = ? COLLATE NOCASE', (username,))
        row = cursor.fetchone()
        if row and row[0]:
            group_name = row[0]

    try:
        if group_name:
            cursor.execute('INSERT INTO posts (username, post_content, group_name) VALUES (?, ?, ?)',
                           (username, post, group_name))
        else:
            cursor.execute('INSERT INTO posts (username, post_content) VALUES (?, ?)',
                           (username, post))

        conn.commit()
        conn.close()

        # If this was a group post, send the user back to the group page so they see it
        if group_name:
            return redirect(url_for('group_page'))

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

        # Get the IDs of the logged-in user and the user to be added as a friend (case-insensitive)
        cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (session['username'],))
        user1_row = cursor.fetchone()
        if not user1_row:
            conn.close()
            return "Current user not found."
        user1_id = user1_row[0]

        cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (friend_username,))
        user2_row = cursor.fetchone()
        if not user2_row:
            conn.close()
            return "User to add not found."
        user2_id = user2_row[0]

        # Only prevent duplicate adds in the same direction
        cursor.execute('SELECT * FROM friendships WHERE user1_id = ? AND user2_id = ?', (user1_id, user2_id))
        existing_friendship = cursor.fetchone()

        if existing_friendship:
            conn.close()
            return "Friend already added."

        # Add the friendship to the database
        cursor.execute('INSERT INTO friendships (user1_id, user2_id) VALUES (?, ?)', (user1_id, user2_id))
        # Add notification for the user being added
        cursor.execute('INSERT INTO notifications (user_id, type, message) VALUES (?, ?, ?)',
                       (user2_id, 'friend_request', f"{session['username']} added you as a friend."))
        conn.commit()
        conn.close()
        return "Friend added successfully."
    return redirect(url_for('login'))

    
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/notifications')
def notifications():
    if 'username' in session:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (session['username'],))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return redirect(url_for('login'))
        user_id = row[0]
        cursor.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
        notifications = cursor.fetchall()
        conn.close()
        return render_template('notifications.html', notifications=notifications)
    return redirect(url_for('login'))


@app.route('/notifications/mark_read', methods=['POST'])
def mark_notification_read():
    """Mark a notification as read for the current user.

    Expects form field `id` with the notification id.
    """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'not_logged_in'}), 401
    nid = request.form.get('id')
    if not nid:
        return jsonify({'success': False, 'error': 'missing_id'}), 400
    try:
        nid = int(nid)
    except ValueError:
        return jsonify({'success': False, 'error': 'bad_id'}), 400

    conn = create_connection()
    cursor = conn.cursor()
    # ensure the notification belongs to the current user
    cursor.execute('SELECT user_id FROM notifications WHERE id = ?', (nid,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': 'not_found'}), 404
    user_id = row[0]
    cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (session['username'],))
    cur_row = cursor.fetchone()
    if not cur_row or cur_row[0] != user_id:
        conn.close()
        return jsonify({'success': False, 'error': 'not_owner'}), 403

    cursor.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (nid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/check_username', methods=['POST'])
def check_username():
    username = request.form.get('username')
    conn = create_connection()
    cursor = conn.cursor()
    # Check existence case-insensitively
    cursor.execute('SELECT 1 FROM users WHERE username = ? COLLATE NOCASE', (username,))
    exists = cursor.fetchone() is not None
    conn.close()
    return jsonify({'available': not exists})


@app.route('/comments/<int:post_id>', methods=['GET'])
def get_comments(post_id):
    """Return JSON list of comments for a given post id"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, u.username, c.content, c.timestamp, u.pfp
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.post_id = ?
        ORDER BY c.timestamp DESC
    ''', (post_id,))
    rows = cursor.fetchall()
    conn.close()
    comments = []
    for r in rows:
        comments.append({'id': r[0], 'username': r[1], 'content': r[2], 'timestamp': r[3], 'pfp': r[4]})
    return jsonify({'comments': comments})


@app.route('/add_comment', methods=['POST'])
def add_comment():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    post_id = request.form.get('post_id')
    content = request.form.get('content')
    if not post_id or not content:
        return jsonify({'error': 'post_id and content are required'}), 400
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (session['username'],))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    user_id = user_row[0]
    try:
        cursor.execute('INSERT INTO comments (post_id, user_id, content) VALUES (?, ?, ?)', (post_id, user_id, content))
        # optional: add notification to post author
        cursor.execute('SELECT username FROM posts WHERE id = ?', (post_id,))
        post_author_row = cursor.fetchone()
        if post_author_row:
            post_author = post_author_row[0]
            if post_author != session['username']:
                cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (post_author,))
                author_id_row = cursor.fetchone()
                if author_id_row:
                    author_id = author_id_row[0]
                    cursor.execute('INSERT INTO notifications (user_id, type, message) VALUES (?, ?, ?)',
                                   (author_id, 'comment', f"{session['username']} commented on your post."))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()
        return jsonify({'error': 'Could not add comment'}), 500

@app.route('/like_post', methods=['POST'])
def like_post():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    post_id = request.form.get('post_id')
    action = request.form.get('action')  # 'like' or 'unlike'
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (session['username'],))
    user_id = cursor.fetchone()[0]
    cursor.execute('SELECT username FROM posts WHERE id = ?', (post_id,))
    post_author_row = cursor.fetchone()
    if not post_author_row:
        conn.close()
        return jsonify({'error': 'Post not found'}), 404
    post_author = post_author_row[0]
    if action == 'like':
        # Check if this user has ever liked this post before
        cursor.execute('SELECT 1 FROM notifications WHERE user_id = (SELECT id FROM users WHERE username = ? COLLATE NOCASE) AND type = "like" AND message = ? LIMIT 1',
                       (post_author, f"{session['username']} liked your post."))
        already_notified = cursor.fetchone() is not None
        try:
            cursor.execute('INSERT INTO likes (user_id, post_id) VALUES (?, ?)', (user_id, post_id))
            # Add notification for post author if not self and not already notified
            if post_author != session['username'] and not already_notified:
                cursor.execute('SELECT id FROM users WHERE username = ? COLLATE NOCASE', (post_author,))
                author_id = cursor.fetchone()[0]
                cursor.execute('INSERT INTO notifications (user_id, type, message) VALUES (?, ?, ?)',
                               (author_id, 'like', f"{session['username']} liked your post."))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # Already liked
    elif action == 'unlike':
        cursor.execute('DELETE FROM likes WHERE user_id = ? AND post_id = ?', (user_id, post_id))
        conn.commit()
    # Get updated like count
    cursor.execute('SELECT COUNT(*) FROM likes WHERE post_id = ?', (post_id,))
    like_count = cursor.fetchone()[0]
    conn.close()
    return jsonify({'like_count': like_count})

if __name__ == '__main__':
    create_table()  # Create the table when the app starts
    create_post_table() # Create the table for the posts
    # ensure legacy DBs get the new column for group posts
    try:
        ensure_posts_group_column()
    except NameError:
        pass
    create_friend_table()
    create_notifications_table()
    create_likes_table()
    create_comments_table()
    app.run(debug=True)
    #app.run(host='10.6.8.167', port=5000, debug=True)

