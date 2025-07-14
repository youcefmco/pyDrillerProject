from pydriller import Repository
import os
import matplotlib.pyplot as plt
import pandas as pd

# --- CONFIGURATION ---
# Step 1: Configure these variables for your project
CONFIG = {
    # Path to your local Git repository

    # "REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/PapyrusProjectFMU/",
    # "REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/PapyrusProject/",
    "REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/AOCS-project/",
    # The folder containing the auto-generated code you want to analyze
    # "TARGET_FOLDER": "/BasicActiveObjectExample/",#rc/generated-code/
    "TARGET_FOLDER": "/OBC750-AOCS-Shell-RTP/",  # rc/generated-code/
    # Main branch to analyze
    "BRANCH": "master",
    # ADD THIS: List of file extensions to include in the analysis
    "TARGET_EXTENSIONS": [".c", ".h", ".java", ".hpp", ".di", ".uml", ".notation", ".genmodel"],
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
    Analyzes the Git repository to extract metrics on churn, commits, and SLoC,
    now with per-file tracking.
    """
    print("🚀 Starting repository analysis...")

    # --- Data Collection Variables ---
    # This new dictionary will store all metrics per file
    file_metrics = {}

    commit_counts = {key: 0 for key in CONFIG["COMMIT_KEYWORDS"]}
    commit_counts["other"] = 0
    chronological_data = []

    repo_miner = Repository(
        CONFIG["REPO_PATH"],
        only_in_branch=CONFIG["BRANCH"]
        # only_in_path=CONFIG["TARGET_FOLDER"]
    )

    for commit in repo_miner.traverse_commits():
        commit_classified = False
        commit_churn = 0

        # Classify commit
        msg = commit.msg.lower()
        for key, keywords in CONFIG["COMMIT_KEYWORDS"].items():
            if any(keyword in msg for keyword in keywords):
                commit_counts[key] += 1
                commit_classified = True
                break
        if not commit_classified:
            commit_counts["other"] += 1

        # Calculate churn per file
        for mod in commit.modified_files:
            # Check if the file matches our target folder and extensions
            if (mod.new_path and
                    # mod.new_path.startswith(CONFIG["TARGET_FOLDER"]) and
                    mod.new_path.endswith(tuple(CONFIG["TARGET_EXTENSIONS"]))):

                # Ensure file entry exists in our dictionary
                if mod.new_path not in file_metrics:
                    file_metrics[mod.new_path] = {'churn': 0, 'sloc': 0, 'ratio': 0}

                current_churn = mod.added_lines + mod.deleted_lines
                file_metrics[mod.new_path]['churn'] += current_churn
                commit_churn += current_churn

        chronological_data.append({
            "date": commit.committer_date,
            "churn": commit_churn
        })

    print("✅ Churn analysis complete. Calculating SLoC for relevant files...")

    # --- Calculate Current SLoC for tracked files ---
    repo_root = CONFIG["REPO_PATH"]
    for file_path_relative in list(file_metrics.keys()):
        # We only calculate SLoC for files that had churn
        full_path = os.path.join(repo_root, file_path_relative)

        if os.path.exists(full_path):
            sloc = count_sloc(full_path)
            file_metrics[file_path_relative]['sloc'] = sloc
        else:
            # File was deleted, so its SLoC is 0
            file_metrics[file_path_relative]['sloc'] = 0

    # --- Final Metric Calculations (Overall and Per-File) ---
    total_sloc = sum(data['sloc'] for data in file_metrics.values())
    total_churn = sum(data['churn'] for data in file_metrics.values())
    refactoring_ratio = total_churn / total_sloc if total_sloc > 0 else 0

    # Calculate per-file ratio
    for data in file_metrics.values():
        if data['sloc'] > 0:
            data['ratio'] = data['churn'] / data['sloc']

    results = {
        "total_sloc": total_sloc,
        "total_churn": total_churn,
        "refactoring_ratio": refactoring_ratio,
        "commit_counts": commit_counts,
        "file_metrics": file_metrics,
        "chronological_data": chronological_data
    }

    return results


def print_summary(results):
    """Prints a formatted summary including per-file metrics."""
    print("\n" + "=" * 60)
    print("📊 MBD GIT ANALYSIS REPORT")
    print("=" * 60)
    print("--- Overall Metrics ---")
    print(f"Total SLoC in '{CONFIG['TARGET_FOLDER']}' (matching extensions): {results['total_sloc']:,}")
    print(f"Total Code Churn (Lines Added + Deleted): {results['total_churn']:,}")
    print(f"Overall Refactoring Ratio (Churn / SLoC): {results['refactoring_ratio']:.2%}")
    print("\n--- Commit Classification ---")
    for key, count in results['commit_counts'].items():
        if count > 0:
            print(f"  - {key.capitalize():<10}: {count} commits")

    print("\n--- Top 5 Files by Refactoring Ratio (Churn/SLoC) ---")
    # Sort files by refactoring ratio, descending
    sorted_files = sorted(
        results['file_metrics'].items(),
        key=lambda item: item[1]['ratio'],
        reverse=True
    )

    if not sorted_files:
        print("No files with churn were found to analyze.")
    else:
        print(f"{'File':<60} {'Ratio':<10} {'Churn':<10} {'SLoC':<10}")
        print("-" * 90)
        for path, data in sorted_files[:5]:
            ratio_str = f"{data['ratio']:.2%}"
            print(f"{path:<60} {ratio_str:<10} {data['churn']:,<10} {data['sloc']:,<10}")
    print("=" * 60)


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

    # --- NEW Plot: Top 5 Files by Refactoring Ratio ---
    file_metrics = results.get('file_metrics', {})
    if file_metrics:
        hotspots_df = pd.DataFrame.from_dict(file_metrics, orient='index')
        hotspots_df = hotspots_df[hotspots_df['ratio'] > 0].sort_values('ratio', ascending=False).head(5)

        if not hotspots_df.empty:
            plt.figure(figsize=(12, 8))
            hotspots_df['ratio'].sort_values().plot(kind='barh', color='coral')
            plt.title('Top 5 Files by Refactoring Ratio (Churn/SLoC)', fontsize=16, fontweight='bold')
            plt.xlabel('Refactoring Ratio')
            plt.ylabel('File Path')
            # Format x-axis as percentage
            plt.gca().xaxis.set_major_formatter(plt.FuncFormatter('{:.0%}'.format))
            plt.tight_layout()
            plt.savefig('refactoring_ratio_hotspots.png')
            print("\nSaved 'refactoring_ratio_hotspots.png'")

    plt.show()


if __name__ == "__main__":
    analysis_results = analyze_repository()
    print_summary(analysis_results)
    create_plots(analysis_results)
