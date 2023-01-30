import os

from compressed_json import CompressedJSONReader

def casefold_or_none(s):
    if not s is None:
        return s.casefold()
    else:
        return None
        
try:
    import progressbar
    
    def compressed_json_progress_wrapper(file_path):
        with progressbar.ProgressBar(
                max_value=os.path.getsize(file_path)
        ) as bar, CompressedJSONReader.from_filename(
            file_path
        ) as reader:
            for d in reader:
                yield d
                bar.update(reader.compressed_file.tell())
except ImportError:
    pass
        
