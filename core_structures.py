"""
Core data structures for the document versioning system.
"""
import datetime
import hashlib
from typing import Dict, List, Optional

class User:
    """
    Represents a user in the versioning system.
    (Optional for now, but good to think about for future development)
    """
    def __init__(self, id: str, name: str, email: str):
        self.id: str = id
        self.name: str = name
        self.email: str = email

    def __repr__(self) -> str:
        return f"User(id='{self.id}', name='{self.name}', email='{self.email}')"

class Document:
    """
    Represents a document being tracked by the versioning system.
    """
    def __init__(self, id: str, filepath: str):
        self.id: str = id  # Unique identifier for the document
        self.filepath: str = filepath  # Relative path within the repository

    def __repr__(self) -> str:
        return f"Document(id='{self.id}', filepath='{self.filepath}')"

class Version:
    """
    Represents a specific version of a document.
    """
    def __init__(self,
                 id: str,
                 document_id: str,
                 timestamp: datetime.datetime,
                 author: str,  # For now, a simple string. Could be linked to a User object later.
                 message: str,
                 content: str): # For now, storing full content.
        self.id: str = id  # Unique identifier for this version
        self.document_id: str = document_id  # ID of the Document this is a version of
        self.timestamp: datetime.datetime = timestamp
        self.author: str = author
        self.message: str = message
        self.content: str = content # Actual content of the file for this version.
        # For diff-based storage later:
        # self.base_version_id: Optional[str] = None # ID of the version this diff is based on
        # self.diff_content: Optional[str] = None # The diff itself
        self.content_checksum: str = self._calculate_checksum(content)

    def _calculate_checksum(self, content: str) -> str:
        """Calculates the SHA256 checksum of the content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def __repr__(self) -> str:
        return (f"Version(id='{self.id}', document_id='{self.document_id}', "
                f"timestamp='{self.timestamp}', author='{self.author}', "
                f"content_checksum='{self.content_checksum}')")

class Repository:
    """
    Manages a collection of documents and their versions.
    """
    def __init__(self, path: str):
        self.path: str = path  # Filesystem path to the root of the repository
        # Metadata (like a .git directory) would be stored within this path.
        # For example, a subdirectory like '.vcs_meta' could store:
        # - A list/database of all Document objects.
        # - A list/database of all Version objects.
        # - Information about branches, tags, etc.
        # - The actual content of different versions (or diffs).
        #
        # self.documents: Dict[str, Document] = {} # Maps document_id to Document object
        # self.versions: Dict[str, List[Version]] = {} # Maps document_id to a list of its versions

    def __repr__(self) -> str:
        return f"Repository(path='{self.path}')"

# Example Usage (Optional - mainly for illustration, not part of the core structures)
if __name__ == '__main__':
    # Create a user (optional)
    # user1 = User(id="user001", name="Alice Wonderland", email="alice@example.com")

    # Create a document
    doc1_id = "doc001"
    doc1 = Document(id=doc1_id, filepath="notes/project_ideas.txt")
    print(f"Created Document: {doc1}")

    # Create a version of this document
    version1_content = "Initial thoughts on project X.\n- Feature A\n- Feature B"
    version1 = Version(
        id="v001",
        document_id=doc1_id,
        timestamp=datetime.datetime.now(),
        author="Alice", # Could be user1.name or user1.id
        message="Initial commit of project ideas.",
        content=version1_content
    )
    print(f"Created Version: {version1}")
    print(f"Version content checksum: {version1.content_checksum}")

    version2_content = "Initial thoughts on project X.\n- Feature A (revised)\n- Feature B\n- Feature C (new)"
    version2 = Version(
        id="v002",
        document_id=doc1_id,
        timestamp=datetime.datetime.now() + datetime.timedelta(hours=1),
        author="Alice",
        message="Added Feature C and revised Feature A.",
        content=version2_content
    )
    print(f"Created Version: {version2}")
    print(f"Version content checksum: {version2.content_checksum}")

    # Create a repository
    repo1 = Repository(path="/tmp/my_project_repo")
    print(f"Created Repository: {repo1}")

    # In a real system, the Repository class would have methods to add documents,
    # commit new versions, checkout versions, etc.
    # For example:
    # repo1.add_document(doc1)
    # repo1.commit(document_id=doc1_id, author="Alice", message="Further updates", content="New content here...")
    # checked_out_content = repo1.checkout(document_id=doc1_id, version_id="v001")
    # print(f"Content of doc1 at version v001: {checked_out_content}")
    #
    # Diff storage considerations for Version class:
    # Instead of storing `content: str`, we might have:
    # `base_version_id: Optional[str]` (None for the first version)
    # `patch: Optional[str]` (the diff from the base version)
    #
    # To reconstruct a version:
    # 1. If base_version_id is None, the content is stored directly (or as a full snapshot).
    # 2. If base_version_id is present, retrieve the base version's content,
    #    then apply the patch to get the current version's content.
    # This would require a diffing library (e.g., difflib) and a way to store/retrieve
    # these patches efficiently. The Repository would manage storing these version
    # components (full files or patches).
    pass
