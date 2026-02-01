import requests
import json
from datetime import datetime

# =================================================
# DYNAMIC CONFIGURATION LOADER
# =================================================
def load_accounts():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found!")
        return {"leetcode": [], "codeforces": []}

# =================================================
# LEETCODE FETCHING (Rating + Solved)
# =================================================
def get_leetcode_data(username):
    """
    Fetches both Contest Rating and Total Solved in a SINGLE query.
    Returns: (rating, solved_count)
    """
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
        response = requests.post("https://leetcode.com/graphql", json=payload, timeout=10)
        data = response.json()
        
        rating = 0.0
        solved = 0
        
        # 1. Extract Rating (if user has participated in contests)
        if data.get("data") and data["data"].get("userContestRanking"):
            rating = data["data"]["userContestRanking"]["rating"]
            
        # 2. Extract Solved Count
        if data.get("data") and data["data"].get("matchedUser"):
            stats = data["data"]["matchedUser"]["submitStats"]["acSubmissionNum"]
            for stat in stats:
                if stat["difficulty"] == "All":
                    solved = stat["count"]
        
        return rating, solved

    except Exception as e:
        print(f"Error fetching LeetCode ({username}): {e}")
        return 0.0, 0

# =================================================
# CODEFORCES FETCHING
# =================================================
def get_codeforces_rating(handle):
    """Fetches maxRating for a Codeforces handle."""
    try:
        url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data['status'] == 'OK':
            return data['result'][0].get('maxRating', 0)
    except Exception as e:
        print(f"Error fetching Codeforces ({handle}): {e}")
    return 0

# =================================================
# MAIN LOGIC
# =================================================
def process_stats(config):
    # --- LeetCode Logic ---
    lc_accounts = config.get("leetcode", [])
    max_lc_rating = 0.0
    total_lc_solved = 0
    
    print(f"--- Processing {len(lc_accounts)} LeetCode Accounts ---")
    for user in lc_accounts:
        rating, solved = get_leetcode_data(user)
        print(f"   User: {user} | Rating: {round(rating)} | Solved: {solved}")
        
        # Logic: Max Rating, Sum Solved
        if rating > max_lc_rating:
            max_lc_rating = rating
        total_lc_solved += solved

    # --- Codeforces Logic ---
    cf_accounts = config.get("codeforces", [])
    max_cf_rating = 0
    
    print(f"\n--- Processing {len(cf_accounts)} Codeforces Accounts ---")
    for handle in cf_accounts:
        rating = get_codeforces_rating(handle)
        print(f"   Handle: {handle} | Max Rating: {rating}")
        
        # Logic: Max Rating
        if rating > max_cf_rating:
            max_cf_rating = rating

    return int(max_lc_rating), total_lc_solved, max_cf_rating

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
    best_lc_rating, total_lc_solved, best_cf_rating = process_stats(config)
    update_latex_file(best_lc_rating, total_lc_solved, best_cf_rating)