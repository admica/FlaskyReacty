#!/opt/pcapserver/venv_linux/bin/python3

import bcrypt
import getpass
import json

def generate_user_hash():
    # Get username
    username = input("Enter username: ").strip()
    
    # Get password securely (no show)
    password = getpass.getpass("Enter password: ")
    confirm_password = getpass.getpass("Confirm password: ")
    
    # Verify passwords match
    if password != confirm_password:
        print("Error: Passwords do not match!")
        return
    
    # Generate hash
    salt = bcrypt.gensalt(12)
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
    
    # Create config entry
    user_entry = {"username": username, "password": password_hash.decode('utf-8'), "role": "user"}
    
    # Output in config.ini format
    print(f"{username} = {json.dumps(user_entry)}")

if __name__ == "__main__":
    try:
        generate_user_hash()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
    except Exception as e:
        print(f"Error: {e}")
