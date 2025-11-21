"""Script to load sample genealogy data into the system"""
import requests
import json
import time
from pathlib import Path

API_BASE_URL = "http://localhost:8000/api"

def load_file(file_path: str, source_type: str):
    """Load a JSON file and submit to the API"""
    print(f"\nLoading {file_path}...")

    with open(file_path, 'r') as f:
        data = json.load(f)

    payload = {
        "source_type": source_type,
        "file_name": Path(file_path).name,
        "records": data["records"]
    }

    response = requests.post(f"{API_BASE_URL}/ingest", json=payload)

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Successfully submitted {result['records_submitted']} records")
        print(f"  Job ID: {result['job_id']}")
        return result['job_id']
    else:
        print(f"✗ Error: {response.status_code}")
        print(response.text)
        return None


def check_job_status(job_id: int):
    """Check the status of a processing job"""
    response = requests.get(f"{API_BASE_URL}/jobs/{job_id}")
    if response.status_code == 200:
        return response.json()
    return None


def main():
    print("=" * 60)
    print("GENEALOGY DATA PIPELINE - SAMPLE DATA LOADER")
    print("=" * 60)

    # Data files to load
    data_files = [
        ("sample_data/naturalization_records.json", "naturalization"),
        ("sample_data/immigration_records.json", "immigration"),
        ("sample_data/census_records.json", "census"),
        ("sample_data/obituary_records.json", "obituary"),
        ("sample_data/birth_records.json", "birth"),
    ]

    job_ids = []

    # Load all files
    for file_path, source_type in data_files:
        job_id = load_file(file_path, source_type)
        if job_id:
            job_ids.append(job_id)
        time.sleep(1)  # Brief pause between submissions

    # Wait for processing
    print("\n" + "=" * 60)
    print("MONITORING PROCESSING JOBS")
    print("=" * 60)

    all_complete = False
    max_attempts = 60  # Maximum 2 minutes of polling
    attempts = 0

    while not all_complete and attempts < max_attempts:
        all_complete = True
        attempts += 1

        for job_id in job_ids:
            status = check_job_status(job_id)
            if status:
                if status['status'] == 'failed':
                    print(f"✗ Job {job_id} FAILED: {status.get('error_message', 'Unknown error')}")
                    all_complete = False
                    break
                elif status['status'] not in ['completed']:
                    all_complete = False
                    print(f"Job {job_id}: {status['status']} - {status['records_processed']}/{status['total_records']}")

        if not all_complete:
            time.sleep(2)

    if attempts >= max_attempts:
        print("\n✗ Timeout waiting for jobs to complete")
    else:
        print("\n✓ All jobs completed!")

    # Fetch and display leads
    print("\n" + "=" * 60)
    print("FETCHING LEADS")
    print("=" * 60)

    response = requests.get(f"{API_BASE_URL}/leads?min_score=50")
    if response.status_code == 200:
        leads = response.json()
        print(f"\nFound {len(leads)} leads:\n")

        for lead in leads:
            print(f"📋 {lead['name']}")
            print(f"   Score: {lead['lead_score']}/100 ({lead['data_confidence']} confidence)")
            print(f"   Address: {lead['last_known_address']}")
            print(f"   German Ancestor: {lead['german_ancestor']['name']}")
            print(f"   Born: {lead['german_ancestor']['birth_place']}")
            print(f"   Sources: {lead['sources_count']}")
            print()

    print("=" * 60)
    print("SAMPLE DATA LOADED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
