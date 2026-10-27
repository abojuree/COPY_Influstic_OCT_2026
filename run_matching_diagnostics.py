import sys
import os
import re

# Fix Windows terminal Unicode errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

# Set up path so we can import from the Flask app
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from run import app
from apps import db
from apps.social.models import SocialAccount, SocialPost

def tokenize(text):
    if not text:
        return set()
    # Simple lowercase and alphanumeric extraction
    words = re.findall(r'\b\w+\b', str(text).lower())
    return set(words)

def print_table(headers, rows):
    """ Helper to print ASCII tables """
    col_widths = [max(len(str(item)) for item in col) for col in zip(headers, *rows)]
    col_widths = [width + 2 for width in col_widths] # add padding
    
    header_str = "".join(f"{str(h):<{col_widths[i]}}" for i, h in enumerate(headers))
    print("-" * len(header_str))
    print(header_str)
    print("-" * len(header_str))
    
    for row in rows:
        row_str = "".join(f"{str(item):<{col_widths[i]}}" for i, item in enumerate(row))
        print(row_str)
    print("-" * len(header_str))
    print("\n")


def run_diagnostics():
    with app.app_context():
        print("=== MATCHING DIAGNOSTICS ENGINE ===")
        
        # ---------------------------------------------------------
        # STEP 1: Database Inventory & Sparsity Audit
        # ---------------------------------------------------------
        total_accounts = SocialAccount.query.count()
        total_posts = SocialPost.query.count()
        
        print(f"\n[STEP 1: Database Inventory & Sparsity Audit]")
        print(f"Total SocialAccount Records: {total_accounts}")
        print(f"Total SocialPost Records: {total_posts}\n")
        
        accounts = SocialAccount.query.all()
        
        inv_headers = ["Username", "Platform", "Followers", "Total Scraped Posts", "Posts w/ Caption"]
        inv_rows = []
        
        # We will cache the tokenized texts and metrics for later steps to save time
        account_data = {}
        
        for acc in accounts:
            posts = SocialPost.query.filter_by(socialaccount_id=acc.id).all()
            total_scraped = len(posts)
            posts_with_caption = [p for p in posts if p.caption and str(p.caption).strip()]
            num_with_caption = len(posts_with_caption)
            
            platform_name = acc.platform.name if acc.platform else "Unknown"
            inv_rows.append([acc.username, platform_name, acc.followers or 0, total_scraped, num_with_caption])
            
            # Extract combined caption text
            combined_caption = " ".join([str(p.caption) for p in posts_with_caption])
            
            # Aggregate metrics for objectives
            total_views = sum(p.plays for p in posts if p.plays)
            total_likes = sum(p.likes for p in posts if p.likes)
            total_comments = sum(p.comments for p in posts if p.comments)
            total_shares = sum(p.shares for p in posts if p.shares)
            total_saves = sum(p.saves for p in posts if p.saves)
            
            account_data[acc.id] = {
                'username': acc.username,
                'followers': acc.followers or 0,
                'tokens': tokenize(combined_caption),
                'total_views': total_views,
                'total_likes': total_likes,
                'total_comments': total_comments,
                'total_shares': total_shares,
                'total_saves': total_saves
            }
            
        print_table(inv_headers, inv_rows)

        # ---------------------------------------------------------
        # STEP 2: Jaccard Niche Text Matching Isolation
        # ---------------------------------------------------------
        print(f"[STEP 2: Jaccard Niche Text Matching Isolation]")
        test_cases = {
            "Test Case A (Sports/Football)": ["football", "art", "esports", "world", "cup"],
            "Test Case B (Entertainment/Comedy)": ["movie", "jumanji", "chicken", "fun"],
            "Test Case C (Tech/Software - Out of Niche)": ["software", "coding", "python", "ai"]
        }
        
        for test_name, keywords in test_cases.items():
            print(f"--- {test_name} Keywords: {keywords} ---")
            jaccard_headers = ["Username", "Intersect (|C ∩ I|)", "Union (|C ∪ I|)", "Jaccard Score J(C,I)"]
            jaccard_rows = []
            
            I = set(keywords)
            for acc_id, data in account_data.items():
                C = data['tokens']
                intersection = C.intersection(I)
                union = C.union(I)
                
                intersect_count = len(intersection)
                union_count = len(union)
                j_score = intersect_count / union_count if union_count > 0 else 0.0
                
                # Save Jaccard Score for Test Case A for Step 4
                if test_name == "Test Case A (Sports/Football)":
                    account_data[acc_id]['jaccard_score'] = j_score
                
                jaccard_rows.append([data['username'], intersect_count, union_count, f"{j_score:.4f}"])
                
            print_table(jaccard_headers, jaccard_rows)
            
            
        # ---------------------------------------------------------
        # STEP 3: Objective-Weight Sensitivity Test
        # ---------------------------------------------------------
        print(f"[STEP 3: Objective-Weight Sensitivity Test]")
        obj_headers = ["Username", "Brand Awareness (Share/View)", "Conversions (Save/View)", "Community (Engage/Follower)"]
        obj_rows = []
        
        for acc_id, data in account_data.items():
            views = data['total_views']
            followers = data['followers']
            
            # Brand Awareness
            brand_aw = data['total_shares'] / views if views > 0 else 0.0
            # Direct Conversions
            conversions = data['total_saves'] / views if views > 0 else 0.0
            # Community Building
            community = (data['total_likes'] + data['total_comments']) / followers if followers > 0 else 0.0
            
            # We will use Community Building score for Step 4
            account_data[acc_id]['objective_score'] = min(community, 1.0) # Cap at 1.0 for percentages
            
            obj_rows.append([data['username'], f"{brand_aw:.6f}", f"{conversions:.6f}", f"{community:.6f}"])
            
        print_table(obj_headers, obj_rows)

        # ---------------------------------------------------------
        # STEP 4: Full Score Decomposition Analysis
        # ---------------------------------------------------------
        print(f"[STEP 4: Full Score Decomposition Analysis]")
        print("Using weights: W_niche=0.4 (Test A), W_obj=0.4 (Community), W_scale=0.2 (Log Followers)")
        
        decomp_headers = ["Username", "Score_Jaccard", "Score_Objective", "Score_Scale", "Final_Combined_Score"]
        decomp_rows = []
        
        import math
        MAX_FOLLOWERS = max([d['followers'] for d in account_data.values()]) if account_data else 1
        if MAX_FOLLOWERS <= 1:
            MAX_FOLLOWERS = 2 # prevent div by zero
        
        for acc_id, data in account_data.items():
            w_niche = 0.4
            w_obj = 0.4
            w_scale = 0.2
            
            score_jaccard = data['jaccard_score']
            score_obj = data['objective_score']
            
            # Scale score: log(followers) / log(MAX_FOLLOWERS)
            followers = data['followers'] if data['followers'] > 0 else 1
            score_scale = math.log10(followers) / math.log10(MAX_FOLLOWERS)
            if score_scale < 0: score_scale = 0
            if score_scale > 1: score_scale = 1
            
            final_score = (w_niche * score_jaccard) + (w_obj * score_obj) + (w_scale * score_scale)
            
            decomp_rows.append([
                data['username'],
                f"{score_jaccard*100:.2f}%",
                f"{score_obj*100:.2f}%",
                f"{score_scale*100:.2f}%",
                f"{final_score*100:.2f}%"
            ])
            
        print_table(decomp_headers, decomp_rows)
        print("=== DIAGNOSTICS COMPLETE ===")

if __name__ == '__main__':
    run_diagnostics()
