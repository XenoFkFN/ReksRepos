import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from packaging.version import Version, InvalidVersion

# Core Configurations
REPO_NAME = "Rek's Repo's"
REPO_IDENTIFIER = "com.reks.repo"
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
    # Extract only the base sequence matching decimal version frameworks
    version_str = version_str.lower().lstrip('v').split('-')[0].split('+')[0].strip()
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
    """Trims down app names to flag equivalent titles with slight variations"""
    clean = re.sub(r'\[.*?\]', '', name)
    clean = clean.lower()
    # Strip common fluff tags used by repository aggregators
    for word in ['tweaked', 'cracked', 'plus', 'premium', 'watusi', 'uyou', 'mod', 'lrd']:
        clean = clean.replace(word, '')
    clean = re.sub(r'[^a-zA-Z0-9]', '', clean).lower().strip()
    return clean

def fetch_github_release(repo_path):
    apps = []
    api_url = f"https://github.com{repo_path}/releases/latest"
    gh_headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "AltStore-Aggregator"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        gh_headers["Authorization"] = f"token {token}"
        
    try:
        res = requests.get(api_url, headers=gh_headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            tag = data.get("tag_name", "1.0.0")
            repo_name_clean = repo_path.split("/")[-1]
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.lower().endswith(".ipa"):
                    apps.append({
                        "name": f"[{repo_name_clean}] " + name.replace(".ipa", "").replace("-", " ").replace("_", " "),
                        "bundleIdentifier": f"com.github.{repo_path.replace('/', '.')}".lower(),
                        "version": tag,
                        "versionDate": asset.get("updated_at"),
                        "downloadURL": asset.get("browser_download_url"),
                        "localizedDescription": f"Fetched from GitHub release: {repo_path}",
                        "developerName": repo_path.split("/"),
                        "size": asset.get("size", 0)
                    })
    except Exception as e:
        print(f"[-] Error processing GitHub API for {repo_path}: {e}")
    return apps

def merge_external_altstore(url):
    # Enforce safe protocol formats
    if url.startswith("content-download-egs"):
        url = "https://" + url
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if "apps" in data and isinstance(data["apps"], list):
                source_label = data.get("name", url.split("//")[-1].split("/")[0])
                processed_apps = []
                for app in data["apps"]:
                    # Inject descriptive organization labels onto the name parameter mapping
                    if not app.get("name", "").startswith("["):
                        app["name"] = f"[{source_label}] {app.get('name', 'Unknown App')}"
                    processed_apps.append(app)
                print(f"[+] Unpacked {len(processed_apps)} apps from JSON target source: {source_label}")
                return processed_apps
    except Exception as e:
        print(f"[-] Skipping target source parsing verification for address {url}: {e}")
    return []

def scrape_html_page(url):
    apps = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.find_all(['a', 'source', 'iframe'], href=True)
            site_label = url.split("//")[-1].split("/")[0]
            for link in links:
                href = urljoin(url, link['href'])
                if ".ipa" in href.lower():
                    title = href.split('/')[-1].split('?')[0].replace(".ipa", "").replace("-", " ").replace("_", " ")
                    apps.append({
                        "name": f"[{site_label}] {title[:30]}",
                        "bundleIdentifier": f"com.scraped.{re.sub(r'[^a-zA-Z0-9]', '', title)}".lower(),
                        "version": "1.0.0",
                        "versionDate": "2026-01-01T00:00:00Z",
                        "downloadURL": href,
                        "localizedDescription": f"Discovered on web platform index:\n{url}",
                        "developerName": "External Host",
                        "size": 0
                    })
    except Exception as e:
        print(f"[-] Error scraping web page layout for {url}: {e}")
    return apps

def main():
    all_apps = []
    
    if os.path.exists("repos.txt"):
        with open("repos.txt", "r") as f:
            for line in f:
                target = parse_line(line)
                if not target:
                    continue
                
                if "iosgods.com/repo" in target:
                    print("[!] Skipping standard jailbreak deb Cydia endpoint link.")
                    continue
                elif target.endswith(".json") or "repo" in target or "source" in target or "cypwn" in target or "egs" in target:
                    all_apps.extend(merge_external_altstore(target))
                elif "github.com/" in target:
                    match = re.search(r"github\.com/([^/]+/[^/]+)", target)
                    if match:
                        all_apps.extend(fetch_github_release(match.group(1).strip("/")))
                elif "/" in target and not target.startswith("http"):
                    all_apps.extend(fetch_github_release(target))
                    
    if os.path.exists("urls.txt"):
        with open("urls.txt", "r") as f:
            for line in f:
                target = parse_line(line)
                if target:
                    all_apps.extend(scrape_html_page(target))

    # Strict Double-Check Deduplication Filtering
    # Aggressively filters based on normalized identifier structures to map unique items
    latest_apps_map = {}
    
    for app in all_apps:
        bid = app.get("bundleIdentifier", "").strip().lower()
        norm_name = normalize_app_name(app.get("name", ""))
        
        if not bid or not norm_name:
            continue
            
        # Target identity mapped down through structural patterns
        match_key = bid if "github" in bid else norm_name
        current_version = app.get("version", "0.0.0")
        
        if match_key not in latest_apps_map:
            latest_apps_map[match_key] = app
        else:
            existing_version = latest_apps_map[match_key].get("version", "0.0.0")
            if is_newer(current_version, existing_version):
                latest_apps_map[match_key] = app

    final_apps = list(latest_apps_map.values())
    final_apps.sort(key=lambda x: x.get("name", "").lower())

    repo_structure = {
        "name": REPO_NAME,
        "identifier": REPO_IDENTIFIER,
        "apps": final_apps
    }
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(repo_structure, f, indent=2)
        
    print(f"[=] Processing complete. Filtered output tracking counts:")
    print(f"[=] Original Raw Aggregate Target Count: {len(all_apps)}")
    print(f"[=] Unique Version-Locked Saved Count: {len(final_apps)}")

if __name__ == "__main__":
    main()
