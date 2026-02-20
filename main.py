import functions_framework
from src.ingestion.real_time_collector import main

@functions_framework.cloud_event
def gcp_entry_point(cloud_event):
    """
    Entry point for Google Cloud Run (Pub/Sub trigger).
    """
    print(f"Triggered by Cloud Scheduler. Event ID: {cloud_event.get('id')}")
    main()
