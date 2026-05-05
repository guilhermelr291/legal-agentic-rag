"""Streamlit document upload and management page.

Provides UI components for:
- File upload with validation (PDF/DOCX/XLSX, max 50MB)
- Document list with status display
- Real-time status polling
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import requests
import streamlit as st

if TYPE_CHECKING:
    from io import BytesIO

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_USER_ID = "test-user-id"

# =============================================================================
# API Client Functions
# =============================================================================


class UploadError(Exception):
    """Exception raised when file upload fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def upload_file(file_bytes: bytes, filename: str, user_id: str = DEFAULT_USER_ID) -> str:
    """Upload a file to the document ingestion API.

    Args:
        file_bytes: Raw file content as bytes.
        filename: Original filename with extension.
        user_id: User identifier for RLS. Defaults to test-user-id.

    Returns:
        Document ID (UUID) assigned to the uploaded document.

    Raises:
        UploadError: If the upload fails with details from the server.

    Example:
        >>> with open("contract.pdf", "rb") as f:
        ...     doc_id = upload_file(f.read(), "contract.pdf")
        ...     print(f"Uploaded: {doc_id}")
    """
    url = f"{API_BASE_URL}/documents/upload"

    files = {
        "file": (filename, file_bytes),
    }

    try:
        response = requests.post(
            url,
            files=files,
            timeout=60,
            headers={
                "X-User-ID": user_id,  # Header for user identification
            },
        )
        response.raise_for_status()
        result = response.json()
        return result["document_id"]

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        try:
            error_data = e.response.json()
            detail = error_data.get("detail", str(e))
        except Exception:
            detail = str(e)

        if status_code == 400:
            raise UploadError(f"Invalid file: {detail}", status_code) from e
        if status_code == 413:
            raise UploadError(f"File too large: {detail}", status_code) from e
        if status_code >= 500:
            raise UploadError(f"Server error: {detail}", status_code) from e
        raise UploadError(f"Upload failed: {detail}", status_code) from e

    except requests.exceptions.ConnectionError as e:
        raise UploadError(
            "Cannot connect to API server. Is the backend running?",
            None,
        ) from e

    except requests.exceptions.Timeout as e:
        raise UploadError("Upload timed out. Please try again.", None) from e

    except requests.exceptions.RequestException as e:
        raise UploadError(f"Upload failed: {e}", None) from e


def get_document_status(document_id: str, user_id: str = DEFAULT_USER_ID) -> dict:
    """Get the current processing status of a document.

    Args:
        document_id: UUID of the document.
        user_id: User identifier for RLS.

    Returns:
        Dictionary with status information.

    Raises:
        UploadError: If the request fails.
    """
    url = f"{API_BASE_URL}/documents/{document_id}/status"

    try:
        response = requests.get(
            url,
            timeout=10,
            headers={"X-User-ID": user_id},
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        raise UploadError(f"Failed to get status: {e}") from e


def list_documents(user_id: str = DEFAULT_USER_ID, status_filter: str | None = None) -> list[dict]:
    """List all documents for the current user.

    Args:
        user_id: User identifier for RLS.
        status_filter: Optional status to filter by.

    Returns:
        List of document dictionaries.

    Raises:
        UploadError: If the request fails.
    """
    url = f"{API_BASE_URL}/documents"
    params = {}
    if status_filter:
        params["status_filter"] = status_filter

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10,
            headers={"X-User-ID": user_id},
        )
        response.raise_for_status()
        result = response.json()
        return result.get("documents", [])

    except requests.exceptions.RequestException as e:
        raise UploadError(f"Failed to list documents: {e}") from e


# =============================================================================
# Validation Functions
# =============================================================================


def validate_file_extension(filename: str) -> tuple[bool, str]:
    """Validate that file has an allowed extension.

    Args:
        filename: Name of the file to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    import os

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed_str = ", ".join(ALLOWED_EXTENSIONS)
        return False, f"Invalid file type '{ext}'. Allowed: {allowed_str}"
    return True, ""


def validate_file_size(file_size: int) -> tuple[bool, str]:
    """Validate that file size is within limits.

    Args:
        file_size: Size in bytes.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        return False, f"File too large ({size_mb:.1f} MB). Maximum: {MAX_FILE_SIZE_MB} MB"
    return True, ""


# =============================================================================
# UI Components
# =============================================================================


def render_upload_section() -> None:
    """Render the file upload section with validation and progress.

    Displays a file uploader widget that accepts PDF/DOCX/XLSX files,
    validates file size (50MB max), and provides upload feedback.
    """
    st.header("Upload Document")
    st.markdown("Upload legal documents (PDF, DOCX, XLSX) for AI analysis.")

    # File uploader widget
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["pdf", "docx", "xlsx"],
        help=f"Maximum file size: {MAX_FILE_SIZE_MB} MB",
        key="document_uploader",
    )

    if uploaded_file is None:
        st.info("Select a file to upload")
        return

    # Display file details
    file_size = len(uploaded_file.getvalue())
    size_mb = file_size / (1024 * 1024)

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Filename:** {uploaded_file.name}")
    with col2:
        st.write(f"**Size:** {size_mb:.2f} MB")

    # Client-side validation
    ext_valid, ext_error = validate_file_extension(uploaded_file.name)
    if not ext_valid:
        st.error(ext_error)
        return

    size_valid, size_error = validate_file_size(file_size)
    if not size_valid:
        st.error(size_error)
        return

    st.success("File validation passed")

    # Upload button with progress
    if st.button("Upload Document", type="primary", key="upload_button"):
        _perform_upload(uploaded_file)


def _perform_upload(uploaded_file) -> None:
    """Execute the file upload with progress indication.

    Args:
        uploaded_file: Streamlit UploadedFile object.
    """
    progress_bar = st.progress(0, text="Preparing upload...")

    try:
        # Read file content
        progress_bar.progress(25, text="Reading file...")
        file_bytes = uploaded_file.getvalue()

        # Upload
        progress_bar.progress(50, text="Uploading to server...")
        document_id = upload_file(
            file_bytes=file_bytes,
            filename=uploaded_file.name,
        )

        # Complete
        progress_bar.progress(100, text="Upload complete!")
        st.success(f"✅ Document uploaded successfully! ID: `{document_id}`")
        st.info("Processing has started in the background. Check the document list below for status.")

        # Store uploaded document ID for polling
        if "uploaded_docs" not in st.session_state:
            st.session_state.uploaded_docs = []
        st.session_state.uploaded_docs.append({
            "document_id": document_id,
            "filename": uploaded_file.name,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        })

        # Clear the uploader by rerunning
        st.balloons()

    except UploadError as e:
        progress_bar.empty()
        logger.error("Upload failed: %s", e.message)

        if e.status_code == 400:
            st.error(f"❌ {e.message}")
        elif e.status_code == 413:
            st.error(f"❌ {e.message}")
        elif e.status_code and e.status_code >= 500:
            st.error(f"❌ Server error: {e.message}")
        else:
            st.error(f"❌ Upload failed: {e.message}")

    except Exception as e:
        progress_bar.empty()
        logger.exception("Unexpected error during upload")
        st.error(f"❌ Unexpected error: {e}")


def render_status_badge(status: str, processing_time: float | None = None) -> str:
    """Render a status badge with appropriate icon and styling.

    Args:
        status: Document status ('processing', 'ready', 'failed').
        processing_time: Optional processing duration in seconds.

    Returns:
        HTML/markdown formatted status badge.
    """
    if status == "processing":
        if processing_time and processing_time > 120:
            minutes = int(processing_time / 60)
            return f"🔄 Processing for {minutes} minutes"
        return "🔄 Processing"

    if status == "ready":
        return "✅ Ready"

    if status == "failed":
        return "❌ Upload failed. Please try again."

    return f"❓ {status}"


def render_document_list() -> None:
    """Render the document list with status display.

    Shows all user's documents with status badges and metadata.
    """
    st.header("Your Documents")

    try:
        docs = list_documents()

        if not docs:
            st.info("No documents yet. Upload your first document above!")
            return

        # Display as a table-like structure
        for doc in docs:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                with col1:
                    st.write(f"**{doc['filename']}**")
                    st.caption(f"Type: {doc['file_type'].upper()}")

                with col2:
                    status = doc['status']
                    badge = render_status_badge(status)
                    st.write(badge)

                with col3:
                    # Format file size
                    size_bytes = doc.get('file_size', 0)
                    if size_bytes > 1024 * 1024:
                        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                    else:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    st.write(size_str)

                with col4:
                    # Format date
                    updated = doc.get('updated_at', '')
                    if updated:
                        try:
                            dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                            date_str = dt.strftime('%Y-%m-%d %H:%M')
                        except Exception:
                            date_str = str(updated)[:16]
                    else:
                        date_str = "Unknown"
                    st.write(date_str)

                # Add divider
                st.divider()

    except UploadError as e:
        st.error(f"Failed to load documents: {e.message}")

    except Exception as e:
        logger.exception("Error loading document list")
        st.error(f"Error loading documents: {e}")


def poll_status(document_id: str) -> str | None:
    """Poll document status until terminal state is reached.

    Uses Streamlit session state to track polling without blocking.

    Args:
        document_id: UUID of the document to poll.

    Returns:
        Final status if terminal, None if still processing.
    """
    poll_key = f"poll_{document_id}"

    # Check if we should poll this document
    if poll_key not in st.session_state:
        st.session_state[poll_key] = {
            "last_check": None,
            "status": "processing",
        }

    poll_data = st.session_state[poll_key]

    # Only poll every 2 seconds
    now = datetime.now(timezone.utc)
    last_check = poll_data.get("last_check")

    if last_check:
        try:
            last_dt = datetime.fromisoformat(last_check)
            elapsed = (now - last_dt).total_seconds()
            if elapsed < 2:
                return None  # Too soon to poll again
        except Exception:
            pass

    # Perform poll
    try:
        status_info = get_document_status(document_id)
        current_status = status_info.get("status", "unknown")

        poll_data["last_check"] = now.isoformat()
        poll_data["status"] = current_status

        # Terminal states
        if current_status in ("ready", "failed"):
            poll_data["final"] = True
            return current_status

        return None  # Still processing

    except Exception:
        # Silently fail on poll errors, will retry next cycle
        return None


# =============================================================================
# Main Page
# =============================================================================


def main() -> None:
    """Main entry point for the documents page."""
    st.set_page_config(
        page_title="Document Upload",
        page_icon="📄",
        layout="wide",
    )

    st.title("📄 Document Ingestion")
    st.markdown("---")

    # Upload section
    render_upload_section()

    st.markdown("---")

    # Document list section
    render_document_list()


if __name__ == "__main__":
    main()
