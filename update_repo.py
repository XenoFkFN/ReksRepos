import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

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

def fetch_github_release(repo_path):
    """Processes clean GitHub paths like owner/repo"""
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
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.lower().endswith(".ipa"):
                    apps.append({
                        "name": name.replace(".ipa", "").replace("-", " ").replace("_", " "),
                        "bundleIdentifier": f"com.github.{repo_path.replace('/', '.')}.{re.sub(r'[^a-zA-Z0-9]', '', name)}".lower(),
                        "version": tag.lstrip('v'),
                        "versionDate": asset.get("updated_at"),
                        "downloadURL": asset.get("browser_download_url"),
                        "localizedDescription": f"Fetched from GitHub release: {repo_path}",
                        "developerName": repo_path.split("/")[0],
                        "size": asset.get("size", 0)
                    })
    except Exception as e:
        print(f"[-] Error processing GitHub API for {repo_path}: {e}")
    return apps

def merge_external_altstore(url):
    """Downloads an existing AltStore JSON source and extracts its apps directly"""
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if "apps" in data and isinstance(data["apps"], list):
                print(f"[+] Successfully extracted {len(data['apps'])} apps from source JSON: {url}")
                return data["apps"]
    except Exception as e:
        print(f"[-] Failed parsing external AltStore JSON framework at {url}: {e}")
    return []

def scrape_html_page(url):
    """Scrapes raw web code to look for direct downloadable .ipa files"""
    apps = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.find_all(['a', 'source', 'iframe'], href=True)
            for link in links:
                href = urljoin(url, link['href'])
                if ".ipa" in href.lower():
                    title = href.split('/')[-1].split('?')[0].replace(".ipa", "").replace("-", " ").replace("_", " ")
                    apps.append({
                        "name": title if len(title) < 40 else "External Web App",
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
    
    # Process target list from repos.txt
    if os.path.exists("repos.txt"):
        with open("repos.txt", "r") as f:
            for line in f:
                target = parse_line(line)
                if not target:
                    continue
                
                # Check 1: Is it a direct link to an existing JSON AltStore repository?
                if target.endswith(".json") or "repo" in target.lower():
                    print(f"[*] Extracting existing AltStore Source: {target}")
                    all_apps.extend(merge_external_altstore(target))
                
                # Check 2: Is it a generic GitHub link?
                elif "github.com/" in target:
                    match = re.search(r"github\.com/([^/]+/[^/]+)", target)
                    if match:
                        clean_path = match.group(1).strip("/")
                        print(f"[*] Processing GitHub Path extraction: {clean_path}")
                        all_apps.extend(fetch_github_release(clean_path))
                
                # Check 3: Is it a clean standard developer/repo path string?
                elif "/" in target and not target.startswith("http"):
                    print(f"[*] Querying GitHub API for Path: {target}")
                    all_apps.extend(fetch_github_release(target))
                    
    # Process legacy targets from urls.txt if available
    if os.path.exists("urls.txt"):
        with open("urls.txt", "r") as f:
            for line in f:
                target = parse_line(line)
                if target:
                    print(f"[*] Web scraping: {target}")
                    all_apps.extend(scrape_html_page(target))

    repo_structure = {
        "name": REPO_NAME,
        "identifier": REPO_IDENTIFIER,
        "apps": all_apps
    }
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(repo_structure, f, indent=2)
    print(f"[=] Master source update complete. Total applications compiled: {len(all_apps)}")

if __name__ == "__main__":
    main()
