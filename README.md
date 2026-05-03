<!-- PROJECT LOGO -->
<p align="center">
  <img src="https://upload.wikimedia.org/wikipedia/commons/c/c3/Python-logo-notext.svg" alt="Logo" width="120" height="120">
</p>

<h1 align="center">Recruitment Chatbot – Multi-Agent Orchestration</h1>

<p align="center">
  A Streamlit proof-of-concept for a multi-agent recruiting chatbot<br>
  <a href="#demo">View Demo</a>
  ·
  <a href="#demo">Report Bug</a>
  ·
  <a href="#demo">Request Feature</a>
</p>

---
<br></br>

## Table of Contents

- [About The Project](#about-the-project)
- [Features](#features)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Screenshots](#screenshots)
- [Code Examples](#code-examples)
- [Project Structure](#project-structure)
- [To-Do List](#to-do-list)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)
- [Acknowledgments](#acknowledgments)

---
<br></br>


## About The Project

> This project implements a **multi-agent recruitment chatbot** designed to interact with job candidates for a Python Developer position.

The chatbot simulates an SMS-based conversation (implemented via Streamlit for this PoC) and is responsible for guiding candidates through the recruitment process. Its main objectives are:

- Collect and verify candidate information 
- Answer questions about the role 
- Progress the conversation toward scheduling an interview 
- Politely end the conversation when appropriate 

### Multi-Agent Architecture

The system is built using a **modular multi-agent design**, where a central orchestrator (Main Agent) collaborates with specialized advisor agents:

- **Main Agent** – Manages the conversation and decides the next action 
- **Info Advisor** – Answers candidate questions using RAG over a job description PDF 
- **Scheduling Advisor** – Suggests and validates interview time slots using a SQL database 
- **Exit Advisor** – Determines when the conversation should end (fine-tuned model) 

At each turn, the system selects one of three actions:

- `CONTINUE` – keep the conversation going 
- `SCHEDULE` – move toward booking an interview 
- `END` – conclude the interaction 

### Evaluation

The system is evaluated using a labeled dataset of real conversations, where each turn is annotated with the correct action (`continue`, `schedule`, `end`). 

Performance is measured using:
- Accuracy 
- Confusion Matrix 

This project demonstrates how multi-agent orchestration, retrieval-augmented generation (RAG), and tool integration can be combined to build a realistic, goal-oriented conversational system.
<br>

<div style="background: #272822; color: #f8f8f2; padding: 10px; border-radius: 8px;">
  <b> Technologies:</b> Python, Pandas, NumPy, Matplotlib, OpenAI API, LangChain, SQL Server, Streamlit, Chroma
</div>

---
<br></br>


## Features

- Multi-agent conversation orchestration (Main Agent + Advisors)
- Intelligent routing between:
  - Continue conversation
  - Schedule interview
  - End conversation
- Retrieval-Augmented Generation (RAG) for answering job-related questions
- Interview scheduling via SQL Server (function calling)
- Natural language date handling (e.g., "next Monday")
- Fine-tuned Exit Advisor for conversation termination decisions
- Streamlit-based interactive chat interface
- Conversation state management across turns
- Evaluation framework using labeled conversations (accuracy & confusion matrix)
- Cloud deployment  

---
<br></br>


##  Getting Started

### Prerequisites

- Python >= 3.12
- pip

## Live Demo

You can access the deployed application to streamlit community cloud here:

👉 https://genaifinalproject-mqr3xjd9xcr6ywglzoyz2n.streamlit.app/

Note: Tech DB is deployed to Azure SQL, so connection on the first time can take longer

### Running the application on a Windows machine

Follow these steps to run the application on a Windows machine, using a local SQL Server database created with SSMS.

#### 1. Clone the repository and create virtual environment
```bash
git clone https://github.com/bermanalon/GenAI_final_project.git
cd GenAI_final_project


python -m venv .venv

.venv\Scripts\activate 

pip install -r requirements.txt

```
#### 2. Configure environment variables
Create a .env file based on the provided template:
```bash
copy .env.example .env
```
Edit the .env file and set the following values:
```env
OPENAI_API_KEY=your_api_key_here

APP_ENV=local

DB_DRIVER=ODBC Driver 17 for SQL Server
DB_SERVER=your_sql_server
DB_DATABASE=Tech
```
#### 3. Create Tech Data base
Run the following script in SSMS to create and populate the database:
```sql
db_Tech.sql
```
The sample database may contain historical demo dates. If needed, update the dates to the current project year before testing scheduling flows.
For example - you can use the following script (adding 2 years):
```sql
UPDATE dbo.Schedule
SET [date] = DATEADD(YEAR, 2, [date]);
```
Note: it will cause scheduling slots to fall also on Saturdays and Sundays.
#### 4. Run the application
Run the application
```bash
streamlit run streamlit_app/streamlit_main.py
```


---
<br></br>



## Usage

After starting the Streamlit application, the user first fills in a short registration form with basic applicant details.

The chatbot then opens a conversation interface where the candidate can:

- Describe their professional experience
- Ask questions about the Python Developer role
- Request to schedule an interview
- Confirm or reject suggested interview slots

The Main Agent manages each user turn and routes the conversation to the appropriate advisor:

- `Info Advisor` for job-related questions
- `Scheduling Advisor` for interview scheduling
- `Exit Advisor` for detecting when the conversation should end

The conversation ends when an interview is confirmed or when the candidate clearly asks to stop or is no longer interested.

---
<br></br>


## Screenshots

<p float="left">
  <img src="https://mir-s3-cdn-cf.behance.net/project_modules/max_1200/e50214173218977.648c4882a75d6.gif"  width="400"/>
</p>

---
<br></br>


## Code Examples

```python
import pandas as pd
from openai import OpenAI

client = OpenAI(api_key="your_api_key_here") # Replace with your actual API key or use environment variable

# Load data
df = pd.read_csv('data/dataset.csv')

```

---
<br></br>


## Project Structure

```text
python-project/
├── data/
│   └── dataset.csv
├── python_project/
│   ├── __init__.py
│   └── python_project.py
├── tests/
│   └── test.py
├── main.py
├── requirements.txt
└── README.md
```

---
<br></br>


## To-Do List

- [x] Initial project setup
- [x] Add python_project module
- [ ] Improve documentation
- [ ] Add web interface


---
<br></br>


## Contributing

Contributions are **welcome**! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---
<br></br>



## License

Distributed under the XXX License. See `LICENSE` for more information.

---
<br></br>


## Contact

**Your Name** - [@yourtmail@gmail.com](yourmail@gmail.com)  
Project Link: [https://github.com/yourusername/python-project](https://github.com/yourusername/python-project)

---
<br></br>


## Acknowledgments

- [Python](https://www.python.org/)
- [Pandas](https://pandas.pydata.org/)
- [OpenAI API](https://platform.openai.com/docs/overview)


---
