#Per‑commit granularity
from pydriller import Repository

for commit in Repository(
        'C:/Users/youce/OneDrive/Documents/GitHub/PapyrusProject/'
    ).traverse_commits():
    print(
        commit.hash,
        commit.author.name,
        commit.insertions,
        commit.deletions
    )

#Per‑file granularity
for commit in Repository(
        r'C:/Users/youce/OneDrive/Documents/GitHub/AOCS-project'
    ).traverse_commits():
    print("Commit:", commit.hash)
    for m in commit.modified_files:
        path = m.new_path or m.old_path
        print(f"  {path}: +{m.added_lines} -{m.deleted_lines}")