import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from packaging.version import Version, InvalidVersion

# Core Configurations for Krava Signer compatibility
REPO_NAME = "Rek's iOSGods Collection"
REPO_IDENTIFIER = "com.reks.iosgods.source"
OUTPUT_FILE = "apps.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def parse_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    return line

def clean_version(version_str):
    if not version_str:
        return "0.0.0"
    version_str = version_str.lower().lstrip('v').split('-').split('+').strip()
    match = re.match(r'^(\d+(?:\.\d+)*)', version_str)
    if match:
        return match.group(1)
    return "0.0.0"

def is_newer(ver1, ver2):
    try:
        return Version(clean_version(ver1)) > Version(clean_version(ver2))
    except InvalidVersion:
        return ver1 > ver2

def normalize_app_name(name):
    clean = re.sub(r'\[.*?\]', '', name)
    clean = clean.lower()
    for word in ['tweaked', 'cracked', 'plus', 'premium', 'watusi', 'uyou', 'mod', 'lrd']:
        clean = clean.replace(word, '')
    clean = re.sub(r'[^a-zA-Z0-9]', '', clean).lower().strip()
    return clean

def merge_external_altstore(url):
    if url.startswith("content-download-egs"):
        url = "https://" + url
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if "apps" in data and isinstance(data["apps"], list):
                source_label = data.get("name", "Source")
                processed_apps = []
                
                print(f"[*] Analyzing {len(data['apps'])} total apps inside {source_label} for iOSGods tags...")
                
                for app in data["apps"]:
                    # Target fields to scan for iOSGods footprint tags
                    dev_name = str(app.get("developerName", "")).lower()
                    desc = str(app.get("localizedDescription", "")).lower()
                    app_name = str(app.get("name", "")).lower()
                    
                    # STRIPIING MECHANIC: Only pass if iOSGods text is discovered
                    if "iosgods" in dev_name or "iosgods" in desc or "iosgods" in app_name:
                        if not app.get("name", "").startswith("["):
                            app["name"] = f"[iOSGods via {source_label}] {app.get('name', 'Unknown')}"
                        processed_apps.append(app)
                        
                print(f"[+] Found and stripped {len(processed_apps)} pure iOSGods modified apps!")
                return processed_apps
    except Exception as e:
        print(f"[-] Skipping target source parsing verification for address {url}: {e}")
    return []

def main():
    all_apps = []
    
    if os.path.exists("repos.txt"):
        with open("repos.txt", "r") as f:
            for line in f:
                target = parse_line(line)
                if not target:
                    continue
                # We skip checking regular non-JSON links for this specific script run
                if target.endswith(".json") or "repo" in target or "source" in target or "cypwn" in target or "egs" in target:
                    all_apps.extend(merge_external_altstore(target))

    # Version lock de-duplication loop
    latest_apps_map = {}
    for app in all_apps:
        norm_name = normalize_app_name(app.get("name", ""))
        if not norm_name:
            continue
            
        current_version = app.get("version", "0.0.0")
        
        if norm_name not in latest_apps_map:
            latest_apps_map[norm_name] = app
        else:
            existing_version = latest_apps_map[norm_name].get("version", "0.0.0")
            if is_newer(current_version, existing_version):
                latest_apps_map[norm_name] = app

    final_apps = list(latest_apps_map.values())
    final_apps.sort(key=lambda x: x.get("name", "").lower())

    repo_structure = {
        "name": REPO_NAME,
        "identifier": REPO_IDENTIFIER,
        "apps": final_apps
    }
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(repo_structure, f, indent=2)
        
    print(f"[=] Stripping Complete. Final Metrics:")
    print(f"[=] Total iOSGods Apps Extracted: {len(final_apps)}")

if __name__ == "__main__":
    main()
