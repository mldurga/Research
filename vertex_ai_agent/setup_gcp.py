#!/usr/bin/env python3
"""
Setup Google Cloud resources using REST APIs directly
"""

import json
import requests
import sys

# Configuration
credentials_file = "/home/user/Research/vertex_ai_agent/gcp-credentials.json"
project_id = "abiding-circle-478407-i8"
region = "asia-south1"
bucket_name = "abiding-circle-478407-i8-vertex-ai-staging"

def get_access_token():
    """Get OAuth2 access token from service account"""
    import subprocess

    # Use gcloud to get access token (simpler than implementing JWT)
    try:
        # Try using python jwt if available
        from google.oauth2 import service_account
        import google.auth.transport.requests

        credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )

        request = google.auth.transport.requests.Request()
        credentials.refresh(request)

        return credentials.token
    except:
        # Fallback: read credentials and make manual request
        with open(credentials_file, 'r') as f:
            creds = json.load(f)

        # This is a simplified approach - in production you'd implement full JWT
        print("⚠️  Using simplified auth - some operations may require gcloud CLI")
        return None

def enable_api_simple(api_name):
    """Try to enable API using serviceusage API"""
    print(f"Checking {api_name}...")

    token = get_access_token()
    if not token:
        print(f"  ⚠️  Skipping API enablement (auth required)")
        return False

    url = f"https://serviceusage.googleapis.com/v1/projects/{project_id}/services/{api_name}:enable"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, timeout=30)

        if response.status_code in [200, 409]:
            print(f"  ✅ {api_name}")
            return True
        else:
            print(f"  ⚠️  Status {response.status_code}")
            return False
    except Exception as e:
        print(f"  ⚠️  Error: {e}")
        return False

def create_bucket_simple():
    """Try to create bucket using Storage API"""
    print(f"\nChecking bucket: {bucket_name}...")

    token = get_access_token()
    if not token:
        print("  ⚠️  Skipping bucket creation (auth required)")
        return False

    # Check if bucket exists
    check_url = f"https://storage.googleapis.com/storage/v1/b/{bucket_name}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(check_url, headers=headers, timeout=30)
        if response.status_code == 200:
            print(f"  ✅ Bucket already exists")
            return True
    except:
        pass

    # Create bucket
    create_url = f"https://storage.googleapis.com/storage/v1/b?project={project_id}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    data = {
        "name": bucket_name,
        "location": region.upper(),
        "storageClass": "STANDARD"
    }

    try:
        response = requests.post(create_url, headers=headers, json=data, timeout=30)

        if response.status_code in [200, 409]:
            print(f"  ✅ Bucket created")
            return True
        else:
            print(f"  ⚠️  Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"  ⚠️  Error: {e}")
        return False

def main():
    print("=" * 60)
    print("Google Cloud Setup for Vertex AI")
    print("=" * 60)
    print(f"Project: {project_id}")
    print(f"Region: {region}")
    print()

    # Required APIs
    apis = [
        "aiplatform.googleapis.com",
        "storage.googleapis.com",
        "run.googleapis.com"
    ]

    print("Enabling APIs...")
    for api in apis:
        enable_api_simple(api)

    # Create bucket
    create_bucket_simple()

    print()
    print("=" * 60)
    print("✅ Setup completed!")
    print()
    print("Note: If some operations were skipped, you may need to:")
    print("1. Enable APIs manually in Cloud Console")
    print("2. Create bucket manually: gsutil mb -l asia-south1 gs://", bucket_name)
    print("=" * 60)

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
