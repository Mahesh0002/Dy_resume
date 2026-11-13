"""Fetch coding-profile stats and regenerate dynamic_stats.tex.

Failure policy: if any configured account for a platform cannot be fetched,
keep the last published values for that platform instead of writing a partial
or zeroed result. A transient API failure must never wipe the resume numbers.
"""

import json
import re
from datetime import datetime
from pathlib import Path

import requests

STATS_FILE = Path("dynamic_stats.tex")
CONFIG_FILE = Path("config.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DyResume/1.0)"}


# =================================================
# DYNAMIC CONFIGURATION LOADER
# =================================================
def load_accounts():
    try:
        config = json.loads(CONFIG_FILE.read_text())
    except FileNotFoundError:
        print("Error: config.json not found!")
        return {"leetcode": [], "codeforces": []}
    except json.JSONDecodeError as exc:
        print(f"Error: config.json is not valid JSON: {exc}")
        return {"leetcode": [], "codeforces": []}

    return {
        "leetcode": [str(item) for item in config.get("leetcode", []) if item],
        "codeforces": [str(item) for item in config.get("codeforces", []) if item],
    }


# =================================================
# LEETCODE FETCHING (Rating + Solved)
# =================================================
def get_leetcode_data(username):
    """Return (rating, solved_count), or (None, None) when the fetch fails."""
    query = """
    query getUserData($username: String!) {
      userContestRanking(username: $username) {
        rating
      }
      matchedUser(username: $username) {
        submitStats {
          acSubmissionNum {
            difficulty
            count
          }
        }
      }
    }
    """
    payload = {"query": query, "variables": {"username": username}}

    try:
        response = requests.post(
            "https://leetcode.com/graphql",
            json=payload,
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"Error fetching LeetCode ({username}): {exc}")
        return None, None

    if data.get("errors"):
        print(f"LeetCode GraphQL error ({username}): {data['errors']}")
        return None, None

    result = data.get("data") or {}
    matched_user = result.get("matchedUser")
    if not matched_user:
        print(f"LeetCode user not found: {username}")
        return None, None

    rating = 0.0
    contest_ranking = result.get("userContestRanking")
    if contest_ranking and contest_ranking.get("rating") is not None:
        rating = float(contest_ranking["rating"])

    solved = 0
    stats = (matched_user.get("submitStats") or {}).get("acSubmissionNum") or []
    for stat in stats:
        if stat.get("difficulty") == "All":
            solved = int(stat.get("count") or 0)
            break

    return rating, solved


# =================================================
# CODEFORCES FETCHING
# =================================================
def get_codeforces_rating(handle):
    """Return maxRating, or None when the fetch fails."""
    try:
        response = requests.get(
            f"https://codeforces.com/api/user.info?handles={handle}",
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"Error fetching Codeforces ({handle}): {exc}")
        return None

    if data.get("status") != "OK" or not data.get("result"):
        print(f"Codeforces returned no data for {handle}")
        return None

    return int(data["result"][0].get("maxRating") or 0)


# =================================================
# PREVIOUS VALUES
# =================================================
def read_previous_stats():
    """Read the last published values so a failed fetch can preserve them."""
    previous = {
        "leetcodeRating": 0,
        "leetcodeSolved": 0,
        "codeforcesRating": 0,
    }
    if not STATS_FILE.exists():
        return previous

    text = STATS_FILE.read_text()
    for name in previous:
        match = re.search(r"\\newcommand\{\\" + name + r"\}\{(\d+)\}", text)
        if match:
            previous[name] = int(match.group(1))
    return previous


# =================================================
# MAIN LOGIC
# =================================================
def process_stats(config, previous):
    # --- LeetCode Logic ---
    lc_accounts = config.get("leetcode", [])
    lc_ratings = []
    total_lc_solved = 0
    lc_failed = False

    print(f"--- Processing {len(lc_accounts)} LeetCode Accounts ---")
    for user in lc_accounts:
        rating, solved = get_leetcode_data(user)
        if rating is None:
            lc_failed = True
            continue
        print(f"   User: {user} | Rating: {round(rating)} | Solved: {solved}")
        lc_ratings.append(rating)
        total_lc_solved += solved

    if lc_accounts and not lc_failed:
        # LeetCode's GraphQL rating is a float (e.g. 1893.99); round like the UI.
        max_lc_rating = int(round(max(lc_ratings))) if lc_ratings else 0
        lc_solved_out = total_lc_solved
    else:
        max_lc_rating = previous["leetcodeRating"]
        lc_solved_out = previous["leetcodeSolved"]
        if lc_accounts:
            print("[WARN] LeetCode fetch incomplete; preserving previous values.")
        else:
            print("[WARN] No LeetCode accounts configured; preserving previous values.")

    # --- Codeforces Logic ---
    cf_accounts = config.get("codeforces", [])
    cf_ratings = []
    cf_failed = False

    print(f"\n--- Processing {len(cf_accounts)} Codeforces Accounts ---")
    for handle in cf_accounts:
        rating = get_codeforces_rating(handle)
        if rating is None:
            cf_failed = True
            continue
        print(f"   Handle: {handle} | Max Rating: {rating}")
        cf_ratings.append(rating)

    if cf_accounts and not cf_failed:
        max_cf_rating = max(cf_ratings) if cf_ratings else 0
    else:
        max_cf_rating = previous["codeforcesRating"]
        if cf_accounts:
            print("[WARN] Codeforces fetch incomplete; preserving previous values.")
        else:
            print("[WARN] No Codeforces accounts configured; preserving previous values.")

    return max_lc_rating, lc_solved_out, max_cf_rating


def update_latex_file(lc_rating, lc_solved, cf_rating):
    date_str = datetime.now().strftime("%B %d, %Y")

    latex_content = f"""
% AUTOMATICALLY GENERATED FILE
\\newcommand{{\\leetcodeRating}}{{{lc_rating}}}
\\newcommand{{\\leetcodeSolved}}{{{lc_solved}}}
\\newcommand{{\\codeforcesRating}}{{{cf_rating}}}
\\newcommand{{\\lastUpdated}}{{{date_str}}}
"""

    with open("dynamic_stats.tex", "w") as f:
        f.write(latex_content)
    print("\n[SUCCESS] dynamic_stats.tex has been updated.")


if __name__ == "__main__":
    config = load_accounts()
    previous = read_previous_stats()
    best_lc_rating, total_lc_solved, best_cf_rating = process_stats(config, previous)
    update_latex_file(best_lc_rating, total_lc_solved, best_cf_rating)
