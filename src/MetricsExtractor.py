from pydriller import Repository
import os
import matplotlib.pyplot as plt
import pandas as pd

# --- CONFIGURATION ---
# Step 1: Configure these variables for your project
CONFIG = {
    # Path to your local Git repository
    "REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/PapyrusProject/",
    # The folder containing the auto-generated code you want to analyze
    "TARGET_FOLDER": "/BasicActiveObjectExample/",#rc/generated-code/
    # Main branch to analyze
    "BRANCH": "master",
    # Keywords to classify commits. Case-insensitive.
    "COMMIT_KEYWORDS": {
        "feat": ["feat", "feature"],
        "fix": ["fix", "bug", "hotfix", "repair"],
        "refactor": ["refactor", "restructure", "rework"],
        "chore": ["chore", "build", "ci"],
        "docs": ["docs", "documentation"]
    }
}


def count_sloc(file_path):
    """
    A simple Source Lines of Code (SLoC) counter.
    It skips empty lines and common single-line comments for C/C++/Java/Python.
    """
    comment_prefixes = ('#', '//', '/*', '*/', '*')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return len([
                line for line in lines
                if line.strip() and not line.strip().startswith(comment_prefixes)
            ])
    except (IOError, UnicodeDecodeError):
        # Return 0 for binary files or files that can't be read
        return 0


def analyze_repository():
    """
    Analyzes the Git repository to extract metrics on churn, commits, and SLoC.
    """
    print("🚀 Starting repository analysis...")

    # --- Data Collection Variables ---
    total_churn = 0
    commit_counts = {key: 0 for key in CONFIG["COMMIT_KEYWORDS"]}
    commit_counts["other"] = 0
    churn_by_file = {}
    chronological_data = []

    # --- Pydriller Repository Mining ---
    # We only analyze commits that modify the target folder for efficiency
    repo_miner = Repository(
        CONFIG["REPO_PATH"],
        only_in_branch=CONFIG["BRANCH"]
    )


    for commit in repo_miner.traverse_commits():
        commit_classified = False
        commit_churn = 0

        # Classify commit based on message
        msg = commit.msg.lower()
        for key, keywords in CONFIG["COMMIT_KEYWORDS"].items():
            if any(keyword in msg for keyword in keywords):
                commit_counts[key] += 1
                commit_classified = True
                break
        if not commit_classified:
            commit_counts["other"] += 1

        # Calculate churn within the target folder
        for mod in commit.modified_files:
            # Ensure we are only looking at files within the target folder
            #if mod.new_path and mod.new_path.startswith(CONFIG["TARGET_FOLDER"]):
                current_churn = mod.added_lines + mod.deleted_lines
                total_churn += current_churn
                commit_churn += current_churn

                # Track churn per file (hotspots)
                churn_by_file[mod.new_path] = churn_by_file.get(mod.new_path, 0) + current_churn

        chronological_data.append({
            "date": commit.committer_date,
            "churn": commit_churn
        })

    print("✅ Analysis complete.")

    # --- Calculate Current SLoC ---
    total_sloc = 0
    target_path = os.path.join(CONFIG["REPO_PATH"], CONFIG["TARGET_FOLDER"])
    if os.path.isdir(target_path):
        for root, _, files in os.walk(target_path):
            for file in files:
                file_path = os.path.join(root, file)
                total_sloc += count_sloc(file_path)

    # --- Final Metric Calculations ---
    refactoring_ratio = total_churn / total_sloc if total_sloc > 0 else 0

    # --- Prepare results for returning ---
    results = {
        "total_sloc": total_sloc,
        "total_churn": total_churn,
        "refactoring_ratio": refactoring_ratio,
        "commit_counts": commit_counts,
        "churn_by_file": churn_by_file,
        "chronological_data": chronological_data
    }

    return results


def print_summary(results):
    """Prints a formatted summary of the analysis results."""
    print("\n" + "=" * 50)
    print("📊 MBD GIT ANALYSIS REPORT")
    print("=" * 50)
    print(f"Total SLoC in '{CONFIG['TARGET_FOLDER']}': {results['total_sloc']:,}")
    print(f"Total Code Churn (Lines Added + Deleted): {results['total_churn']:,}")
    print(f"Refactoring Ratio (Churn / SLoC): {results['refactoring_ratio']:.2%}")
    print("-" * 50)
    print("Commit Classification:")
    for key, count in results['commit_counts'].items():
        if count > 0:
            print(f"  - {key.capitalize():<10}: {count} commits")
    print("=" * 50)


def create_plots(results):
    """Generates and displays plots based on the analysis results."""
    if not results:
        print("No data to plot.")
        return

    plt.style.use('seaborn-v0_8-whitegrid')

    # --- Plot 1: Commit Classification (Pie Chart) ---
    commit_df = pd.DataFrame.from_dict(
        results['commit_counts'], orient='index', columns=['count']
    ).sort_values('count', ascending=False)
    commit_df = commit_df[commit_df['count'] > 0]

    plt.figure(figsize=(10, 7))
    plt.pie(commit_df['count'], labels=commit_df.index, autopct='%1.1f%%', startangle=140)
    plt.title('Commit Classification by Type', fontsize=16, fontweight='bold')
    plt.ylabel('')  # Hides the 'count' label on the y-axis
    plt.tight_layout()
    plt.savefig('commit_classification_pie.png')
    print("Saved 'commit_classification_pie.png'")

    # --- Plot 2: Cumulative Churn Over Time (Line Chart) ---
    if results['chronological_data']:
        chrono_df = pd.DataFrame(results['chronological_data'])
        chrono_df = chrono_df.sort_values('date')
        chrono_df['cumulative_churn'] = chrono_df['churn'].cumsum()

        plt.figure(figsize=(12, 6))
        plt.plot(chrono_df['date'], chrono_df['cumulative_churn'], marker='o', linestyle='-', markersize=4)
        plt.title('Cumulative Code Churn in Generated Code Over Time', fontsize=16, fontweight='bold')
        plt.xlabel('Date')
        plt.ylabel('Cumulative Lines of Churn (Added + Deleted)')
        plt.grid(True)
        plt.tight_layout()
        plt.savefig('cumulative_churn.png')
        print("Saved 'cumulative_churn.png'")

    # --- Plot 3: File Hotspots (Bar Chart) ---
    hotspots_df = pd.DataFrame.from_dict(
        results['churn_by_file'], orient='index', columns=['churn']
    ).sort_values('churn', ascending=False).head(10)  # Top 10 files

    if not hotspots_df.empty:
        plt.figure(figsize=(12, 8))
        hotspots_df['churn'].sort_values().plot(kind='barh', color='skyblue')
        plt.title('Top 10 "Hotspot" Files by Churn', fontsize=16, fontweight='bold')
        plt.xlabel('Total Lines of Churn (Added + Deleted)')
        plt.ylabel('File Path')
        plt.tight_layout()
        plt.savefig('file_hotspots.png')
        print("Saved 'file_hotspots.png'")

    plt.show()


if __name__ == "__main__":
    analysis_results = analyze_repository()
    print_summary(analysis_results)
    create_plots(analysis_results)