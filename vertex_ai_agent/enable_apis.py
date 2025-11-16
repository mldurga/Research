#!/usr/bin/env python3
"""
Enable required Google Cloud APIs for Vertex AI deployment
"""

import os
import sys
from google.cloud import storage
from google.oauth2 import service_account
import requests
import json

# Load credentials
credentials_path = "/home/user/Research/vertex_ai_agent/gcp-credentials.json"
project_id = "abiding-circle-478407-i8"

# Load service account credentials
credentials = service_account.Credentials.from_service_account_file(
    credentials_path,
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)

def enable_api(api_name):
    """Enable a Google Cloud API"""
    print(f"Enabling {api_name}...")

    url = f"https://serviceusage.googleapis.com/v1/projects/{project_id}/services/{api_name}:enable"

    # Get access token
    credentials.refresh(requests.Request())
    headers = {
        'Authorization': f'Bearer {credentials.token}',
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers)

    if response.status_code in [200, 409]:  # 200 = success, 409 = already enabled
        print(f"✅ {api_name} enabled successfully")
        return True
    else:
        print(f"⚠️  {api_name}: {response.status_code} - {response.text}")
        return False

def create_bucket(bucket_name, region):
    """Create GCS bucket if it doesn't exist"""
    print(f"\nCreating staging bucket: {bucket_name}")

    try:
        storage_client = storage.Client(
            credentials=credentials,
            project=project_id
        )

        # Check if bucket exists
        try:
            bucket = storage_client.get_bucket(bucket_name)
            print(f"✅ Bucket already exists: gs://{bucket_name}")
            return True
        except:
            pass

        # Create bucket
        bucket = storage_client.bucket(bucket_name)
        bucket.location = region.upper()
        bucket.storage_class = "STANDARD"

        new_bucket = storage_client.create_bucket(bucket)
        print(f"✅ Bucket created: gs://{bucket_name}")
        return True

    except Exception as e:
        print(f"❌ Error creating bucket: {e}")
        return False

def main():
    print("=" * 60)
    print("Enabling Google Cloud APIs and Creating Resources")
    print("=" * 60)
    print(f"Project: {project_id}")
    print(f"Region: asia-south1")
    print()

    # APIs to enable
    apis = [
        "aiplatform.googleapis.com",
        "storage.googleapis.com",
        "serviceusage.googleapis.com",
        "run.googleapis.com",
        "cloudbuild.googleapis.com"
    ]

    print("Enabling required APIs...")
    print()

    success = True
    for api in apis:
        if not enable_api(api):
            success = False

    print()

    # Create staging bucket
    bucket_name = "abiding-circle-478407-i8-vertex-ai-staging"
    if not create_bucket(bucket_name, "asia-south1"):
        success = False

    print()
    print("=" * 60)

    if success:
        print("✅ All APIs enabled and resources created successfully!")
        print()
        print("Ready for Vertex AI deployment!")
        return 0
    else:
        print("⚠️  Some operations had warnings. Check output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
