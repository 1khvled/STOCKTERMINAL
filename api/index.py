import os
import sys

# Ensure the app directory is in the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))

# Import the Flask app
from server import app

# Vercel needs the app object to serve the application
# No need to run app.run() here
