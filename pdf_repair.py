#!/usr/bin/env python3
"""
PDF Repair Tool

Recursively scans for PDF files in the script directory and attempts to repair
corrupted or damaged PDFs using multiple repair strategies. Results are written
to a human-readable log file.

Repair strategies are attempted in order:
    1. pypdf (Python PDF library)
    2. PyMuPDF (fitz)
    3. qpdf (external command-line tool)
    4. Ghostscript (external command-line tool)

Output:
    repair_report.log: Detailed report of repair attempts and results
    fixed-<original>.pdf: Repaired PDF files saved next to originals
"""

from pathlib import Path
import logging
import shutil
import subprocess
import datetime

# Optional third-party library imports
# These libraries are not required but provide additional repair capabilities
try:
    from pypdf import PdfReader, PdfWriter  # pyright: ignore[reportMissingImports]
except Exception:
    PdfReader = None
    PdfWriter = None

try:
    import fitz  # PyMuPDF  # pyright: ignore[reportMissingImports]
except Exception:
    fitz = None

# ------------------------------------------------------------------------------------
# Logging configuration for console
# ------------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("repair")

# Custom logging handler to capture warnings from PDF libraries
# This allows us to collect warnings generated during repair attempts
# without cluttering the console output
class LogCaptureHandler(logging.Handler):
    def __init__(self, level=logging.WARNING):
        super().__init__(level)
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))


def capture_warnings_for(logger_names, func, *args, **kwargs):
    """
    Execute a function while capturing warnings from specified loggers.
    
    Temporarily attaches custom handlers to the specified loggers to capture
    warning messages without displaying them. Handlers are removed after
    execution regardless of success or failure.
    
    Args:
        logger_names: List of logger names to capture warnings from
        func: Function to execute
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func
        
    Returns:
        Tuple of (result, warnings, exception) where:
            - result: Return value of func (None if exception occurred)
            - warnings: List of captured warning messages
            - exception: Exception object if one occurred, None otherwise
    """
    handlers = {}
    try:
        # Attach capture handlers to specified loggers
        for name in logger_names:
            log = logging.getLogger(name)
            handler = LogCaptureHandler()
            formatter = logging.Formatter("%(levelname)s: %(message)s")
            handler.setFormatter(formatter)
            log.addHandler(handler)
            handlers[name] = handler

        # Execute the function and capture any exceptions
        try:
            result = func(*args, **kwargs)
            exc = None
        except Exception as e:
            result = None
            exc = e
    finally:
        # Always remove handlers, even if an exception occurred
        for name, handler in handlers.items():
            logging.getLogger(name).removeHandler(handler)

    # Collect all captured warnings
    warnings = []
    for h in handlers.values():
        warnings.extend(h.records)

    return result, warnings, exc

# ------------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------------

def safe_output_path(src: Path) -> Path:
    """
    Generate a safe output path for repaired PDF files.
    
    If a file with the default name already exists, appends a counter
    to ensure uniqueness (e.g., fixed-document-1.pdf, fixed-document-2.pdf).
    
    Args:
        src: Source PDF file path
        
    Returns:
        Path to the output file that does not conflict with existing files
    """
    dst = src.with_name(f"fixed-{src.name}")
    counter = 1
    while dst.exists():
        dst = src.with_name(f"fixed-{src.stem}-{counter}{src.suffix}")
        counter += 1
    return dst

def count_pages(path: Path):
    """
    Attempt to count pages in a PDF file using available libraries.
    
    Args:
        path: Path to the PDF file
        
    Returns:
        Number of pages if successful, None otherwise
    """
    # Attempt to count pages using pypdf library
    if PdfReader:
        try:
            r = PdfReader(str(path), strict=False)
            return len(r.pages)
        except Exception:
            pass

    # Fallback to PyMuPDF if pypdf is unavailable or fails
    if fitz:
        try:
            doc = fitz.open(str(path))
            pages = doc.page_count
            doc.close()
            return pages
        except Exception:
            pass

    return None

# ------------------------------------------------------------------------------------
# Repair Strategies
# ------------------------------------------------------------------------------------

def repair_with_pypdf(src: Path, dst: Path) -> bool:
    """
    Repair a PDF file using the pypdf library.
    
    Reads all pages from the source PDF and writes them to a new file,
    preserving metadata if available. This process can fix certain types
    of corruption by rebuilding the PDF structure.
    
    Args:
        src: Path to the source (corrupted) PDF file
        dst: Path where the repaired PDF will be written
        
    Returns:
        True if repair was successful
        
    Raises:
        RuntimeError: If pypdf library is not available
    """
    if PdfReader is None or PdfWriter is None:
        raise RuntimeError("pypdf not available")
    reader = PdfReader(str(src), strict=False)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    # Attempt to preserve metadata if present
    if getattr(reader, "metadata", None):
        try:
            writer.add_metadata(reader.metadata)
        except Exception:
            pass
    with open(dst, "wb") as f:
        writer.write(f)
    return True

def repair_with_pymupdf(src: Path, dst: Path) -> bool:
    """
    Repair a PDF file using PyMuPDF (fitz).
    
    Uses aggressive garbage collection and deflation to rebuild the PDF
    structure, which can repair various types of corruption.
    
    Args:
        src: Path to the source (corrupted) PDF file
        dst: Path where the repaired PDF will be written
        
    Returns:
        True if repair was successful
        
    Raises:
        RuntimeError: If PyMuPDF library is not available
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF not available")
    doc = fitz.open(str(src))
    # garbage=4: maximum garbage collection, deflate=True: compress streams
    doc.save(str(dst), garbage=4, deflate=True, incremental=False)
    doc.close()
    return True

def repair_with_qpdf(src: Path, dst: Path) -> bool:
    """
    Repair a PDF file using qpdf command-line tool.
    
    The --linearize flag rebuilds the PDF structure and can repair
    corruption issues. qpdf must be installed on the system.
    
    Args:
        src: Path to the source (corrupted) PDF file
        dst: Path where the repaired PDF will be written
        
    Returns:
        True if repair was successful
        
    Raises:
        RuntimeError: If qpdf is not installed or not found in PATH
        subprocess.CalledProcessError: If qpdf command fails
    """
    qpdf = shutil.which("qpdf")
    if not qpdf:
        raise RuntimeError("qpdf not installed")
    # --linearize: rebuild PDF structure for better compatibility
    subprocess.run([qpdf, "--linearize", str(src), str(dst)],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return True

def repair_with_ghostscript(src: Path, dst: Path) -> bool:
    """
    Repair a PDF file using Ghostscript command-line tool.
    
    Ghostscript re-renders the PDF, which can fix corruption by completely
    rebuilding the file structure. This is often the most effective but also
    the slowest repair method.
    
    Args:
        src: Path to the source (corrupted) PDF file
        dst: Path where the repaired PDF will be written
        
    Returns:
        True if repair was successful
        
    Raises:
        RuntimeError: If Ghostscript is not installed or not found in PATH
        subprocess.CalledProcessError: If Ghostscript command fails
    """
    gs = shutil.which("gs") or shutil.which("ghostscript")
    if not gs:
        raise RuntimeError("ghostscript not installed")
    # Ghostscript arguments:
    # -dNOPAUSE/-dBATCH: non-interactive mode
    # -dSAFER: restricted file operations for security
    # -sDEVICE=pdfwrite: output PDF format
    # -dCompatibilityLevel=1.7: PDF version compatibility
    # -dPDFSETTINGS=/prepress: high-quality settings for prepress
    args = [
        gs,
        "-dNOPAUSE", "-dBATCH", "-dSAFER",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.7",
        "-dPDFSETTINGS=/prepress",
        "-sOutputFile=" + str(dst),
        str(src)
    ]
    subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return True

STRATEGIES = [
    ("pypdf", repair_with_pypdf, ["pypdf", "pypdf._reader"]),
    ("pymupdf", repair_with_pymupdf, ["fitz"]),
    ("qpdf", repair_with_qpdf, []),
    ("ghostscript", repair_with_ghostscript, []),
]

# ------------------------------------------------------------------------------------
# Main per-file logic
# ------------------------------------------------------------------------------------

def try_repair_file(src: Path):
    """
    Attempt to repair a single PDF file using multiple strategies.
    
    Tries each repair strategy in order until one succeeds. Collects warnings
    and errors from each attempt for reporting purposes.
    
    Args:
        src: Path to the PDF file to repair
        
    Returns:
        Dictionary containing repair results with keys:
            - original: Original file path
            - repaired: Path to repaired file (if successful)
            - status: "REPAIRED" or "FAILED"
            - strategy: Name of successful strategy (if repaired)
            - warnings: List of warning messages
            - error: Error message (if all strategies failed)
            - pages_before: Page count before repair
            - pages_after: Page count after repair
    """
    result = {
        "original": str(src),
        "repaired": "",
        "status": "",
        "strategy": "",
        "warnings": [],
        "error": "",
        "pages_before": None,
        "pages_after": None,
    }

    result["pages_before"] = count_pages(src)
    dst = safe_output_path(src)

    # Try each repair strategy in order until one succeeds
    errors = []
    for strat_name, strat_func, loggers in STRATEGIES:

        def run():
            return strat_func(src, dst)

        repaired, warnings, exc = capture_warnings_for(loggers, run)

        if warnings:
            result["warnings"].extend(warnings)

        # If repair succeeded, record results and return
        if exc is None and repaired:
            result["status"] = "REPAIRED"
            result["strategy"] = strat_name
            result["repaired"] = str(dst)
            result["pages_after"] = count_pages(dst)
            return result

        # Record error for this strategy attempt
        if exc is not None:
            errors.append(f"{strat_name}: {type(exc).__name__}: {exc}")

    # All strategies failed - combine all error messages
    if errors:
        result["error"] = "All strategies failed. " + "; ".join(errors)
    else:
        result["error"] = "All strategies failed (no exceptions recorded)"
    
    result["status"] = "FAILED"
    return result

# ------------------------------------------------------------------------------------
# Logging to .log file
# ------------------------------------------------------------------------------------

def write_log_report(results, log_path: Path):
    """
    Write a human-readable repair report to a log file.
    
    Creates a formatted report containing the status, strategy used, warnings,
    and errors for each PDF file that was processed.
    
    Args:
        results: List of result dictionaries from try_repair_file()
        log_path: Path where the log file should be written
    """
    with open(log_path, "w", encoding="utf-8") as f:
        timestamp = datetime.datetime.now().isoformat()
        f.write(f"PDF Repair Report — {timestamp}\n")
        f.write("=" * 80 + "\n\n")

        for r in results:
            f.write(f"FILE: {r['original']}\n")
            f.write(f"  Status:       {r['status']}\n")
            f.write(f"  Strategy:     {r['strategy']}\n")
            f.write(f"  Repaired To:  {r['repaired']}\n")
            f.write(f"  Pages Before: {r['pages_before']}\n")
            f.write(f"  Pages After:  {r['pages_after']}\n")

            if r["warnings"]:
                f.write("  Warnings:\n")
                for w in r["warnings"]:
                    f.write(f"    - {w}\n")

            if r["error"]:
                f.write(f"  Error: {r['error']}\n")

            f.write("\n" + "-" * 80 + "\n\n")

# ------------------------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------------------------

def check_available_tools():
    """
    Check which repair tools are available on the system.
    
    Returns:
        List of available tool names
    """
    available = []
    
    if PdfReader is not None and PdfWriter is not None:
        available.append("pypdf")
    if fitz is not None:
        available.append("pymupdf")
    if shutil.which("qpdf"):
        available.append("qpdf")
    if shutil.which("gs") or shutil.which("ghostscript"):
        available.append("ghostscript")
    
    return available


def main():
    """
    Main entry point for the PDF repair tool.
    
    Scans the script directory recursively for PDF files, attempts to repair
    each one, and writes a comprehensive report to repair_report.log.
    """
    # Check for available repair tools
    available_tools = check_available_tools()
    if not available_tools:
        logger.error("No PDF repair tools are available!")
        logger.error("")
        logger.error("Please install at least one of the following:")
        logger.error("  Python libraries:")
        logger.error("    pip3 install pypdf")
        logger.error("    pip3 install pymupdf")
        logger.error("  Command-line tools (macOS):")
        logger.error("    brew install qpdf")
        logger.error("    brew install ghostscript")
        logger.error("")
        logger.error("After installing, run this script again.")
        return
    
    logger.info(f"Available repair tools: {', '.join(available_tools)}")
    
    script_dir = Path(__file__).parent.resolve()
    logger.info(f"Scanning directory: {script_dir}")

    # Find all PDF files recursively in the script directory
    pdfs = sorted(script_dir.rglob("*.pdf"))
    if not pdfs:
        logger.info("No PDFs found.")
        return

    results = []
    logger.info(f"Found {len(pdfs)} PDFs. Starting repair...")
    for pdf in pdfs:
        logger.info(f"Processing {pdf}")
        info = try_repair_file(pdf)
        results.append(info)
        logger.info(f"  → {info['status']} (strategy={info['strategy']})")

    # Write comprehensive report to log file
    log_file = script_dir / "repair_report.log"
    write_log_report(results, log_file)
    logger.info(f"\nLog written to: {log_file}\n")


if __name__ == "__main__":
    main()
