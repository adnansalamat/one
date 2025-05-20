import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
import uuid # For generating unique IDs
import difflib

# Assuming core_structures.py is in the same directory
try:
    from core_structures import Document, Version, Repository, User
except ImportError:
    print("Error: core_structures.py not found. Make sure it's in the same directory.")
    sys.exit(1)

# --- Constants ---
VCS_DIR_NAME = ".docvcs"
OBJECTS_DIR = "objects"
VERSIONS_DIR = "versions"
STAGING_FILE = "staging.txt"
DOCUMENTS_FILE = "documents.json" # To store Document metadata
REFS_DIR = "refs"
HEADS_DIR = os.path.join(REFS_DIR, "heads")
HEAD_FILE = "HEAD"
DEFAULT_BRANCH_NAME = "main"


# --- Helper Functions ---
# ... (existing helpers) ...

def get_refs_path(repo_root):
    """Returns the path to the refs directory."""
    return os.path.join(get_vcs_path(repo_root), REFS_DIR)

def get_refs_heads_path(repo_root):
    """Returns the path to the refs/heads directory (branches)."""
    return os.path.join(get_vcs_path(repo_root), HEADS_DIR)

def get_head_filepath(repo_root):
    """Returns the path to the HEAD file."""
    return os.path.join(get_vcs_path(repo_root), HEAD_FILE)

def read_head(repo_root):
    """
    Reads the content of HEAD.
    Returns a string: either a branch name (e.g., "main") or a commit_id (detached HEAD).
    Returns None if HEAD file doesn't exist or is empty.
    """
    head_filepath = get_head_filepath(repo_root)
    try:
        with open(head_filepath, 'r') as f:
            content = f.read().strip()
            return content if content else None
    except FileNotFoundError:
        return None

def write_head(repo_root, content):
    """Writes the given content (branch name or commit_id) to the HEAD file."""
    head_filepath = get_head_filepath(repo_root)
    os.makedirs(os.path.dirname(head_filepath), exist_ok=True)
    with open(head_filepath, 'w') as f:
        f.write(content)

def get_branch_filepath(repo_root, branch_name):
    """Returns the filepath for a given branch in .docvcs/refs/heads/."""
    return os.path.join(get_refs_heads_path(repo_root), branch_name)

def read_branch_commit_id(repo_root, branch_name):
    """Reads the commit_id from the specified branch file."""
    branch_file = get_branch_filepath(repo_root, branch_name)
    try:
        with open(branch_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def write_branch_commit_id(repo_root, branch_name, commit_id):
    """Writes the commit_id to the specified branch file."""
    branch_file = get_branch_filepath(repo_root, branch_name)
    os.makedirs(os.path.dirname(branch_file), exist_ok=True)
    with open(branch_file, 'w') as f:
        f.write(commit_id)

def list_branches(repo_root):
    """Returns a dictionary of branch_name: commit_id."""
    branches = {}
    heads_path = get_refs_heads_path(repo_root)
    if not os.path.exists(heads_path):
        return branches
    for branch_name in os.listdir(heads_path):
        commit_id = read_branch_commit_id(repo_root, branch_name)
        if commit_id:
            branches[branch_name] = commit_id
    return branches

def is_valid_branch_name(branch_name):
    """Checks if a branch name is valid (simple check for now)."""
    if not branch_name or \
       branch_name.startswith(".") or \
       ".." in branch_name or \
       any(c in branch_name for c in " ~^:?*[\\]"):
        return False
    return True

def get_current_commit_id(repo_root):
    """Gets the commit ID HEAD is currently pointing to, either directly or via a branch."""
    head_content = read_head(repo_root)
    if not head_content:
        return None # Should not happen in a well-formed repo after init

    branch_path = get_branch_filepath(repo_root, head_content)
    if os.path.exists(branch_path): # HEAD points to a branch
        return read_branch_commit_id(repo_root, head_content)
    else: # HEAD is detached, points directly to a commit
        # Basic check: is it a plausible commit ID format (e.g. UUID length)?
        if len(head_content) == 36: # Assuming UUIDs for commit_ids
             # Further validation could involve checking if this commit_id exists in versions.
            return head_content
    return None # Not a branch and not a recognizable commit ID

def get_repo_root(path="."):
    """Finds the repository root by looking for the .docvcs directory."""
    current_path = os.path.abspath(path)
    while True:
        if os.path.isdir(os.path.join(current_path, VCS_DIR_NAME)):
            return current_path
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:  # Reached filesystem root
            return None
        current_path = parent_path

def is_repo_initialized(path="."):
    """Checks if the given path is within an initialized repository."""
    return get_repo_root(path) is not None

def get_vcs_path(repo_root):
    """Returns the path to the .docvcs directory."""
    return os.path.join(repo_root, VCS_DIR_NAME)

def get_objects_path(repo_root):
    """Returns the path to the objects directory."""
    return os.path.join(get_vcs_path(repo_root), OBJECTS_DIR)

def get_versions_path(repo_root):
    """Returns the path to the versions directory."""
    return os.path.join(get_vcs_path(repo_root), VERSIONS_DIR)

def get_staging_filepath(repo_root):
    """Returns the path to the staging file."""
    return os.path.join(get_vcs_path(repo_root), STAGING_FILE)

def get_documents_filepath(repo_root):
    """Returns the path to the documents metadata file."""
    return os.path.join(get_vcs_path(repo_root), DOCUMENTS_FILE)

def read_json_file(filepath, default_data=None):
    """Reads a JSON file and returns its content, or default_data if it doesn't exist/is empty."""
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return default_data if default_data is not None else {}
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default_data if default_data is not None else {}


def write_json_file(filepath, data):
    """Writes data to a JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def calculate_file_checksum(filepath):
    """Calculates SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while True:
                data = f.read(65536)  # Read in 64k chunks
                if not data:
                    break
                sha256.update(data)
        return sha256.hexdigest()
    except FileNotFoundError:
        return None

# --- Command Implementations ---

def init_command(args):
    """Initializes a new repository."""
    repo_path = os.path.abspath(args.directory)
    vcs_path = os.path.join(repo_path, VCS_DIR_NAME)

    if os.path.exists(vcs_path):
        print(f"Error: Repository already initialized at {repo_path}")
        return

    try:
        os.makedirs(vcs_path)
        os.makedirs(os.path.join(vcs_path, OBJECTS_DIR))
        os.makedirs(os.path.join(vcs_path, VERSIONS_DIR))
        # Create an empty staging file
        with open(os.path.join(vcs_path, STAGING_FILE), 'w') as f:
            pass
        # Create an empty documents metadata file
        write_json_file(os.path.join(vcs_path, DOCUMENTS_FILE), {})

        # Initialize refs and HEAD for branching
        os.makedirs(get_refs_heads_path(repo_path)) # Creates .docvcs/refs/heads/
        write_head(repo_path, DEFAULT_BRANCH_NAME) # HEAD points to "main"

        print(f"Initialized empty DocVCS repository in {vcs_path}")
        print(f"Default branch '{DEFAULT_BRANCH_NAME}' created. HEAD points to '{DEFAULT_BRANCH_NAME}'.")
    except OSError as e:
        print(f"Error: Could not initialize repository at {repo_path}: {e}")

def add_command(args):
    """Adds file(s) to the staging area."""
    repo_root = get_repo_root()
    if not repo_root:
        print("Error: Not a DocVCS repository. Initialize with 'docvcs init' first.")
        return

    staging_filepath = get_staging_filepath(repo_root)
    staged_files = set()
    if os.path.exists(staging_filepath) and os.path.getsize(staging_filepath) > 0:
        with open(staging_filepath, 'r') as f:
            staged_files = set(line.strip() for line in f if line.strip())

    added_count = 0
    for filepath_arg in args.files:
        # Ensure the file path is absolute before trying to make it relative
        abs_filepath_arg = os.path.abspath(filepath_arg)

        if not os.path.exists(abs_filepath_arg):
            print(f"Error: File not found: {filepath_arg}")
            continue

        if not os.path.isfile(abs_filepath_arg):
            print(f"Error: '{filepath_arg}' is a directory or not a regular file. Only files can be added.")
            continue

        # Check if the file is within the repository root
        if not abs_filepath_arg.startswith(repo_root + os.sep):
            print(f"Error: File '{filepath_arg}' is outside the repository '{repo_root}'.")
            continue

        relative_filepath = os.path.relpath(abs_filepath_arg, repo_root)

        if relative_filepath in staged_files:
            print(f"File '{relative_filepath}' is already staged.")
            continue

        staged_files.add(relative_filepath)
        print(f"Added '{relative_filepath}' to staging area.")
        added_count +=1

    if added_count > 0 or (not args.files and not staged_files): # Update if new files added or if called with no args and staging is empty
        with open(staging_filepath, 'w') as f:
            for staged_file in sorted(list(staged_files)):
                f.write(staged_file + "\n")
    elif not args.files and staged_files:
         print("No files specified to add. Current staged files:")
         for sf in sorted(list(staged_files)):
             print(f"  - {sf}")


def commit_command(args):
    """Commits staged changes."""
    repo_root = get_repo_root()
    if not repo_root:
        print("Error: Not a DocVCS repository. Initialize with 'docvcs init' first.")
        return

    if not args.message:
        print("Error: Commit message is required. Use -m <message>.")
        return

    staging_filepath = get_staging_filepath(repo_root)
    if not os.path.exists(staging_filepath) or os.path.getsize(staging_filepath) == 0:
        print("Nothing to commit. Staging area is empty. Use 'docvcs add <file>...' to stage changes.")
        return

    with open(staging_filepath, 'r') as f:
        staged_files_relpaths = [line.strip() for line in f if line.strip()]

    if not staged_files_relpaths:
        print("Nothing to commit. Staging area is empty after processing. (This shouldn't happen if checks above are correct)")
        return

    # Load document metadata
    documents_meta_filepath = get_documents_filepath(repo_root)
    documents_data = read_json_file(documents_meta_filepath, {}) # { "filepath": "document_id" }

    objects_path = get_objects_path(repo_root)
    versions_path = get_versions_path(repo_root)

    commit_id = str(uuid.uuid4()) # A unique ID for this commit/version batch
    commit_timestamp = datetime.datetime.now(datetime.timezone.utc)
    # For now, author is OS username. Could be configurable.
    try:
        author = os.getlogin()
    except OSError:
        author = "unknown"


    committed_files_info = []

    for rel_filepath in staged_files_relpaths:
        abs_filepath = os.path.join(repo_root, rel_filepath)
        if not os.path.exists(abs_filepath):
            print(f"Warning: Staged file '{rel_filepath}' not found in working directory. Skipping.")
            continue

        content_checksum = calculate_file_checksum(abs_filepath)
        if not content_checksum:
            print(f"Warning: Could not calculate checksum for '{rel_filepath}'. Skipping.")
            continue

        # Store object if it doesn't exist
        object_filepath = os.path.join(objects_path, content_checksum)
        if not os.path.exists(object_filepath):
            shutil.copy2(abs_filepath, object_filepath)

        # Get or create Document ID
        doc_id = documents_data.get(rel_filepath)
        if not doc_id:
            doc_id = str(uuid.uuid4())
            documents_data[rel_filepath] = doc_id
            # In a more complex system, Document object itself might be stored separately
            # For now, just tracking filepath -> doc_id mapping

        version_id = str(uuid.uuid4()) # Unique ID for this specific file version
        version_data = {
            "id": version_id,
            "document_id": doc_id,
            "filepath_at_commit": rel_filepath, # Store the filepath as it was at commit time
            "timestamp": commit_timestamp.isoformat(),
            "author": author,
            "message": args.message,
            "content_checksum": content_checksum,
            "commit_id": commit_id # Link to the overall commit
        }

        # Store version metadata
        version_meta_filename = f"{commit_id}_{version_id}.json" # Ensure unique filename
        version_meta_filepath = os.path.join(versions_path, version_meta_filename)
        write_json_file(version_meta_filepath, version_data)

        committed_files_info.append(f"{rel_filepath} (checksum: {content_checksum[:7]})")

    if not committed_files_info:
        print("No files were successfully committed.")
        return

    # Save updated document metadata
    write_json_file(documents_meta_filepath, documents_data)

    # Clear staging area
    with open(staging_filepath, 'w') as f:
        pass

    # Update HEAD and branch ref
    head_content = read_head(repo_root)
    if not head_content:
        # This should ideally not happen if init always creates HEAD
        print("Critical Error: HEAD file is missing or empty!")
        head_content = DEFAULT_BRANCH_NAME # Attempt to recover by assuming default branch
        write_head(repo_root, head_content)

    # Check if HEAD points to a branch or is detached
    branch_file_path = get_branch_filepath(repo_root, head_content) # head_content could be a branch name
    
    if os.path.exists(os.path.dirname(branch_file_path)) and not head_content.startswith('.'): # Check if it's a path-like name for a branch
        # HEAD points to a branch, update the branch
        write_branch_commit_id(repo_root, head_content, commit_id)
        print(f"Committed {len(committed_files_info)} file(s) to branch '{head_content}' (commit {commit_id}):")
    else:
        # HEAD is detached or points to something not in refs/heads (e.g. a commit_id directly)
        write_head(repo_root, commit_id) # Update HEAD to new commit_id directly
        print(f"Committed {len(committed_files_info)} file(s) while in 'detached HEAD' state (commit {commit_id}):")
        print("HEAD is now at this commit. To save this work, create a new branch:")
        print(f"  docvcs branch <new-branch-name> {commit_id}")


    for info in committed_files_info:
        print(f"  - {info}")


def log_command(args):
    """Displays commit log."""
    repo_root = get_repo_root()
    if not repo_root:
        print("Error: Not a DocVCS repository. Initialize with 'docvcs init' first.")
        return

    versions_path = get_versions_path(repo_root)
    if not os.path.exists(versions_path) or not os.listdir(versions_path):
        print("No commits yet.")
        return

    all_versions = []
    for filename in os.listdir(versions_path):
        if filename.endswith(".json"):
            version_data = read_json_file(os.path.join(versions_path, filename))
            if version_data: # Ensure file was not empty or malformed
                 all_versions.append(version_data)

    # Group by commit_id and sort by timestamp
    commits = {}
    for v in all_versions:
        commit_id = v.get("commit_id")
        if commit_id not in commits:
            commits[commit_id] = {
                "id": commit_id,
                "message": v.get("message"),
                "author": v.get("author"),
                "timestamp": v.get("timestamp"),
                "files": []
            }
        commits[commit_id]["files"].append(v.get("filepath_at_commit", "N/A"))

    # Sort commits by timestamp (most recent first)
    sorted_commits = sorted(commits.values(), key=lambda c: c["timestamp"], reverse=True)

    if not sorted_commits:
        print("No valid commit data found.")
        return

    # Get branch information for display
    head_content = read_head(repo_root)
    current_branches = list_branches(repo_root)
    commit_to_branches = {}
    for branch_name, commit_id_val in current_branches.items():
        if commit_id_val not in commit_to_branches:
            commit_to_branches[commit_id_val] = []
        commit_to_branches[commit_id_val].append(branch_name)


    for commit in sorted_commits:
        commit_id_val = commit['id']
        branch_decorations = []
        is_head_commit = False

        # Check if HEAD points to this commit
        if head_content == commit_id_val: # Detached HEAD at this commit
            branch_decorations.append("HEAD detached at")
            is_head_commit = True
        
        # Check if any branches point to this commit
        if commit_id_val in commit_to_branches:
            for branch_name in sorted(commit_to_branches[commit_id_val]):
                if head_content == branch_name: # HEAD points to this branch
                    branch_decorations.append(f"HEAD -> {branch_name}")
                    is_head_commit = True
                elif not is_head_commit or head_content != commit_id_val : # Avoid double listing if HEAD is also this branch
                    branch_decorations.append(branch_name)
        
        decoration_str = ""
        if branch_decorations:
            decoration_str = f" ({', '.join(branch_decorations)})"

        print("-" * 40)
        print(f"Commit:  {commit_id_val}{decoration_str}")
        print(f"Author:  {commit['author']}")
        print(f"Date:    {commit['timestamp']}")
        print(f"Message: {commit['message']}")
        print(f"Files:   {', '.join(sorted(list(set(commit['files']))))}")
    print("-" * 40)


def checkout_command(args):
    """Checks out a version of a file, an entire commit, or a branch."""
    repo_root = get_repo_root()
    if not repo_root:
        print("Error: Not a DocVCS repository. Initialize with 'docvcs init' first.")
        return

    target_name = args.version_id # This can be a commit_id or a branch_name
    target_filepath_arg = args.filepath
    actual_commit_id_to_checkout = None
    is_branch_checkout = False

    # Try to resolve target_name as a branch
    branch_commit_id = read_branch_commit_id(repo_root, target_name)
    if branch_commit_id:
        if target_filepath_arg:
            print("Error: Cannot checkout a specific file when switching branches. Switch branch first, then checkout file if needed.")
            return
        actual_commit_id_to_checkout = branch_commit_id
        is_branch_checkout = True
        print(f"Switching to branch '{target_name}' (commit {actual_commit_id_to_checkout}).")
    else:
        # Assume target_name is a commit_id
        # A more robust check would be to see if it's a valid commit format or exists in versions
        if len(target_name) == 36: # Basic UUID check
            actual_commit_id_to_checkout = target_name
            if not target_filepath_arg: # Only set detached HEAD if checking out whole commit
                print(f"Checking out commit '{actual_commit_id_to_checkout}'. You are now in 'detached HEAD' state.")
            else:
                 print(f"Checking out file from commit '{actual_commit_id_to_checkout}'.")
        else:
            print(f"Error: Branch or commit '{target_name}' not found.")
            return

    if not actual_commit_id_to_checkout: # Should have been caught by now
        print(f"Error: Could not resolve '{target_name}' to a valid commit.")
        return

    versions_path = get_versions_path(repo_root)
    objects_path = get_objects_path(repo_root)
    versions_for_commit = []
    for filename in os.listdir(versions_path):
        if filename.endswith(".json"):
            version_data = read_json_file(os.path.join(versions_path, filename))
            if version_data and version_data.get("commit_id") == actual_commit_id_to_checkout:
                versions_for_commit.append(version_data)

    if not versions_for_commit:
        print(f"Error: No files found for commit ID '{actual_commit_id_to_checkout}'. It might be an invalid or empty commit.")
        # If it was a branch checkout, the branch might point to a non-existent/corrupt commit
        if is_branch_checkout:
             print(f"Branch '{target_name}' may be corrupted or pointing to a non-existent commit.")
        return

    checked_out_count = 0
    # If checking out a whole commit/branch, first note all files in that commit
    # to potentially remove files not present in the target commit (later enhancement, for now just overwrite)
    
    # First, remove all files currently tracked by DocVCS from the working directory
    # if we are doing a full branch/commit checkout.
    # This is a simple approach; more advanced would be to handle untracked files carefully.
    if not target_filepath_arg:
        # Get list of all files tracked by *any* version (simplistic, could be refined)
        all_tracked_files = set()
        docs_data = read_json_file(get_documents_filepath(repo_root), {})
        for f_path in docs_data.keys():
             all_tracked_files.add(os.path.join(repo_root, f_path))
        
        # For all files that were part of *this* specific commit we are checking out
        files_in_target_commit = {os.path.join(repo_root, v['filepath_at_commit']) for v in versions_for_commit}

        # Iterate through files in current working dir that are known to the repo
        # and remove them if they are not in the target commit.
        # This is a destructive action and needs careful consideration for user experience in a real tool.
        # For now, we will just overwrite, and new files will appear.
        # A more git-like behavior would be to remove files that are tracked but not in the target commit.
        pass # Placeholder for more complex file cleanup logic

    for version_meta in versions_for_commit:
        content_checksum = version_meta.get("content_checksum")
        committed_rel_filepath = version_meta.get("filepath_at_commit")

        if not content_checksum or not committed_rel_filepath:
            print(f"Warning: Incomplete version metadata found for commit '{actual_commit_id_to_checkout}'. Skipping an entry.")
            continue

        if target_filepath_arg:
            abs_target_filepath_arg = os.path.abspath(target_filepath_arg)
            rel_target_filepath_arg = os.path.relpath(abs_target_filepath_arg, repo_root)
            if rel_target_filepath_arg != committed_rel_filepath:
                continue

        source_object_path = os.path.join(objects_path, content_checksum)
        destination_path = os.path.join(repo_root, committed_rel_filepath)

        if not os.path.exists(source_object_path):
            print(f"Error: Object file '{content_checksum}' for '{committed_rel_filepath}' in commit '{actual_commit_id_to_checkout}' not found.")
            continue

        try:
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            shutil.copy2(source_object_path, destination_path)
            if not target_filepath_arg: # Avoid per-file message if checking out whole commit
                 pass
            else:
                print(f"Restored '{committed_rel_filepath}' to version from commit '{actual_commit_id_to_checkout}'.")
            checked_out_count += 1
        except Exception as e:
            print(f"Error restoring file '{committed_rel_filepath}': {e}")
        
        if target_filepath_arg and checked_out_count > 0:
            break # Specific file found and processed

    if checked_out_count > 0:
        if is_branch_checkout:
            write_head(repo_root, target_name) # Update HEAD to the branch name
            print(f"Successfully switched to branch '{target_name}'.")
        elif not target_filepath_arg: # Full commit checkout (detached HEAD)
            write_head(repo_root, actual_commit_id_to_checkout) # Update HEAD to the commit ID
            print(f"Successfully checked out commit '{actual_commit_id_to_checkout}'. HEAD is now detached.")
        # If only a file was checked out, HEAD doesn't change.
    elif checked_out_count == 0:
        if target_filepath_arg:
            print(f"File '{target_filepath_arg}' not found in commit '{actual_commit_id_to_checkout}'.")
        elif not is_branch_checkout : # Failed to checkout a commit_id
            print(f"No files were checked out for commit '{actual_commit_id_to_checkout}'.")
        # If is_branch_checkout and count is 0, other messages would have appeared.

# --- Branch Command Implementation ---

def branch_command(args):
    """Manages branches."""
    repo_root = get_repo_root()
    if not repo_root:
        print("Error: Not a DocVCS repository. Initialize with 'docvcs init' first.")
        return

    if args.branch_name: # Create a new branch
        if not is_valid_branch_name(args.branch_name):
            print(f"Error: Invalid branch name '{args.branch_name}'. Avoid spaces and special characters like . ~ ^ : ? * [ \\")
            return

        branch_filepath = get_branch_filepath(repo_root, args.branch_name)
        if os.path.exists(branch_filepath):
            print(f"Error: Branch '{args.branch_name}' already exists.")
            return

        # Determine the commit to point the new branch to
        commit_to_branch_from = args.commit_id
        if not commit_to_branch_from: # If no commit_id provided, use current HEAD's commit
            head_content = read_head(repo_root)
            if not head_content:
                print("Error: HEAD is missing or unreadable. Cannot determine current commit.")
                return
            
            if os.path.exists(get_branch_filepath(repo_root, head_content)): # HEAD points to a branch
                commit_to_branch_from = read_branch_commit_id(repo_root, head_content)
                if not commit_to_branch_from:
                    print(f"Error: Current branch '{head_content}' is unborn (has no commits yet). Cannot create new branch from it.")
                    return
            else: # HEAD is detached, points to a commit
                commit_to_branch_from = head_content
                # Validate this commit_id exists (optional, but good practice)
                # For simplicity, we'll assume it's valid if it's in HEAD and not a branch name
                if not len(commit_to_branch_from) == 36 : # Basic UUID check
                    print(f"Error: Detached HEAD does not point to a valid commit ID ('{commit_to_branch_from}'). Cannot create branch.")
                    return


        if not commit_to_branch_from: # Should be caught above
             print("Error: Could not determine a commit to branch from. No commits yet?")
             return

        # Check if the source commit actually exists (by checking if any version file references it)
        source_commit_exists = False
        versions_path = get_versions_path(repo_root)
        if os.path.exists(versions_path):
            for fname in os.listdir(versions_path):
                if fname.endswith(".json"):
                    v_data = read_json_file(os.path.join(versions_path, fname))
                    if v_data and v_data.get("commit_id") == commit_to_branch_from:
                        source_commit_exists = True
                        break
        if not source_commit_exists and commit_to_branch_from != DEFAULT_BRANCH_NAME : # Allow creating branch if repo is empty and target is default (which is also empty)
            # Check if we are trying to branch from default before first commit
            if not (read_head(repo_root) == DEFAULT_BRANCH_NAME and not read_branch_commit_id(repo_root, DEFAULT_BRANCH_NAME)):
                 print(f"Error: Commit '{commit_to_branch_from}' to branch from does not exist.")
                 return


        write_branch_commit_id(repo_root, args.branch_name, commit_to_branch_from)
        print(f"Branch '{args.branch_name}' created, pointing to commit '{commit_to_branch_from}'.")

    else: # List branches
        head_content = read_head(repo_root)
        current_branches = list_branches(repo_root)
        if not current_branches and (not head_content or head_content == DEFAULT_BRANCH_NAME):
            print(f"* {DEFAULT_BRANCH_NAME} (no commits yet)")
            return
        elif not current_branches and head_content: # Detached HEAD, no other branches
             print(f"* (HEAD detached at {head_content[:7]})")
             return


        for branch_name in sorted(current_branches.keys()):
            prefix = "  "
            if branch_name == head_content:
                prefix = "* "
            print(f"{prefix}{branch_name}")
        
        if head_content and head_content not in current_branches: # Detached HEAD state
            print(f"* (HEAD detached at {head_content[:7]})")

def main():
    parser = argparse.ArgumentParser(description="DocVCS - A simple document version control system.")
    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True)

    # Init command
    parser_init = subparsers.add_parser("init", help="Initialize a new repository.")
    parser_init.add_argument("directory", nargs="?", default=".", help="Directory to initialize (default: current directory).")
    parser_init.set_defaults(func=init_command)

    # Add command
    parser_add = subparsers.add_parser("add", help="Add file(s) to the staging area.")
    parser_add.add_argument("files", nargs="+", help="File(s) to add.")
    parser_add.set_defaults(func=add_command)

    # Commit command
    parser_commit = subparsers.add_parser("commit", help="Commit staged changes.")
    parser_commit.add_argument("-m", "--message", required=True, help="Commit message.")
    parser_commit.set_defaults(func=commit_command)

    # Log command
    parser_log = subparsers.add_parser("log", help="Display commit log.")
    parser_log.set_defaults(func=log_command)

    # Checkout command
    parser_checkout = subparsers.add_parser("checkout", help="Checkout a version of file(s).")
    parser_checkout.add_argument("version_id", help="Commit ID to checkout.")
    parser_checkout.add_argument("filepath", nargs="?", help="Specific file to checkout (optional).")
    parser_checkout.set_defaults(func=checkout_command)

    # Diff command
    parser_diff = subparsers.add_parser("diff", help="Show differences between file versions.")
    parser_diff.add_argument("filepath", help="File to diff.")
    parser_diff.add_argument("--commit1", help="First commit ID (or 'WORK' for working directory). Defaults to latest committed version.", default=None)
    parser_diff.add_argument("--commit2", help="Second commit ID (or 'WORK' for working directory). Defaults to working directory content.", default="WORK")
    parser_diff.set_defaults(func=diff_command)

    # Branch command
    parser_branch = subparsers.add_parser("branch", help="Manage branches.")
    parser_branch.add_argument("branch_name", nargs="?", help="Name of the branch to create.")
    parser_branch.add_argument("commit_id", nargs="?", help="Commit ID to base the new branch on (optional, defaults to current HEAD's commit).")
    parser_branch.set_defaults(func=branch_command)

    args = parser.parse_args()
    args.func(args)

# --- New/Modified Helper Functions for Diff / Branch ---

def get_file_content_by_checksum(repo_root, checksum):
    """Reads the content of an object file given its checksum."""
    objects_path = get_objects_path(repo_root)
    object_filepath = os.path.join(objects_path, checksum)
    if not os.path.exists(object_filepath):
        # print(f"Debug: Object file not found: {object_filepath}")
        return None
    try:
        with open(object_filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        # print(f"Debug: Error reading object file {object_filepath}: {e}")
        return None

def get_version_metadata_for_file(repo_root, rel_filepath, commit_id=None):
    """
    Retrieves version metadata for a specific file.
    If commit_id is given, finds metadata for that commit.
    If commit_id is None, finds the latest committed version metadata.
    """
    versions_path = get_versions_path(repo_root)
    relevant_versions = []

    if not os.path.exists(versions_path):
        return None

    for filename in os.listdir(versions_path):
        if not filename.endswith(".json"):
            continue
        version_data = read_json_file(os.path.join(versions_path, filename))
        if not version_data:
            continue

        # Check if this version metadata is for the target file
        if version_data.get("filepath_at_commit") == rel_filepath:
            if commit_id: # Specific commit requested
                if version_data.get("commit_id") == commit_id:
                    relevant_versions.append(version_data) # Should be only one per file per commit
            else: # Latest version requested
                relevant_versions.append(version_data)

    if not relevant_versions:
        return None

    if commit_id: # If a specific commit was requested, there should be at most one
        return relevant_versions[0] if relevant_versions else None
    else: # Sort by timestamp to find the latest
        relevant_versions.sort(key=lambda v: v.get("timestamp", ""), reverse=True)
        return relevant_versions[0]


# --- Diff Command Implementation ---

def diff_command(args):
    """Shows differences between file versions."""
    repo_root = get_repo_root()
    if not repo_root:
        print("Error: Not a DocVCS repository. Initialize with 'docvcs init' first.")
        return

    abs_filepath = os.path.abspath(args.filepath)
    if not abs_filepath.startswith(repo_root + os.sep):
        print(f"Error: File '{args.filepath}' is outside the repository.")
        return
    rel_filepath = os.path.relpath(abs_filepath, repo_root)

    content1, label1 = None, ""
    content2, label2 = None, ""

    # Determine content and label for the first version (commit1 or latest)
    if args.commit1 and args.commit1.upper() != "WORK":
        # Specific commit for version 1
        meta1 = get_version_metadata_for_file(repo_root, rel_filepath, args.commit1)
        if not meta1:
            print(f"Error: File '{rel_filepath}' not found in commit '{args.commit1}'.")
            # Treat as empty content if not found for diffing purposes
            content1 = ""
            label1 = f"{rel_filepath} (Commit {args.commit1} - Not Found)"
        else:
            content1 = get_file_content_by_checksum(repo_root, meta1["content_checksum"])
            if content1 is None:
                print(f"Error: Could not read content for '{rel_filepath}' from commit '{args.commit1}' (checksum: {meta1['content_checksum']}).")
                content1 = "" # Treat as empty
            label1 = f"{rel_filepath} (Commit {args.commit1})"
    elif args.commit1 and args.commit1.upper() == "WORK":
        # Working directory for version 1 (explicitly)
        if not os.path.exists(abs_filepath):
            print(f"Error: File '{rel_filepath}' not found in working directory.")
            content1 = ""
        else:
            try:
                with open(abs_filepath, 'r', encoding='utf-8') as f:
                    content1 = f.read()
            except Exception as e:
                print(f"Error reading working directory file {rel_filepath}: {e}")
                content1 = ""
        label1 = f"{rel_filepath} (Working Directory)"
    else:
        # Default for version 1: Latest committed version
        latest_meta = get_version_metadata_for_file(repo_root, rel_filepath)
        if not latest_meta:
            print(f"Info: File '{rel_filepath}' is not tracked or has no committed versions.")
            # If comparing against working dir, and file is untracked, working dir is "new"
            if args.commit2 and args.commit2.upper() == "WORK":
                 content1 = "" # Empty content for "latest committed"
                 label1 = f"{rel_filepath} (No committed versions)"
            else: # Comparing two non-existent versions or untracked vs specific commit
                print(f"Cannot perform diff if '{rel_filepath}' has no committed versions and not comparing to WORK.")
                return
        else:
            content1 = get_file_content_by_checksum(repo_root, latest_meta["content_checksum"])
            if content1 is None:
                print(f"Error: Could not read content for latest version of '{rel_filepath}' (checksum: {latest_meta['content_checksum']}).")
                content1 = "" # Treat as empty
            label1 = f"{rel_filepath} (Latest Commit: {latest_meta['commit_id'][:7]})"


    # Determine content and label for the second version (commit2 or working directory)
    if args.commit2 and args.commit2.upper() != "WORK":
        # Specific commit for version 2
        meta2 = get_version_metadata_for_file(repo_root, rel_filepath, args.commit2)
        if not meta2:
            print(f"Error: File '{rel_filepath}' not found in commit '{args.commit2}'.")
            content2 = "" # Treat as empty
            label2 = f"{rel_filepath} (Commit {args.commit2} - Not Found)"
        else:
            content2 = get_file_content_by_checksum(repo_root, meta2["content_checksum"])
            if content2 is None:
                print(f"Error: Could not read content for '{rel_filepath}' from commit '{args.commit2}' (checksum: {meta2['content_checksum']}).")
                content2 = "" # Treat as empty
            label2 = f"{rel_filepath} (Commit {args.commit2})"
    else: # Default for version 2: Working directory
        if not os.path.exists(abs_filepath):
            print(f"Info: File '{rel_filepath}' not found in working directory.")
            content2 = "" # Treat as empty if not exists in work
            label2 = f"{rel_filepath} (Working Directory - Not Found)"
        else:
            try:
                with open(abs_filepath, 'r', encoding='utf-8') as f:
                    content2 = f.read()
            except Exception as e:
                print(f"Error reading working directory file {rel_filepath}: {e}")
                return # Cannot proceed if working file is unreadable
        label2 = f"{rel_filepath} (Working Directory)"

    # Handle cases where one of the contents couldn't be retrieved and is None
    if content1 is None: content1 = ""
    if content2 is None: content2 = ""

    if content1 == content2:
        print(f"No differences found for '{rel_filepath}' between specified versions.")
        print(f"  1: {label1}")
        print(f"  2: {label2}")
        return

    diff = difflib.unified_diff(
        content1.splitlines(keepends=True),
        content2.splitlines(keepends=True),
        fromfile=f"a/{label1}",
        tofile=f"b/{label2}",
        lineterm='\n'
    )

    sys.stdout.writelines(list(diff))


if __name__ == "__main__":
    main()
