import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from werkzeug.datastructures import FileStorage
from apps.reports.models import ScanLog
from apps.globals.util import import_content_from_excel
import pandas as pd

def test_5_1_sqlite_fallback_initialization(app, db):
    """
    Test 5.1 - SQLite Fallback Initialization:
    Verify that ScanLog compiled without crashing, proving JSON compatibility.
    """
    # The database fixture already created all tables.
    # We just need to verify we can insert and retrieve a ScanLog with JSON data
    # under the SQLite in-memory database.
    
    log = ScanLog(
        success_count={"instagram": 10},
        failure_count={"tiktok": 2},
        failures={"tiktok": {"user_1": "Not found"}}
    )
    db.session.add(log)
    db.session.commit()
    
    fetched = ScanLog.query.first()
    assert fetched is not None
    assert fetched.success_count["instagram"] == 10
    assert fetched.failure_count["tiktok"] == 2

def test_5_2_excel_upload_type_checking(app, db):
    """
    Test 5.2 - Excel Upload Type Checking:
    Assert .xlsx routes to pd.read_excel and .csv to pd.read_csv.
    """
    # Create mock FileStorage objects
    excel_file = FileStorage(
        stream=BytesIO(b"dummy excel content"),
        filename="test_upload.xlsx",
        name="file"
    )
    
    csv_file = FileStorage(
        stream=BytesIO(b"dummy csv content"),
        filename="test_upload.csv",
        name="file"
    )

    # We patch pandas functions to just return an empty dataframe
    # We also patch 'flash' so it doesn't crash outside request context
    empty_df = pd.DataFrame(columns=["name", "description"])
    
    with app.app_context(), app.test_request_context():
        with patch('pandas.read_excel', return_value=empty_df) as mock_read_excel:
            with patch('pandas.read_csv', return_value=empty_df) as mock_read_csv:
                
                # Test .xlsx
                import_content_from_excel(excel_file, "contents")
                mock_read_excel.assert_called_once()
                mock_read_csv.assert_not_called()
                
                mock_read_excel.reset_mock()
                mock_read_csv.reset_mock()
                
                # Test .csv
                import_content_from_excel(csv_file, "contents")
                mock_read_csv.assert_called_once()
                mock_read_excel.assert_not_called()
