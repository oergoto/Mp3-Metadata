import os
import random
import shutil
import sys

def prepare_test(src_root, dst_dir, count=20):
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    all_mp3s = []
    print(f"Scanning {src_root}...")
    for root, dirs, files in os.walk(src_root):
        for f in files:
            if f.lower().endswith(".mp3"):
                all_mp3s.append(os.path.join(root, f))
    
    print(f"Found {len(all_mp3s)} MP3 files.")
    
    selected = random.sample(all_mp3s, min(len(all_mp3s), count))
    
    print(f"Copying {len(selected)} files to {dst_dir}...")
    for src in selected:
        dst = os.path.join(dst_dir, os.path.basename(src))
        # Handle duplicate filenames in selection if any (unlikely from different folders but possible)
        if os.path.exists(dst):
            base, ext = os.path.splitext(os.path.basename(src))
            dst = os.path.join(dst_dir, f"{base}_{random.randint(1000,9999)}{ext}")
            
        shutil.copy2(src, dst)
        print(f"Copied: {os.path.basename(src)}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python prepare_test.py <src_dir> <dst_dir>")
        sys.exit(1)
        
    src_dir = sys.argv[1]
    dst_dir = sys.argv[2]
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    prepare_test(src_dir, dst_dir, count)
