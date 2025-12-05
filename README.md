# pdf-repair

A Python-based utility for **batch repairing PDF files**, designed to recursively scan directories, attempt multiple repair strategies, and generate both repaired PDF outputs and a detailed log report.

This tool is useful for restoring corrupted, damaged, or partially unreadable PDFs in bulk without manual intervention.

---

## ✨ Features

- 🔍 **Recursive directory scanning**  
  Automatically finds all `.pdf` files starting from the script’s directory.

- 🛠️ **Multi-strategy repair attempts**  
  Sequentially tries multiple recovery methods (e.g., `pypdf`, fallback strategies).

- 📄 **Auto-generated repair report**  
  Creates a `repair_report.log` summarizing:
  - File path  
  - Status (success, skipped, failed)  
  - Repair strategy used  
  - Error messages (if any)

- 📁 **Repaired output files**  
  Successful repairs are saved as:  
  `fixed-<original_name>.pdf`

- 🔐 **Non-destructive**  
  Original files are never overwritten.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Install dependencies:

```bash
pip install pypdf
```

---

## ▶️ Usage

Place the script in the directory containing PDFs you want to repair, then run:

```bash
python pdf_repair.py
```

The script will:

1. Search recursively for all PDFs  
2. Attempt multiple repair strategies  
3. Log results to `repair_report.log`  
4. Write repaired files prefixed with `fixed-`

---

## 📘 Example Log Output

`repair_report.log`:

```
file: ./docs/sample1.pdf
status: success
strategy: pypdf_reader
notes: Repaired successfully

file: ./archive/broken.pdf
status: failed
strategy: fallback
error: Could not parse xref table
```

---

## 🧩 Project Structure

```
pdf-batch-repair/
│
├── pdf_repair.py        # Main repair script
├── repair_report.log    # Generated after each run
└── README.md            # Project documentation
```

---

## 🛡️ Error Handling & Reporting

The script gracefully handles:

- Corrupted or malformed PDFs  
- Permission issues  
- Empty or zero-byte files  
- Unsupported PDF structures  

All failures and warnings are logged for review.

---

## 📄 License

MIT
