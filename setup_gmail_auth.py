import sys
import os

# Ensure we can import from the Backend directory
sys.path.append(os.getcwd())

try:
    from Backend.app.services.gmail_service import gmail_service
    print("Starting Gmail Authentication Process...")
    print("A browser window should open shortly to authenticate with your Google Account.")
    print("If you haven't placed 'credentials.json' in this folder yet, this will fail.")
    
    gmail_service.authenticate_interactive()
    
    if os.path.exists('token.json'):
        print("\nSUCCESS! 'token.json' has been created.")
        print("The Gmail integration is now ready to use.")
    else:
        print("\nAuth process completed but 'token.json' was not found. Something might have gone wrong.")
        
except ImportError as e:
    print(f"Error importing gmail_service: {e}")
    print("Make sure you are running this script from the project root directory.")
except Exception as e:
    print(f"An error occurred: {e}")
