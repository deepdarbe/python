import os
import psutil
import pandas as pd

def get_system_resources():
    system_memory = psutil.virtual_memory().available
    system_cores = psutil.cpu_count(logical=False)
    return system_memory, system_cores

def find_files_with_extension(directory, extensions):
    matching_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_extension = os.path.splitext(file)[1].lower()
            if file_extension in extensions:
                matching_files.append(os.path.join(root, file))
    return matching_files

def filter_files_with_text(files, text):
    matching_files = []
    skipped_files = []
    for file in files:
        try:
            if file.lower().endswith('.xlsx'):
                df = pd.read_excel(file, engine='openpyxl')
                if df.applymap(lambda cell: text in str(cell)).any().any():
                    matching_files.append(file)
            else:
                with open(file, 'r', encoding='utf-8') as f:
                    file_contents = f.read()
                    if text in file_contents:
                        matching_files.append(file)
        except Exception as e:
            skipped_files.append(file)
            print(f"Hata ({file}): {e}")
    return matching_files, skipped_files

def main():
    search_directory = input("Lütfen arama yapmak istediğiniz dizini girin: ")
    extensions = input("Lütfen aradığınız dosya uzantılarını virgülle ayırarak girin (örn. .xlsx,.txt): ").lower().split(',')
    search_text = input("Lütfen aradığınız metni girin: ")
    
    total_memory, total_cores = get_system_resources()
    max_memory = total_memory * 0.6

    print(f"Toplam Bellek: {total_memory} bytes")
    print(f"Kullanılabilir Bellek: {max_memory} bytes")
    print(f"Toplam İşlemci Çekirdeği: {total_cores}")
    
    cache_file = os.path.join(search_directory, ".file_cache.txt")
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as cache:
            cached_files = cache.read().splitlines()
    else:
        cached_files = []

    matching_files = find_files_with_extension(search_directory, extensions)

    new_files = [file for file in matching_files if file not in cached_files]
    filtered_files, skipped_files = filter_files_with_text(new_files, search_text)

    if filtered_files:
        print("\nBulunan dosyalar:")
        for idx, file in enumerate(filtered_files, start=1):
            print(f"{idx}. {file}")
    else:
        print("Eşleşen dosya bulunamadı.")

    if new_files or skipped_files:
        with open(cache_file, 'a') as cache:
            for file in new_files + skipped_files:
                cache.write(file + '\n')

    unreachable_files = [file for file in cached_files if not os.path.exists(file)]
    if unreachable_files:
        print("\nUlaşılamayan dosyalar/dizinler:")
        for idx, file in enumerate(unreachable_files, start=1):
            print(f"{idx}. {file}")
        print("Bu dosyalar/dizinler artık mevcut değil.")

if __name__ == "__main__":
    main()
