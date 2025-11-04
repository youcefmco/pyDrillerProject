import os
from datetime import datetime

from pydriller import Repository, ModificationType
from pydriller.metrics.process.change_set import ChangeSet  # ADD THIS
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.dates as mdates
import matplotlib.ticker as mtick
from pydriller.metrics.process.change_set import ChangeSet

# --- CONFIGURATION ---
# Step 1: Configure these variables for your project
CONFIG = {
    # PAIR of: Path to your local Git repository & "TARGET_EXTENSIONS
    #"REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/AOCS-Combined-History", "TARGET_EXTENSIONS": [".uml"],
    # "REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/PapyrusProjectFMU/",
    # "REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/PapyrusProject/"
     "REPO_PATH": "C:/Users/youce/OneDrive/Documents/GitHub/AOCS-project/","TARGET_EXTENSIONS": [ ".c", ".h",".java"],
    # The folder containing the auto-generated code you want to analyze
    # "TARGET_FOLDER": "/BasicActiveObjectExample/",#rc/generated-code/
    "TARGET_FOLDER": "/OBC750-AOCS-Shell-RTP/",  # rc/generated-code/
    # Main branch to analyze
    "BRANCH": "master",
    # ADD THIS: List of file extensions to include in the analysis
    # "TARGET_EXTENSIONS": [ ".uml"],  # ".c", ".h",".java", ".hpp", ".genmodel",".di", ".notation"
    # Keywords to classify commits. Case-insensitive.
    "COMMIT_KEYWORDS": {
        "feat": ["feat", "feature"],
        "fix": ["fix", "bug", "hotfix", "repair"],
        "refactor": ["refactor", "restructure", "rework"],
        "chore": ["chore", "build", "ci"],
        "docs": ["docs", "documentation"]
    },
    # ADD THIS: List of SHAs to exclude from the analysis
    "EXCLUDE_COMMIT_SHAS": [
        "d1182c504c64e2680f19474eab7f8297a3d4ec81",  # trying to get dliver event to stop fot the timer
        # "3d3ca6b06accca0ad0f6c68d9901730af09ac48e", #first commit
        "411bf3c5c4a68467286266fe53090b1ca5259c88"  # removing java profile

        # Add more SHAs as needed
    ]
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
                # TODO : counting comments and adding +2 SLOC
                sloc_count += 2

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
        # ←––––– Drop unwanted commits right away
        if commit.hash in CONFIG["EXCLUDE_COMMIT_SHAS"]:
            print("one is here")
            continue
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
                # TODO : current churn is divided by 10 (WEHN Needed)
                current_churn = (mod.added_lines + mod.deleted_lines)//10

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
            data['ratio'] = (data['refactoring_churn'] / data['sloc'])

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

    print("\n--- Top 10 Files by Refactoring Ratio (Churn/SLoC) ---")
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
        for path, data in sorted_files[:10]:
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

    # NORMAL SIZE

    # commit_df = pd.DataFrame.from_dict(
    #     results['commit_counts'], orient='index', columns=['count']
    # ).sort_values('count', ascending=False)
    # commit_df = commit_df[commit_df['count'] > 0]
    #
    # plt.figure(figsize=(10, 7))
    # plt.pie(commit_df['count'], labels=commit_df.index, autopct='%1.1f%%', startangle=140)
    # plt.title('Commit Classification by Type', fontsize=16, fontweight='bold')
    # plt.ylabel('')  # Hides the 'count' label on the y-axis
    # plt.tight_layout()
    # plt.savefig('commit_classification_pie.png')
    # print("Saved 'commit_classification_pie.png'")
    #
    # # --- Plot 2: Cumulative Churn Over Time (Line Chart) ---
    # if results['chronological_data']:
    #     chrono_df = pd.DataFrame(results['chronological_data'])
    #     chrono_df = chrono_df.sort_values('date')
    #     chrono_df['cumulative_refactoring_churn'] = chrono_df['refactoring_churn'].cumsum()
    #
    #     plt.figure(figsize=(12, 6))
    #     plt.plot(chrono_df['date'], chrono_df['cumulative_refactoring_churn'], marker='o', linestyle='-', markersize=4)
    #     plt.title('Cumulative Code Churn in Generated Code Over Time', fontsize=16, fontweight='bold')
    #     plt.xlabel('Date')
    #     plt.ylabel('Cumulative Lines of Churn (Added + Deleted)')
    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig('cumulative_churn.png')
    #     print("Saved 'cumulative_churn.png'")

    #A0 SIZE
    # --- Plot 1: Commit Classification (Pie Chart) ---
    commit_df = pd.DataFrame.from_dict(
        results['commit_counts'], orient='index', columns=['count']
    ).sort_values('count', ascending=False)
    commit_df = commit_df[commit_df['count'] > 0]

    if not commit_df.empty:
        plt.figure(figsize=(14, 14))  # Large square for poster
        wedges, texts, autotexts = plt.pie(
            commit_df['count'],
            labels=None,  # legend instead of inline labels
            autopct='%1.1f%%',
            startangle=140,
            pctdistance=0.75,
            wedgeprops={'linewidth': 0.5, 'edgecolor': 'white'}
        )

        # Style text sizes
        for at in autotexts:
            at.set_fontsize(24)

        plt.legend(
            wedges,
            commit_df.index,
            title="Commit Type",
            loc="center left",
            bbox_to_anchor=(1.05, 0.5),
            fontsize=22,
            frameon=False
        )

        plt.axis("equal")  # keep pie circular
        plt.tight_layout()
        plt.savefig("commit_classification_pie.svg", format="svg")
        plt.savefig("commit_classification_pie.png", dpi=300)
        plt.close()
        print("Saved commit_classification_pie.svg and PNG")

    # --- Plot 2: Cumulative Churn Over Time (Line Chart) ---
    if results['chronological_data']:
        chrono_df = pd.DataFrame(results['chronological_data'])
        chrono_df = chrono_df.sort_values("date")
        chrono_df["cumulative_refactoring_churn"] = chrono_df["refactoring_churn"].cumsum()

        fig, ax = plt.subplots(figsize=(20, 10))  # Wide for poster
        ax.plot(
            chrono_df["date"],
            chrono_df["cumulative_refactoring_churn"],
            marker="o",
            linestyle="-",
            linewidth=3,
            markersize=8
        )

        ax.set_xlabel("Date", fontsize=28, fontweight="bold")
        ax.set_ylabel("Cumulative Lines of Churn (Added + Deleted)", fontsize=28, fontweight="bold")

        # Format x-axis dates
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=22)
        plt.setp(ax.get_yticklabels(), fontsize=22)

        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        fig.savefig("cumulative_churn.svg", format="svg")
        fig.savefig("cumulative_churn.png", dpi=300)
        plt.close(fig)
        print("Saved cumulative_churn.svg and PNG")

    #  --- Plot 3: File Hotspots (Bar Chart) ---
    # NORMAL SIZE
    # file_metrics = results.get('file_metrics', {})
    # if file_metrics:
    #     hotspots_df = pd.DataFrame.from_dict(file_metrics, orient='index')
    #     hotspots_df = hotspots_df[hotspots_df['refactoring_churn'] > 0].sort_values('refactoring_churn',
    #                                                                                 ascending=False).head(10)
    #
    #     if not hotspots_df.empty:
    #         # 💡 NEW: Shorten the file paths for better readability on the plot
    #         # This takes each path in the index and rebuilds it with only the parent folder and filename.
    #         hotspots_df.index = hotspots_df.index.map(
    #             lambda p: os.path.join(os.path.basename(os.path.dirname(p)), os.path.basename(p))
    #         )
    #         plt.figure(figsize=(12, 8))
    #         hotspots_df['refactoring_churn'].sort_values().plot(kind='barh', color='skyblue')
    #         plt.title('Top 10 "Hotspot" Files by refactoring churn', fontsize=16, fontweight='bold')
    #         plt.xlabel('Total Lines of refactoring_churn (Added + Deleted)')
    #         plt.ylabel('Generated Code')
    #         # Format x-axis as percentage
    #         # plt.gca().xaxis.set_major_formatter(plt.FuncFormatter('{:.0%}'.format))
    #         plt.tight_layout()
    #         plt.savefig('file_hotspots.png')
    #         print("\nSaved 'file_hotspots.png'")

    #A0 SIZE
    # --- Plot 3: File Hotspots (Bar Chart) ---
    file_metrics = results.get('file_metrics', {})
    if file_metrics:
        hotspots_df = pd.DataFrame.from_dict(file_metrics, orient='index')
        hotspots_df = hotspots_df[hotspots_df['refactoring_churn'] > 0] \
            .sort_values('refactoring_churn', ascending=False) \
            .head(10)

        if not hotspots_df.empty:
            # Shorten paths -> keep only parent folder + filename
            hotspots_df.index = hotspots_df.index.map(
                #lambda p: os.path.join(os.path.basename(os.path.dirname(p)), os.path.basename(p))
                #Removing the file extension
                lambda p: os.path.splitext(os.path.basename(p))[0]
            )

            plt.figure(figsize=(18, 10))  # large for poster
            ax = hotspots_df['refactoring_churn'].sort_values().plot(
                kind='barh',
                color='skyblue',
                edgecolor='black'
            )

            # Axis labels (no title)
            ax.set_xlabel("Total Lines of Refactoring Churn (Added + Deleted)", fontsize=26, fontweight="bold")
            ax.set_ylabel("File", fontsize=26, fontweight="bold")

            # Tick label size
            plt.xticks(fontsize=28)
            plt.yticks(fontsize=28)

            plt.tight_layout()
            plt.savefig("file_hotspots.svg", format="svg")
            plt.savefig("file_hotspots.png", dpi=300)
            plt.close()
            print("Saved file_hotspots.svg and PNG")

    # --- NEW Plot: Top 4 Files by Refactoring Ratio ---
    file_metrics = results.get('file_metrics', {})
    if file_metrics:
        hotspots_df = pd.DataFrame.from_dict(file_metrics, orient='index')
        hotspots_df = hotspots_df[hotspots_df['ratio'] > 0].sort_values('ratio', ascending=False).head(5)
    # NORMAL SIZE
    #     if not hotspots_df.empty:
    #         # 💡 NEW: Shorten the file paths for better readability on the plot
    #         # This takes each path in the index and rebuilds it with only the parent folder and filename.
    #         hotspots_df.index = hotspots_df.index.map(
    #             #lambda p: os.path.join(os.path.basename(os.path.dirname(p)), os.path.basename(p))
    #             lambda p: os.path.basename(p)
    #         )
    #         plt.figure(figsize=(12, 8))
    #         hotspots_df['ratio'].sort_values().plot(kind='barh', color='coral')
    #         plt.title('Top 5 Files by Refactoring Ratio (R. Churn/SLoC)', fontsize=16, fontweight='bold')
    #         plt.xlabel('Refactoring Ratio')
    #         plt.ylabel('Generated Code')
    #         # Format x-axis as percentage
    #         plt.gca().xaxis.set_major_formatter(plt.FuncFormatter('{:.0%}'.format))
    #         # ADD THIS LINE to set the x-axis limit from 0% to 100%
    #         plt.xlim(0, 1.0)
    #         plt.tight_layout()
    #         plt.savefig('refactoring_ratio_hotspots.png')
    #         print("\nSaved 'refactoring_ratio_hotspots.png'")

    # A0 SIZE
    if not hotspots_df.empty:
        # Keep only the filename without extension for clarity on the plot
        hotspots_df.index = hotspots_df.index.map(
            lambda p: os.path.splitext(os.path.basename(p))[0]
        )
        # If you prefer "parent/file" without extension, use:
        # hotspots_df.index = hotspots_df.index.map(
        #     lambda p: os.path.join(os.path.basename(os.path.dirname(p)),
        #                            os.path.splitext(os.path.basename(p))[0])
        # )

        # Poster-friendly figure size
        fig, ax = plt.subplots(figsize=(18, 10))

        # Horizontal bar chart (sorted ascending for nice layout)
        series = hotspots_df['ratio'].sort_values()
        series.plot(kind='barh', ax=ax, color='coral', edgecolor='black')

        # Labels (no title)
        ax.set_xlabel("Refactoring Ratio (Churn / SLoC)", fontsize=28, fontweight='bold')
        ax.set_ylabel("File", fontsize=28, fontweight='bold')

        # Format x-axis as percent (0% to 100%)
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0))
        ax.set_xlim(0, 1.0)

        # Ticks font sizes
        ax.tick_params(axis='x', labelsize=22)
        ax.tick_params(axis='y', labelsize=22)

        ax.grid(axis='x', alpha=0.25)

        plt.tight_layout()
        fig.savefig("refactoring_ratio_hotspots.svg", format="svg")
        fig.savefig("refactoring_ratio_hotspots.png", dpi=300)
        plt.close(fig)
        print("Saved 'refactoring_ratio_hotspots.svg' and PNG")

    impact_data = results.get('commit_impact_data', [])
    if impact_data:
        df = pd.DataFrame(impact_data)
        #NORMAL SIZE
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

        plt.title('Commit Impact Analysis', fontsize=22, fontweight='bold')
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

        #A0 SIZE
        # plt.figure(figsize=(14, 10))  # Bigger for poster clarity
        #
        # # Define colors for each commit type
        # colors = {'fix': 'red', 'refactor': 'orange', 'feat': 'green', 'other': 'gray'}
        #
        # # Plot each group with a different color
        # for commit_type, group in df.groupby('type'):
        #     plt.scatter(
        #         group['size'],
        #         group['churn'],
        #         alpha=0.7,
        #         s=80,  # Increase dot size for visibility
        #         c=colors.get(commit_type, 'blue'),
        #         label=commit_type
        #     )
        #
        # # No title
        # plt.xlabel('Change Set Size (Files per Commit)', fontsize=22, fontweight='bold')
        # plt.ylabel('Commit Churn (Lines Added + Deleted)', fontsize=22, fontweight='bold')
        #
        # plt.legend(fontsize=18, markerscale=1.5)
        # plt.grid(True, alpha=0.3)
        #
        # # Use log scale for readability
        # plt.xscale('log')
        # plt.yscale('log')
        #
        # plt.tight_layout()
        # plt.savefig("commit_impact_plot.svg", format="svg")  # SVG for poster
        # print("\nSaved 'commit_impact_plot.svg'")
        #
        # plt.show()


if __name__ == "__main__":
    analysis_results = analyze_repository()
    print_summary(analysis_results)
    create_plots(analysis_results)
