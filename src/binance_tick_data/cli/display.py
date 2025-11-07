"""Rich display functions for professional CLI output.

This module provides formatted, color-coded output using the Rich library.
Separates presentation logic from business logic for clean architecture.
"""

from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

from .models import (
    DownloadParams,
    DownloadResult,
    StreamParams,
    StreamResult,
    ValidationResult,
    DataSummary,
)


# Create console instance (reused across functions)
console = Console()


# ============================================================================
# Download Display Functions
# ============================================================================

def display_download_info(params: DownloadParams) -> None:
    """
    Display download parameters in a formatted table.

    Args:
        params: Download parameters to display
    """
    console.print("\n[bold cyan]HISTORICAL DATA DOWNLOAD[/bold cyan]\n")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Symbols", ", ".join(params.symbols))
    table.add_row("Start Date", str(params.start_date))
    table.add_row("End Date", str(params.end_date or "today"))
    table.add_row("Days to Download", str(params.days_to_download))

    if params.max_records:
        table.add_row("Max Records", f"{params.max_records:,}")

    table.add_row("Batch Size", str(params.batch_size))
    table.add_row("Destination", params.destination)

    console.print(table)
    console.print()


def display_download_result(result: DownloadResult) -> None:
    """
    Display download results with colors and formatting.

    Args:
        result: Download result to display
    """
    console.print()

    if result.success:
        # Success panel
        console.print(Panel(
            "[bold green]✓ DOWNLOAD COMPLETE[/bold green]",
            border_style="green",
        ))

        # Metrics table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Records Downloaded", f"{result.records_count:,}")
        table.add_row("Duration", f"{result.duration_seconds:.2f} seconds")
        table.add_row("Throughput", f"{result.records_per_second:.0f} records/second")

        if result.symbols_processed:
            table.add_row("Symbols Processed", ", ".join(result.symbols_processed))

        console.print(table)

        # Output path
        console.print(f"\n[cyan]Output:[/cyan] {result.output_path}")

        # Per-symbol breakdown if available
        if result.metadata.get('symbol_counts'):
            console.print("\n[cyan]Per-symbol counts:[/cyan]")
            for symbol, count in result.metadata['symbol_counts'].items():
                console.print(f"  {symbol}: [green]{count:,}[/green] records")

        # Warnings if any
        if result.warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.print(f"  [yellow]⚠[/yellow]  {warning}")

    else:
        # Failure panel
        console.print(Panel(
            "[bold red]✗ DOWNLOAD FAILED[/bold red]",
            border_style="red",
        ))

        console.print(f"\n[red]Error:[/red] {result.error}")

        if result.duration_seconds > 0:
            console.print(f"[dim]Failed after {result.duration_seconds:.2f} seconds[/dim]")

    console.print()


def create_download_progress() -> Progress:
    """
    Create a Rich progress bar for download operations.

    Returns:
        Configured Progress instance

    Example:
        >>> progress = create_download_progress()
        >>> with progress:
        ...     task = progress.add_task("[cyan]Downloading...", total=None)
        ...     # ... perform download ...
        ...     progress.update(task, completed=True)
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    )


# ============================================================================
# Stream Display Functions
# ============================================================================

def display_stream_info(params: StreamParams) -> None:
    """
    Display stream parameters in a formatted table.

    Args:
        params: Stream parameters to display
    """
    console.print("\n[bold cyan]REAL-TIME DATA STREAMING[/bold cyan]\n")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Symbols", ", ".join(params.symbols))
    table.add_row("Buffer Size", str(params.buffer_size))

    if params.max_batches:
        table.add_row("Max Batches", str(params.max_batches))
    else:
        table.add_row("Mode", "Continuous (until Ctrl+C)")

    table.add_row("Destination", params.destination)

    console.print(table)
    console.print("\n[dim]Press Ctrl+C to stop gracefully[/dim]\n")


def display_stream_result(result: StreamResult) -> None:
    """
    Display stream results with colors and formatting.

    Args:
        result: Stream result to display
    """
    console.print()

    if result.success:
        # Success panel
        console.print(Panel(
            "[bold green]✓ STREAM COMPLETED[/bold green]",
            border_style="green",
        ))

        # Metrics table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Batches Processed", str(result.batches_processed))
        table.add_row("Approximate Records", f"{result.records_count:,}")
        table.add_row("Duration", f"{result.duration_seconds:.2f} seconds")

        console.print(table)

        # Output path
        if result.output_path:
            console.print(f"\n[cyan]Output:[/cyan] {result.output_path}")

        # Warnings if any
        if result.warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.print(f"  [yellow]⚠[/yellow]  {warning}")

    else:
        # Failure panel
        console.print(Panel(
            "[bold red]✗ STREAM FAILED[/bold red]",
            border_style="red",
        ))

        console.print(f"\n[red]Error:[/red] {result.error}")

        if result.batches_processed > 0:
            console.print(f"\n[dim]Processed {result.batches_processed} batches before failure[/dim]")

    console.print()


def display_batch_update(batch_number: int, timestamp: str) -> None:
    """
    Display a batch processing update.

    Args:
        batch_number: Current batch number
        timestamp: Timestamp of batch processing
    """
    console.print(f"[cyan]Batch {batch_number}[/cyan] processed at [dim]{timestamp}[/dim]")


# ============================================================================
# General Display Functions
# ============================================================================

def display_error(message: str, details: str = None) -> None:
    """
    Display an error message with optional details.

    Args:
        message: Main error message
        details: Optional detailed error information
    """
    console.print(f"\n[bold red]Error:[/bold red] {message}")
    if details:
        console.print(f"[dim]{details}[/dim]")
    console.print()


def display_warning(message: str) -> None:
    """
    Display a warning message.

    Args:
        message: Warning message
    """
    console.print(f"[yellow]⚠ Warning:[/yellow] {message}")


def display_info(message: str) -> None:
    """
    Display an informational message.

    Args:
        message: Info message
    """
    console.print(f"[cyan]ℹ[/cyan] {message}")


def display_success(message: str) -> None:
    """
    Display a success message.

    Args:
        message: Success message
    """
    console.print(f"[green]✓[/green] {message}")


def display_next_steps(steps: list[str]) -> None:
    """
    Display suggested next steps after an operation.

    Args:
        steps: List of next step descriptions
    """
    console.print("\n[bold cyan]Next steps:[/bold cyan]")
    for i, step in enumerate(steps, 1):
        console.print(f"  {i}. {step}")
    console.print()


# ============================================================================
# Progress Context Manager
# ============================================================================

class DownloadProgressManager:
    """
    Context manager for download progress display.

    Example:
        >>> with DownloadProgressManager() as progress:
        ...     for symbol in symbols:
        ...         progress.update(f"Downloading {symbol}...")
        ...         # ... download symbol ...
    """

    def __init__(self):
        self.progress = create_download_progress()
        self.task = None

    def __enter__(self):
        self.progress.__enter__()
        self.task = self.progress.add_task("[cyan]Downloading...", total=None)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update(self, description: str):
        """Update progress description."""
        if self.task is not None:
            self.progress.update(self.task, description=f"[cyan]{description}[/cyan]")


# ============================================================================
# Validation Display Functions
# ============================================================================

def display_validation_result(result: ValidationResult) -> None:
    """
    Display validation results with colors and formatting.

    Args:
        result: Validation result to display
    """
    console.print()

    if result.success:
        # Determine overall status
        if result.has_issues:
            status_color = "yellow"
            status_icon = "⚠"
            status_text = "VALIDATION COMPLETE - ISSUES FOUND"
        else:
            status_color = "green"
            status_icon = "✓"
            status_text = "VALIDATION COMPLETE - NO ISSUES"

        console.print(Panel(
            f"[bold {status_color}]{status_icon} {status_text}[/bold {status_color}]",
            border_style=status_color,
        ))

        # Summary table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value")

        table.add_row("Symbols Checked", str(len(result.symbols_checked)))
        table.add_row("Total Records", f"{result.total_records:,}")
        table.add_row("Duplicates Found", 
                     f"[red]{result.duplicate_count:,}[/red]" if result.duplicate_count > 0 
                     else "[green]0[/green]")
        table.add_row("Gaps Found",
                     f"[yellow]{result.gap_count}[/yellow]" if result.gap_count > 0
                     else "[green]0[/green]")
        table.add_row("Quality Score", 
                     f"[green]{result.quality_score:.1f}%[/green]" if result.quality_score >= 95
                     else f"[yellow]{result.quality_score:.1f}%[/yellow]")
        table.add_row("Duration", f"{result.duration_seconds:.2f} seconds")

        console.print(table)

        # Show issues if any
        if result.issues:
            console.print(f"\n[bold yellow]Issues Found:[/bold yellow]")
            for issue in result.issues[:20]:  # Limit to first 20
                issue_type = issue.get('type', 'unknown')
                symbol = issue.get('symbol', 'N/A')
                message = issue.get('message', 'No details')
                
                if issue_type == "duplicates":
                    console.print(f"  [red]•[/red] {symbol}: {message}")
                elif issue_type == "gap":
                    gap_hours = issue.get('gap_hours', 0)
                    console.print(f"  [yellow]•[/yellow] {symbol}: Gap of {gap_hours:.1f} hours")
                else:
                    console.print(f"  [dim]•[/dim] {symbol}: {message}")

            if len(result.issues) > 20:
                console.print(f"\n[dim]... and {len(result.issues) - 20} more issues[/dim]")

        # Symbols checked
        if result.symbols_checked:
            console.print(f"\n[cyan]Symbols validated:[/cyan] {', '.join(result.symbols_checked)}")

    else:
        # Failure panel
        console.print(Panel(
            "[bold red]✗ VALIDATION FAILED[/bold red]",
            border_style="red",
        ))

        if result.issues:
            for issue in result.issues:
                console.print(f"[red]Error:[/red] {issue.get('message', 'Unknown error')}")

    console.print()


# ============================================================================
# List Data Display Functions
# ============================================================================

def display_data_list(summaries: List[DataSummary], summary_mode: bool = False) -> None:
    """
    Display list of available data.

    Args:
        summaries: List of data summaries to display
        summary_mode: If True, show condensed summary view
    """
    console.print()

    if not summaries:
        console.print("[yellow]No data found in database[/yellow]\n")
        return

    if summary_mode:
        # Summary view - compact table
        console.print("[bold cyan]DATA SUMMARY[/bold cyan]\n")

        table = Table(show_header=True, box=None)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Records", justify="right")
        table.add_column("Date Range")
        table.add_column("Size", justify="right")

        total_records = 0
        total_size = 0

        for summary in summaries:
            total_records += summary.record_count
            total_size += summary.size_bytes

            date_range = "N/A"
            if summary.start_date and summary.end_date:
                date_range = f"{summary.start_date} to {summary.end_date}"

            table.add_row(
                summary.symbol,
                f"{summary.record_count:,}",
                date_range,
                f"{summary.size_mb:.1f} MB",
            )

        console.print(table)

        # Totals
        console.print()
        console.print(f"[bold]Total:[/bold] {len(summaries)} symbols, "
                     f"{total_records:,} records, "
                     f"{total_size / (1024 * 1024):.1f} MB")

    else:
        # Detailed view - one panel per symbol
        console.print(f"[bold cyan]AVAILABLE DATA ({len(summaries)} symbols)[/bold cyan]\n")

        for summary in summaries:
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Key", style="cyan", width=15)
            table.add_column("Value", style="white")

            table.add_row("Symbol", f"[bold]{summary.symbol}[/bold]")
            table.add_row("Records", f"{summary.record_count:,}")
            
            if summary.start_date:
                table.add_row("Start Date", str(summary.start_date))
            if summary.end_date:
                table.add_row("End Date", str(summary.end_date))
            if summary.start_date and summary.end_date:
                table.add_row("Days of Data", str(summary.days_of_data))
            
            table.add_row("Size", f"{summary.size_mb:.1f} MB")
            
            if summary.last_updated:
                table.add_row("Last Updated", summary.last_updated.strftime("%Y-%m-%d %H:%M:%S"))

            console.print(table)
            console.print()

    console.print()
