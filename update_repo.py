import os
import json
import re
import requests
from bs4 import BeautifulSoup

# Configuration
REPO_NAME = "My Custom Sideload Source"
REPO_IDENTIFIER = "com.custom.sideload.source"
OUTPUT_FILE = "apps.json"

def get_github_releases(repo_path):
    apps = []
    api_url = f"https://github.com{repo_path}/releases/latest"
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    # Optional: Add GitHub Token if running into rate limits
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
        
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code != 200:
            print(f"[-] Failed to fetch GitHub repo {repo_path}: {response.status_code}")
            return apps
            
        data = response.json()
        tag_name = data.get("tag_name", "1.0.0")
        body = data.get("body", "No description provided.")
        
        for asset in data.get("assets", []):
            asset_name = asset.get("name", "")
            if asset_name.endswith(".ipa"):
                download_url = asset.get("browser_download_url")
                # Format name safely
                app_title = asset_name.replace(".ipa", "").replace("-", " ").replace("_", " ")
                app_id = f"{repo_path.replace('/', '.')}.{re.sub(r'[^a-zA-Z0-9]', '', asset_name.split('.')[0])}".lower()
                
                apps.append({
                    "name": app_title,
                    "bundleIdentifier": app_id,
                    "version": tag_name.lstrip('v'),
                    "versionDate": asset.get("updated_at"),
                    "downloadURL": download_url,
                    "localizedDescription": f"Fetched from GitHub release: {repo_path}\n\n{body[:200]}...",
                    "developerName": repo_path.split("/")[0],
                    "size": asset.get("size", 0)
                })
    except Exception as e:
        print(f"[-] Error parsing GitHub repo {repo_path}: {e}")
    return apps

def scrape_custom_urls(url):
    apps = []
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"})
        if response.status_code != 200:
            print(f"[-] Failed to scrape URL {url}: {response.status_code}")
            return apps
            
        soup = BeautifulSoup(response.text, 'html.parser')
        # Find all absolute and relative hyperlinks
        links = soup.find_all('a', href=True)
        
        for index, link in enumerate(links):
            href = link['href']
            # Convert relative pathing to absolute URLs
            if href.startswith('/'):
                from urllib.parse import urljoin
                href = urljoin(url, href)
                
            if ".ipa" in href.lower():
                # Extract clean filename title
                clean_title = href.split('/')[-1].split('?')[0].replace(".ipa", "").replace("-", " ").replace("_", " ")
                link_text = link.get_text().strip()
                display_name = link_text if link_text and len(link_text) < 30 else clean_title
                
                app_id = f"com.scraped.{re.sub(r'[^a-zA-Z0-9]', '', display_name)}".lower()
                
                apps.append({
                    "name": display_name,
                    "bundleIdentifier": app_id,
                    "version": "1.0.0", # Scraped sites rarely expose a clean version tag dynamically
                    "versionDate": "2026-01-01T00:00:00Z", 
                    "downloadURL": href,
                    "localizedDescription": f"Scraped application file found on external site:\n{url}",
                    "developerName": "External Web",
                    "size": 0
                })
    except Exception as e:
        print(f"[-] Error scraping URL {url}: {e}")
    return apps

def main():
    all_apps = []
    
    # 1. Process GitHub Repos
    if os.path.exists("repos.txt"):
        with open("repos.txt", "r") as f:
            repos = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        for repo in repos:
            print(f"[+] Processing GitHub Repo: {repo}")
            all_apps.extend(get_github_releases(repo))
            
    # 2. Process Custom Web Scrapes
    if os.path.exists("urls.txt"):
        with open("urls.txt", "r") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        for url in urls:
            print(f"[+] Scraping External Site: {url}")
            all_apps.extend(scrape_custom_urls(url))
            
    # Assemble AltStore Structure
    repo_structure = {
        "name": REPO_NAME,
        "identifier": REPO_IDENTIFIER,
        "apps": all_apps
    }
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(repo_structure, f, indent=2)
    print(f"[+] Repo successfully built! Output saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
