import os

import requests

OWNER = "linz"
REPO = "topographic-system"
PATH = "schema"
BRANCH = "master"
DEST = "../external/schemas"


def download_github_json_files(
    owner: str, repo: str, path: str, branch: str, dest: str
):
    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    )

    if not os.path.exists(dest):
        os.makedirs(dest)
        print(f"Created directory: {dest}/")

    print(f"Fetching...")
    response = requests.get(api_url)
    if response.status_code != 200:
        print(
            f"Failed to fetch directory info. HTTP Status Code: {response.status_code}"
        )
        print(
            "Message:",
            response.json().get("message", "No error message provided by API."),
        )
        return

    contents = response.json()
    json_files = [
        item
        for item in contents
        if item["type"] == "file" and item["name"].endswith(".json")
    ]

    if not json_files:
        print("No JSON files found in the specified directory.")
        return

    print(f"Found {len(json_files)} JSON file(s). Starting downloads...\n")
    for file_info in json_files:
        file_name = file_info["name"]
        download_url = file_info["download_url"]

        if not download_url:
            continue

        print(f"Downloading {file_name}...")
        file_response = requests.get(download_url)

        if file_response.status_code == 200:
            file_path = os.path.join(dest, file_name)
            with open(file_path, "wb") as f:
                f.write(file_response.content)
            print(f"  -> Saved to {file_path}")
        else:
            print(
                f"  -> Failed to download {file_name} (Status code: {file_response.status_code})"
            )

    print("\nAll downloads completed!")


if __name__ == "__main__":
    download_github_json_files(OWNER, REPO, PATH, BRANCH, DEST)
