# PolicyPilot System Evaluation Report

This report displays the performance evaluation of the PolicyPilot RAG pipeline.

## Overall Metrics

| Metric | Score |
| :--- | :--- |
| **Total Evaluation Cases** | 20 |
| **Retrieval Recall@4 (Hit Rate)** | 100.00% |
| **Average Token-level F1** | 36.75% |
| **Average Semantic Cosine Similarity** | 69.56% |

## Query-by-Query Performance Detail

| ID | Question | Expected Doc/Page | Retrieval Hit? | Token F1 | Semantic Sim |
| :--- | :--- | :--- | :---: | :---: | :---: |
| 1 | How many annual leave days do full-time employees get per year? | `leave_policy.pdf` (P.1) | ✅ | 42.9% | 80.1% |
| 2 | What is the maximum number of annual leave days I can carry forward? | `leave_policy.pdf` (P.1) | ✅ | 44.7% | 78.6% |
| 3 | Do I need to submit a doctor's note for sick leave? | `leave_policy.pdf` (P.2) | ✅ | 12.3% | 37.9% |
| 4 | How much paid maternity leave do female employees receive? | `leave_policy.pdf` (P.2) | ✅ | 41.0% | 79.3% |
| 5 | How many days of paid bereavement leave do I get for immediate family? | `leave_policy.pdf` (P.3) | ✅ | 43.0% | 86.0% |
| 6 | What is the standard hardware kit allocated to employees upon joining? | `it_policy.pdf` (P.1) | ✅ | 33.0% | 51.6% |
| 7 | How often does the company replace laptops? | `it_policy.pdf` (P.1) | ✅ | 41.4% | 79.8% |
| 8 | Am I allowed to install software myself on my company laptop? | `it_policy.pdf` (P.2) | ✅ | 43.5% | 75.1% |
| 9 | What are the rules for choosing a password for my corporate accounts? | `it_policy.pdf` (P.2) | ✅ | 44.4% | 62.1% |
| 10 | Within how much time should a lost or stolen laptop be reported? | `it_policy.pdf` (P.3) | ✅ | 45.6% | 80.4% |
| 11 | Can I book a business class flight for domestic business travel? | `expense_policy.pdf` (P.1) | ✅ | 40.0% | 69.8% |
| 12 | What is the domestic hotel reimbursement rate limit per night? | `expense_policy.pdf` (P.1) | ✅ | 31.2% | 79.4% |
| 13 | What is the international meal per diem rate? | `expense_policy.pdf` (P.2) | ✅ | 32.4% | 77.5% |
| 14 | What is the deadline for submitting expense reports in Concur? | `expense_policy.pdf` (P.2) | ✅ | 44.8% | 73.5% |
| 15 | For what transaction amount is an itemized receipt mandatory? | `expense_policy.pdf` (P.2) | ✅ | 31.8% | 70.5% |
| 16 | How does the company handle conflicts of interest? | `code_of_conduct.pdf` (P.1) | ✅ | 30.1% | 44.9% |
| 17 | Can I accept a gift worth $100 from a supplier? | `code_of_conduct.pdf` (P.2) | ✅ | 22.8% | 68.8% |
| 18 | How can I report an ethical violation anonymously? | `code_of_conduct.pdf` (P.3) | ✅ | 32.9% | 73.5% |
| 19 | What is the minimum number of days I must work from the office in the hybrid model? | `wfh_policy.pdf` (P.1) | ✅ | 42.9% | 51.0% |
| 20 | How much Internet allowance does the company reimburse per month? | `wfh_policy.pdf` (P.2) | ✅ | 34.5% | 71.5% |
