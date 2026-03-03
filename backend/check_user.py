import sqlite3

try:
    conn = sqlite3.connect('trinity.db')
    cursor = conn.cursor()
    
    # Get table schema
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print("Users table schema:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Check for test@test.com
    cursor.execute('SELECT * FROM users WHERE email = ?', ('test@test.com',))
    result = cursor.fetchone()
    
    if result:
        print(f"\n✓ User 'test@test.com' EXISTS in database")
        print("  Solution: Either login with this email or use a different email to register")
    else:
        print("\n✗ User 'test@test.com' NOT found")
        print("  The registration should have worked. There might be a different issue.")
        
    # Show all users
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    print(f"\nTotal users in database: {count}")
    
    if count > 0:
        cursor.execute('SELECT email FROM users LIMIT 5')
        users = cursor.fetchall()
        print("\nRegistered emails:")
        for user in users:
            print(f"  - {user[0]}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
