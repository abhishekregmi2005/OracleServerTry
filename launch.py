#!/usr/bin/env python3
import oci
import json
import requests
from oci.signer import Signer
import time
import random
import os
import sys

key_content = os.environ["OCI_KEY_CONTENT"]
config = {
    "user": os.environ["OCI_USER_OCID"],
    "fingerprint": os.environ["OCI_FINGERPRINT"],
    "tenancy": os.environ["OCI_TENANCY_OCID"],
    "region": os.environ.get("OCI_REGION", "us-chicago-1"),
    "key_content": key_content,
}

signer = Signer(
    tenancy=config["tenancy"],
    user=config["user"],
    fingerprint=config["fingerprint"],
    private_key_content=key_content,
)

ssh_key = os.environ["SSH_PUBLIC_KEY"].strip()

url = "https://iaas.us-chicago-1.oraclecloud.com/20160918/instances"

ADS = [
    "eqhO:US-CHICAGO-1-AD-1",
    "eqhO:US-CHICAGO-1-AD-2",
    "eqhO:US-CHICAGO-1-AD-3",
]

def build_payload(ad):
    return json.dumps({
        "availabilityDomain": ad,
        "compartmentId": os.environ["OCI_COMPARTMENT_ID"],
        "shape": "VM.Standard.A1.Flex",
        "shapeConfig": {
            "ocpus": 4,
            "memoryInGBs": 24
        },
        "sourceDetails": {
            "sourceType": "image",
            "imageId": "ocid1.image.oc1.us-chicago-1.aaaaaaaaqzxgc5f4hbxsoi4mhogsodroy5wgnvxcpuwpt77gt4wl3a3x6m2q"
        },
        "createVnicDetails": {
            "subnetId": os.environ["OCI_SUBNET_ID"],
            "assignPublicIp": True
        },
        "metadata": {
            "ssh_authorized_keys": ssh_key
        },
        "displayName": "AI-Dev-Server"
    })

max_attempts = int(os.environ.get("MAX_ATTEMPTS", "10"))
retry_seconds = int(os.environ.get("RETRY_SECONDS", "45"))

print("Starting sniper loop (rotating all 3 ADs)...")
for attempt in range(1, max_attempts + 1):
    ad = ADS[(attempt - 1) % len(ADS)]
    try:
        resp = requests.post(
            url,
            data=build_payload(ad),
            headers={"Content-Type": "application/json"},
            auth=signer
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"SUCCESS on {ad}! Instance ID: {data['id']}")
            sys.exit(0)
        else:
            err = resp.json()
            code = err.get("code", "")
            message = err.get("message", "")
            print(f"[{ad}] Attempt {attempt}/{max_attempts} - {resp.status_code} {code}: {message}")
            if resp.status_code == 429:
                print("Rate limited. Waiting 5 minutes...")
                time.sleep(300)
            else:
                wait = random.randint(retry_seconds - 10, retry_seconds + 10)
                print(f"Retrying in {wait}s...")
                time.sleep(wait)
    except Exception as e:
        print(f"Unexpected error: {e}")
        time.sleep(60)

print(f"No capacity found after {max_attempts} attempts. Will retry on next scheduled run.")
sys.exit(0)
