import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from core.autoruns_parser import AutorunsParser

print("Testing autoruns parser with corrected field mapping...")

try:
    parser = AutorunsParser()
    print("Parser created successfully")
    
    print("Scanning (this may take a moment)...")
    # Try a quick scan to test
    entries = parser.scan(include_hash=False, verify_signature=False)
    print(f'Found {len(entries)} entries')

    if entries:
        first_entry = entries[0]
        print('First entry:')
        print(f'  Timestamp: {first_entry.timestamp}')
        print(f'  Location: {first_entry.location}')
        print(f'  Entry: {first_entry.entry}')
        print(f'  Description: {first_entry.description}')
        print(f'  Company: {first_entry.company}')
        print(f'  Image Path: {first_entry.image_path}')
        print(f'  Enabled: {first_entry.enabled}')
        print(f'  Category: {first_entry.category}')
        print(f'  Signer: {first_entry.signer}')
        print(f'  Version: {first_entry.version}')
        print(f'  Launch String: {first_entry.launch_string}')
        
        print("\nTest completed successfully!")
    else:
        print("No entries found (this might be expected)")

except Exception as e:
    print(f"Error occurred: {e}")
    import traceback
    traceback.print_exc()