import os
from datetime import datetime

from pydriller import Repository, ModificationType
from pydriller.metrics.process.change_set import ChangeSet  # ADD THIS
import matplotlib.pyplot as plt
import pandas as pd
from pydriller.metrics.process.change_set import ChangeSet

# --- CONFIGURATION ---
# Step 1: Configure these variables for your project
CONFIG = {
    # Path to your local Git repository
    "REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/AOCS-Combined-History",
    #"REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/PapyrusProjectFMU/",
    # "REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/PapyrusProject/",
    # "REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/AOCS-project/",
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
    A more robust Source Lines of Code (SLoC) counter that handles
    C-style multi-line comments (/* ... */) and single-line comments.
    """
    comment_prefixes = ('#', '//')
    in_comment_block = False
    sloc_count = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if in_comment_block:
                    if '*/' in line:
                        line = line.split('*/', 1)[1].strip()
                        in_comment_block = False
                    else:
                        continue

                if not line:
                    continue

                if line.startswith('/*'):
                    if '*/' in line:
                        line = line.split('*/', 1)[1].strip()
                    else:
                        in_comment_block = True
                        continue

                if line and not line.startswith(comment_prefixes):
                    sloc_count += 1
    except (IOError, UnicodeDecodeError):
        return 0
    return sloc_count


def analyze_repository():
    """
    Analyzes the Git repository to extract metrics on churn, commits, and SLoC,
    now with per-file tracking.
    """
    print("🚀 Starting repository analysis...")

    # --- Data Collection Variables ---
    file_metrics = {}
    commit_counts = {key: 0 for key in CONFIG["COMMIT_KEYWORDS"]}
    commit_counts["other"] = 0
    # change_set_size  = []
    chronological_data = []
    commit_impact_data = []

    # --- Instantiate Repository Miner ---
    repo_miner = Repository(
        CONFIG["REPO_PATH"],
        only_in_branch=CONFIG["BRANCH"]
    )

    for commit in repo_miner.traverse_commits():
        # --- 1. Classify commit message --
        commit_type = "other"  # Default type
        msg = commit.msg.lower()
        for key, keywords in CONFIG["COMMIT_KEYWORDS"].items():
            if any(keyword in msg for keyword in keywords):
                commit_counts[key] += 1
                commit_type = key
                break
        if commit_type == "other":
            commit_counts["other"] += 1

        # --- 2. Calculate churn per file
        total_commit_refactoring_churn = 0
        for mod in commit.modified_files:
            if (mod.new_path and
                    mod.new_path.endswith(tuple(CONFIG["TARGET_EXTENSIONS"]))):

                if mod.new_path not in file_metrics:
                    file_metrics[mod.new_path] = {'creation_churn': 0, 'refactoring_churn': 0, 'sloc': 0, 'ratio': 0}

                current_churn = mod.added_lines + mod.deleted_lines

                if mod.change_type == ModificationType.ADD:
                    file_metrics[mod.new_path]['creation_churn'] += current_churn
                else:
                    file_metrics[mod.new_path]['refactoring_churn'] += current_churn
                    total_commit_refactoring_churn += current_churn
        # --- 3. Calculate Change Set Size manually ---
        change_set_size = len(commit.modified_files)  # Calculate change_set_size directly from modified files
        # change_set_size.append(change_set_size)

        # --- 3. Store the data for plotting ---
        # Only store data for commits that actually had churn in the target folder
        if total_commit_refactoring_churn > 0:
            commit_impact_data.append({
                "size": change_set_size,
                "churn": total_commit_refactoring_churn,
                "type": commit_type
            })

        # change_set_size .append(change_set_size)
        chronological_data.append({
            "date": commit.committer_date,
            "refactoring_churn": total_commit_refactoring_churn
        })

    print("✅ Churn analysis complete. Calculating SLoC for relevant files...")

    # --- Calculate Current SLoC for tracked files ---
    repo_root = CONFIG["REPO_PATH"]
    for path, data in file_metrics.items():
        full_path = os.path.join(repo_root, path)
        if os.path.exists(full_path):
            data['sloc'] = count_sloc(full_path)
        if data['sloc'] > 0:
            data['ratio'] = data['refactoring_churn'] / data['sloc']

    # --- Final Metric Calculations ---
    total_sloc = sum(data['sloc'] for data in file_metrics.values())
    total_refactoring_churn = sum(data['refactoring_churn'] for data in file_metrics.values())
    overall_ratio = total_refactoring_churn / total_sloc if total_sloc > 0 else 0

    results = {
        "total_sloc": total_sloc,
        "total_refactoring_churn": total_refactoring_churn,
        "refactoring_ratio": overall_ratio,
        "commit_counts": commit_counts,
        "file_metrics": file_metrics,
        "chronological_data": chronological_data,
        "commit_impact_data": commit_impact_data  # Add the new data
    }

    return results


def print_summary(results):
    """
    Prints a detailed summary of the analysis results in a formatted style to the console.

    This function generates a comprehensive report that includes overall metrics, commit
    classification, top files based on refactoring ratio, and a change set analysis. The report
    is printed directly to the console for quick review and diagnostic purposes.

    :param results: A dictionary containing analysis data with the following potential keys:
        - `total_sloc` (int): Total source lines of code in the repository being analyzed.
        - `total_refactoring_churn` (int): Total lines added and deleted (post-creation).
        - `refactoring_ratio` (float): Overall refactoring ratio calculated as (churn / SLoC).
        - `commit_counts` (dict): Counts of commits categorized by their type, where keys are the
          classification names, and values are the respective counts (int).
        - `file_metrics` (dict): Detailed analysis of individual files. Keys are file paths (str),
          and values are dictionaries with metrics such as:
             - `sloc` (int): Source lines of code.
             - `refactoring_churn` (int): Refactoring churn for the file.
             - `ratio` (float): Refactoring ratio for the file.
        - `commit_impact_data` (list): A list of dictionaries, where each dictionary details the
          size of a commit in terms of affected files (`size`, int). This is used for computing
          the average files changed per commit.

    :return: None
    """
    print("\n" + "=" * 60)
    print("📊 MBD GIT ANALYSIS REPORT")
    print("=" * 60)
    print("--- Overall Metrics ---")
    print(f"Total SLoC in '{CONFIG['REPO_PATH']}' (matching extensions): {results['total_sloc']:,}")
    print(f"Total Refactoring Churn(Lines Added + Deleted (post-creation)): {results['total_refactoring_churn']:,}")
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
        print(f"{'File':<60} {'Ratio':<10} {'Refactor Churn':<15} {'SLoC':<10}")
        print("-" * 90)
        for path, data in sorted_files[:5]:
            ratio_str = f"{data['ratio']:.2%}"
            print(f"{path:<60} {ratio_str:<10} {data['refactoring_churn']:,<10} {data['sloc']:,<10}")
    print("=" * 60)

    print("\n--- Change Set Analysis (Manual Effort Scope) ---")
    if results['commit_impact_data']:
        # number_of_items = len(results['commit_impact_data'])
        # print(f"Number of items in commit_impact_data: {number_of_items}")
        # Calculate the average change set = the sum  of impacted files per commit / sum of commits
        avg_size = sum(entry['size'] for entry in results['commit_impact_data']) / len(results['commit_impact_data'])
        print(f"Average files per  commit: {avg_size:.2f}")


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
        chrono_df['cumulative_refactoring_churn'] = chrono_df['refactoring_churn'].cumsum()

        plt.figure(figsize=(12, 6))
        plt.plot(chrono_df['date'], chrono_df['cumulative_refactoring_churn'], marker='o', linestyle='-', markersize=4)
        plt.title('Cumulative Code Churn in Generated Code Over Time', fontsize=16, fontweight='bold')
        plt.xlabel('Date')
        plt.ylabel('Cumulative Lines of Churn (Added + Deleted)')
        plt.grid(True)
        plt.tight_layout()
        plt.savefig('cumulative_churn.png')
        print("Saved 'cumulative_churn.png'")

    #  --- Plot 3: File Hotspots (Bar Chart) ---
    file_metrics = results.get('file_metrics', {})
    if file_metrics:
        hotspots_df = pd.DataFrame.from_dict(file_metrics, orient='index')
        hotspots_df = hotspots_df[hotspots_df['refactoring_churn'] > 0].sort_values('refactoring_churn',
                                                                                    ascending=False).head(10)

        if not hotspots_df.empty:
            plt.figure(figsize=(12, 8))
            hotspots_df['refactoring_churn'].sort_values().plot(kind='barh', color='skyblue')
            plt.title('Top 10 "Hotspot" Files by refactoring churn', fontsize=16, fontweight='bold')
            plt.xlabel('Total Lines of refactoring_churn (Added + Deleted)')
            plt.ylabel('File Path')
            # Format x-axis as percentage
            # plt.gca().xaxis.set_major_formatter(plt.FuncFormatter('{:.0%}'.format))
            plt.tight_layout()
            plt.savefig('file_hotspots.png')
            print("\nSaved 'file_hotspots.png'")

    # --- NEW Plot: Top 4 Files by Refactoring Ratio ---
    file_metrics = results.get('file_metrics', {})
    if file_metrics:
        hotspots_df = pd.DataFrame.from_dict(file_metrics, orient='index')
        hotspots_df = hotspots_df[hotspots_df['ratio'] > 0].sort_values('ratio', ascending=False).head(5)

        if not hotspots_df.empty:
            plt.figure(figsize=(12, 8))
            hotspots_df['ratio'].sort_values().plot(kind='barh', color='coral')
            plt.title('Top 5 Files by Refactoring Ratio (R. Churn/SLoC)', fontsize=16, fontweight='bold')
            plt.xlabel('Refactoring Ratio')
            plt.ylabel('File Path')
            # Format x-axis as percentage
            plt.gca().xaxis.set_major_formatter(plt.FuncFormatter('{:.0%}'.format))
            plt.tight_layout()
            plt.savefig('refactoring_ratio_hotspots.png')
            print("\nSaved 'refactoring_ratio_hotspots.png'")

    impact_data = results.get('commit_impact_data', [])
    if impact_data:
        df = pd.DataFrame(impact_data)

        plt.figure(figsize=(12, 8))

        # Define colors for each commit type
        colors = {'fix': 'red', 'refactor': 'orange', 'feat': 'green', 'other': 'gray'}

        # Plot each group with a different color
        for commit_type, group in df.groupby('type'):
            plt.scatter(
                group['size'],
                group['churn'],
                alpha=0.6,
                c=colors.get(commit_type, 'blue'),
                label=commit_type
            )

        plt.title('Commit Impact Analysis', fontsize=16, fontweight='bold')
        plt.xlabel('Change Set Size (Number of Files in Commit)')
        plt.ylabel('Commit Churn (Lines Added + Deleted)')
        plt.legend()
        plt.grid(True)
        # Use a log scale if you have extreme outliers (common with regeneration)
        plt.xscale('log')
        plt.yscale('log')
        plt.tight_layout()
        plt.savefig('commit_impact_plot.png')
        print("\nSaved 'commit_impact_plot.png'")

    plt.show()


if __name__ == "__main__":
    analysis_results = analyze_repository()
    print_summary(analysis_results)
    create_plots(analysis_results)
