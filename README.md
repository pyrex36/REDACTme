# REDACTme

🛠️ Prerequisites
Ensure you have the following installed on your system:

Python 3.10+

pip (Python package installer)

A modern web browser (Chrome, Firefox, Safari, Edge)

🚀 Step-by-Step Running Instructions
Option A: Quick Launch via Shell Script (macOS / Linux)
If you are on a Unix-based system, you can use the included automated setup script to install dependencies, download the NLP models, and launch the server.

Make the script executable:
Open your terminal, navigate to the project root directory, and run:
chmod +x backend/setup.sh

Execute the script:
./backend/setup.sh
The script will automatically install dependencies, pull the required spaCy language model, and spin up the backend API on http://localhost:8000.

Open the Frontend UI:
Double-click frontend/index.html to open it directly in your web browser.
-------------------------------------------------------------------------------------------------------------------------------------------------------

Option B: Manual Setup (Windows / macOS / Linux)
Follow these steps to manually set up and run the application environment.

1. Set Up the Backend Server
Open your terminal or command prompt, navigate to the backend/ folder, and follow these commands:

Step 1: Create a virtual environment (Recommended)
python -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows (Command Prompt):
venv\\Scripts\\activate.bat

# On Windows (PowerShell):
.\\venv\\Scripts\\Activate.ps1

Step 2: Install Python dependencies
pip install -r requirements.txt

Step 3: Download the spaCy NLP language model
python -m spacy download en_core_web_sm

Step 4: Start the FastAPI server
uvicorn main:app --reload --port 8000 --host 0.0.0.0

You should see output indicating that Uvicorn running on http://0.0.0.0:8000 is active.


2. Launch the Frontend Application
Because the frontend uses standard modern web APIs to communicate with localhost:8000, you have two straightforward ways to load the UI:

Direct File Load: Simply open your file explorer, navigate to the frontend/ directory, and double-click index.html to open it in your browser (file:///path/to/frontend/index.html).

Local HTTP Server (Optional): If you prefer serving the frontend over local HTTP, open a new terminal tab in the frontend/ directory and run:
python -m http.server 3000


🧪 Testing the Application
Drag and drop a standard PDF containing sample PII (e.g., Canadian Social Insurance Numbers formatted as 123-456-789, phone numbers, credit card strings, or standard names/locations) into the designated SecureRedact drop zone.

Click "Redact Document".

The interface will stream the optimized file payload directly to your local backend server, securely redact the requested boundaries, execute a structural file verification check, and instantly prompt you to download the finalized _redacted.pdf artifact.

Try highlighting or searching for the masked text within the new PDF to confirm that structural extraction is physically impossible.
