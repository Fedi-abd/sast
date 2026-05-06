# Future Feature Implementation Notes

## GitHub URL Support (Sprint 3-4)

### Backend Changes:
1. **PathResolver._resolve_github()** in `scans/services/path_resolver.py`:
```python
   def _resolve_github(self, url: str) -> Tuple[str, bool]:
       temp_dir = tempfile.mkdtemp(prefix='scan_')
       subprocess.run(['git', 'clone', '--depth', '1', url, temp_dir], check=True)
       return (temp_dir, True)
```

2. **UI Changes:**
   - Add radio button: Local Path / GitHub URL
   - Validate GitHub URL format
   - Show "Cloning..." status

### Diagrams to Update:
- Sequence Diagram: Add "Clone Repository" step before "Run Adapter"

---

## File Upload Support (Sprint 2-3)

### Backend Changes:
1. **Project Model** - add FileField:
```python
   uploaded_file = models.FileField(upload_to='uploads/', null=True, blank=True)
```

2. **PathResolver._resolve_upload()**:
```python
   def _resolve_upload(self, file_path: str) -> Tuple[str, bool]:
       temp_dir = tempfile.mkdtemp(prefix='upload_')
       if file_path.endswith('.zip'):
           shutil.unpack_archive(file_path, temp_dir)
       else:
           shutil.copy(file_path, temp_dir)
       return (temp_dir, True)
```

3. **UI Changes:**
   - File upload form
   - Support .zip extraction
   - Progress indicator

### Diagrams to Update:
- Use Case Diagram: No changes needed
- Class Diagram: Add `uploaded_file` field to Project
- Sequence Diagram: Add "Extract Upload" step

---

## Current State (Sprint 1):
- ✅ Architecture supports all three types
- ✅ PathResolver abstraction in place
- ✅ Cleanup logic implemented
- ⏳ Only LOCAL path implemented
- ⏳ GitHub and Upload throw NotImplementedError
