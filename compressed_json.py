import zstandard as zstd
import json
import lzma
import bz2
import os
import io

from json.decoder import JSONDecodeError
from zstandard import ZstdError
from .binarysearch import basic_search_list

try:
    from IPython import embed
except ImportError:
    pass

class ExtensionExistsError(Exception):
    def __init__(self, extension):
        self.extension = extension

class CompressedJSONMetaclass(type):
    def __new__(cls, clsname, bases, attrs, extension):
        new_type = super().__new__(cls, clsname, bases, attrs)
        if not extension is None:
            if extension in cls.extension_to_type:
                raise ExtensionExistsError(extension)
            else:
                cls.extension_to_type[extension] = new_type
        return new_type

    @classmethod
    def get_class_from_filename(cls, filename):
        _, extension = os.path.splitext(filename)
        return cls.extension_to_type[extension]

class CompressedJSONReaderMetaclass(CompressedJSONMetaclass):
    extension_to_type = {}

class CompressedJSONWriterMetaclass(CompressedJSONMetaclass):
    extension_to_type = {}

class CompressedJSONReaderWriter:
    def __init__(self, f):
        self.compressed_file = f

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    @classmethod
    def from_filename(cls, filename, **kwargs):
        compressed_file = open(filename, cls.mode)
        return type(cls).get_class_from_filename(filename)(compressed_file,
                                                           **kwargs)
        
class CompressedJSONReader(CompressedJSONReaderWriter,
                           metaclass=CompressedJSONReaderMetaclass,
                           extension=None):
    mode = "rb"
    
    def __iter__(self):
        yield from self.read_json()

    def close(self):
        self.compressed_file.close()

class CompressedJSONWriter(CompressedJSONReaderWriter,
                           metaclass=CompressedJSONWriterMetaclass,
                           extension=None):
    mode = "wb"
    
    def write_json(self, d):
        self.writer.write((json.dumps(d) + "\n").encode("utf-8"))
        self.writer.flush()

    def close(self):
        #print("CLOSE")
        self.writer.close()
        self.compressed_file.close()
        
class ZSTCompressedJSONReader(CompressedJSONReader,
                              metaclass=CompressedJSONReaderMetaclass,
                              extension=".zst"):
    def __init__(self, f):
        super().__init__(f)
        self.dctx = zstd.ZstdDecompressor(max_window_size=2147483648)
        
    def read_json(self):
        """Read the file associated with this CompressedJSON object,
        treating the file as a zst-compressed file.
        
        This function parses the file's lines as json and yields each parsed
        json object line-by-line.
        """
        line_no = 0
        #try:
        with self.dctx.stream_reader(self.compressed_file) as reader:
            text_stream = io.TextIOWrapper(reader, encoding='utf-8')
            try:
                for line in text_stream:
                    # This strip seems to be necessary due to a bug in
                    # pushshift's API.
                    line = line.lstrip("\0")
                    try:
                        #print(line_no)
                        line_no += 1
                        # if line_no % 1000 == 0:
                        #     line_no += 1
                        #     print(line)
                        # if line_no >= 34116990:
                        #     print(line)
                        yield json.loads(line)
                    except (UnicodeDecodeError, JSONDecodeError) as e:
                        embed()
            except ZstdError as e:
                embed()
        # finally:
        #     pass
            #self.close()
            

class ZSTCompressedJSONWriter(CompressedJSONWriter,
                              metaclass=CompressedJSONWriterMetaclass,
                              extension=".zst"):
    def __init__(self, f, level=3, **compressor_kwargs):
        super().__init__(f)
        compressor = zstd.ZstdCompressor(level=level, **compressor_kwargs)
        self.writer = compressor.stream_writer(f)

class BZ2LikeCompressedJSONReaderMetaclass(CompressedJSONReaderMetaclass):
    def __new__(cls,
                clsname,
                bases,
                attrs,
                extension=None,
                comp_file_cls=None):
        new_type = super().__new__(cls,
                                   clsname,
                                   bases,
                                   attrs,
                                   extension=extension)
        new_type.read_json = cls.read_bz2_like_stream(comp_file_cls)
        return new_type

    @staticmethod
    def read_bz2_like_stream(comp_file_cls):
        """Creates a function to read JSON objects line-by-line from a
        compressed file.

        The function accepts a type, comp_file_cls, which can be used
        to construct an object for reading the file. The type should
        be a class that uses the same interface as bz2.BZ2File.
        """
        def _inner_stream(self):
            with comp_file_cls(self.compressed_file) as decompressed_file:
                for line in decompressed_file:
                    try:
                        yield json.loads(line)
                    except (UnicodeDecodeError, JSONDecodeError) as e:
                        embed()
        return _inner_stream

class BZ2CompressedJSONReader(CompressedJSONReader,
                              metaclass=BZ2LikeCompressedJSONReaderMetaclass,
                              extension=".bz2",
                              comp_file_cls=bz2.BZ2File):
    pass

class XZCompressedJSONReader(CompressedJSONReader,
                             metaclass=BZ2LikeCompressedJSONReaderMetaclass,
                             extension=".xz",
                             comp_file_cls=lzma.LZMAFile):
    pass

class BZ2CompressedJSONWriter(CompressedJSONWriter,
                              metaclass=CompressedJSONWriterMetaclass,
                              extension=".bz2"):
    def __init__(self, f, level=9, **comp_file_kwargs):
        super().__init__(f)
        self.writer = bz2.BZ2File(f,
                                  mode="wb",
                                  compresslevel=level,
                                  **comp_file_kwargs)

class XZCompressedJSONWriter(CompressedJSONWriter,
                             metaclass=CompressedJSONWriterMetaclass,
                             extension=".xz"):
    def __init__(self, f, **comp_file_kwargs):
        super().__init__(f)
        self.writer = lzma.LZMAFile(f, mode="wb", **comp_file_kwargs)

def read_compressed_json_from_filename(filename):
    _, extension = os.path.splitext(filename)
    reader_cls = CompressedJSONReaderMetaclass.extension_to_type[extension]
    with open(filename, "rb") as compressed_file:
        yield from reader_cls(compressed_file).read_json()


def read_all_in_directory(directory, exts, start_with=None, debug=False):
    files = list(sorted(os.listdir(directory)))
    if start_with:
        start_index = basic_search_list(files, start_with)
        if files[start_index] == start_with:
            files = files[start_index:]
        else:
            raise FileNotFoundError(start_with)
    for f in files:
        _, extension = os.path.splitext(f)
        file_path = os.path.join(directory, f)
        if extension in exts:
            if debug:
                print(f)
            yield from read_compressed_json_from_filename(file_path)
