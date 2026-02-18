# PROPOSAL: AI Data Quality Assistant.

## Goal
Enable non-technical users to interact with transactional data using natural language, allowing them to instantly identify missing values, outliers, and inconsistencies without writing SQL.

## The Solution
A proof-of-concept (PoC) application that acts as an **AI Data Analyst**. Users ask questions in plain English, and the system:
1. Translates the question into a safe SQL query using GPT-4o-mini.
2. Executes the query against the data.
3. Returns the exact results (counts, sums, lists of records).

This PoC demonstrates the viability of the concept using a command-line interface and the provided sample data.

---

## Technical Implementation

### How It Works
1. **Schema Inference**: The app automatically detects column names and types from the Excel export.
2. **AI Translation**: GPT-4o-mini converts natural language (e.g., *"How many rows have missing transaction values?"*) into valid SQL.
3. **Safety Layer**: Only `SELECT` statements are allowed; destructive commands (`DROP`, `DELETE`) are blocked.
4. **Execution**: Queries are run via `pandasql` (simulating a SQL database environment).

### Tech Stack
- **Python 3.10+**
- **OpenAI API** (gpt-4o-mini)
- **pandas** & **pandasql**
- **python-dotenv**

## Setup & Usage

### 1. Installation
```bash
git clone <your-repo-url>
cd <repo-name>
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file with your API key:
```
OPENAI_API_KEY=your-api-key-here
```

### 3. Running the Demo
```bash
python main.py "Data Dump - Accrual Accounts.xlsx"
```

The app will load the data and prompt for questions:
```
Ask a data question: How many rows are in the data?

[Generated SQL] SELECT COUNT(*) FROM data
[Result] 13152
```

### Example Data Quality Scenarios
- *How many rows have missing transaction_value?*
- *How many rows have inconsistent fiscal years (Fiscal Year.1 ≠ Fiscal Year.2)?*
- *Which countries have the highest share of missing transaction values?*
- *What is the distribution (min/max/avg) of transaction_value per currency?*
- *How many back-posted documents do we have and what is their total value?*

---

## Next Steps for Production
- **Database Integration**: Replace `pandasql` with a live connection to the company's SQL warehouse.
- **Automated Checks**: Implement a library of scheduled data quality rules (e.g., alert if missing values > 5%).
- **UI/Dashboard**: Build a web frontend for easier access by non-technical staff.
- **Security**: Add user authentication and role-based access control.
