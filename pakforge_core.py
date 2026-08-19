# PakForge parser backend. Use only with files you own or are authorized to modify.

import itertools as it
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import struct
import shutil
import os
import sys
import uuid
import hashlib
import platform
import subprocess
import tempfile
import base64
import ctypes
import ctypes.util
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import PurePath, Path
from typing import List, Dict, Tuple, Optional, Any
import time
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from rich import print as rprint
from rich.markup import escape
from rich.text import Text
from rich.align import Align
from rich.console import Group
from rich.box import HEAVY_EDGE, ROUNDED, DOUBLE_EDGE
from datetime import datetime
import pytz
import gmalg
from Crypto.Cipher import AES
from Crypto.Cipher.AES import MODE_CBC
from Crypto.Hash import SHA1
from Crypto.Util.Padding import unpad
from zstandard import ZstdDecompressor, ZstdCompressionDict, DICT_TYPE_AUTO, ZstdCompressor

console = Console(no_color=bool(os.environ.get('NO_COLOR') or os.environ.get('PAKFORGE_PLAIN')))

# ==================== NEON TERMINAL THEME ====================
NEON = {
    'purple': '#B026FF',
    'violet': '#7A2CFF',
    'blue': '#315CFF',
    'cyan': '#00E5FF',
    'green': '#39FF88',
    'pink': '#FF3DBB',
    'yellow': '#FFE66D',
    'red': '#FF4D6D',
    'muted': '#8B91A7',
}


def themed_prompt(prompt: str) -> str:
    """Render Rich markup prompts correctly for standard Termux input."""
    if not prompt:
        return f"[bold {NEON['purple']}]└──➤[/bold {NEON['purple']}] [bold {NEON['cyan']}]Input:[/bold {NEON['cyan']}] "
    return prompt


# ==================== SIMPLE BLOCK DISPLAY CLASS ====================

class SimpleBlockDisplay:
    """Simple display that shows each file and its blocks"""
    
    def __init__(self, total_files: int, pak_name: str):
        self.total_files = total_files
        self.pak_name = pak_name
        self.processed_files = 0
        self.current_file = ""
        self.current_file_idx = 0
        self.all_blocks = []  # Store all blocks for final summary
        self.total_fitted = 0
        self.total_skipped = 0
        
    def start_file(self, file_name: str, total_blocks: int):
        self.current_file_idx += 1
        self.current_file = file_name
        self.current_blocks = []
        self.current_total_blocks = total_blocks
        self.current_fitted = 0
        self.current_skipped = 0
        
        # Print file header
        console.print()
        console.print(f"[bold cyan]┌─────────────────────────────────────────────────────────────[/bold cyan]")
        console.print(f"[bold cyan]│[/] [bold yellow][{self.current_file_idx}/{self.total_files}][/] [bold green]{file_name}[/bold green] [dim]({total_blocks} blocks)[/dim]")
        console.print(f"[bold cyan]├─────────────────────────────────────────────────────────────[/bold cyan]")
        
    def add_block(self, block_idx: int, block_size: int, fitted: bool, compression_ratio: float = None):
        """Add a block result"""
        size_mb = block_size / (1024 * 1024)
        if fitted:
            self.current_fitted += 1
            self.total_fitted += 1
            ratio_str = f" [{compression_ratio:.1%}]" if compression_ratio else ""
            status = f"[green]✓ FITTED{ratio_str}[/green]"
        else:
            self.current_skipped += 1
            self.total_skipped += 1
            status = f"[red]✗ SKIPPED[/red]"
        
        console.print(f"[bold cyan]│[/]    Block {block_idx:3d}: {size_mb:>7.2f} MB  →  {status}")
        self.current_blocks.append({'fitted': fitted})
        
    def finish_file(self):
        """Finish current file"""
        total_blocks = len(self.current_blocks)
        
        if total_blocks > 0:
            if self.current_fitted == total_blocks:
                status = "[green]✓ ALL FITTED[/green]"
            elif self.current_fitted > 0:
                status = f"[yellow]✓ {self.current_fitted}/{total_blocks} FITTED[/yellow]"
            else:
                status = "[red]✗ ALL SKIPPED[/red]"
        else:
            status = "[green]✓ DONE[/green]"
        
        console.print(f"[bold cyan]└─────────────────────────────────────────────────────────────[/bold cyan]")
        console.print(f"  [dim]Result: {status}[/dim]")
        
        self.processed_files += 1
        self.all_blocks.extend(self.current_blocks)
        
    def final_summary(self):
        """Print final summary"""
        total_blocks = len(self.all_blocks)
        
        console.print()
        console.print(f"[bold green]╔═════════════════════════════════════════════════════════════════╗[/bold green]")
        console.print(f"[bold green]║[/] [bold yellow]REPACK SUMMARY[/bold yellow]")
        console.print(f"[bold green]║[/]")
        console.print(f"[bold green]║[/]   Total Files:   [bold cyan]{self.processed_files}[/bold cyan]")
        console.print(f"[bold green]║[/]   Total Blocks:  [bold cyan]{total_blocks}[/bold cyan]")
        console.print(f"[bold green]║[/]   Fitted Blocks: [bold green]{self.total_fitted}[/bold green]")
        console.print(f"[bold green]║[/]   Skipped Blocks:[bold red]{self.total_skipped}[/bold red]")
        if total_blocks > 0:
            success_rate = (self.total_fitted / total_blocks) * 100
            console.print(f"[bold green]║[/]   Success Rate:  [bold yellow]{success_rate:.1f}%[/bold yellow]")
        console.print(f"[bold green]╚═════════════════════════════════════════════════════════════════╝[/bold green]")

# ==================== PAKFORGE PARSER CORE ====================

ZUC_KEY = bytes.fromhex('01010101010101010101010101010101')
ZUC_IV = bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF')

RSA_MOD_1 = bytes.fromhex('CBE8B9F2504050EF9831B719E9A6249A6D238505ADE909BDE78C180DED6072A0C3347B8AF4780E1F212D952D82D4BF7F233C1ECA499E1F9D9A85B4FAD759F54BABC1666C5DE411EA9E4B2374425DD6C6F54333BBC8F2610FE6063E4D0D6C21A671A8F7C3740555E5DC06D4E1691C456DB4116C0C012BF7B206E8311AAAEC689952BF804EF638F09D5822B4117B114208F14DEB459E80CB770E5B0D7978E21F5E6CED4999D3583108221A7AB28B960277ADB5690A332784019D9C195BE4EA9EA0A09459010F236465DE0D59C3EF7324E954E1118D93EE19F299760C2CDB963CE87973EA5ECC9BBE81C27D4C7C8572AC07E9BCEAC9BD72AB7A56A3C0AD736ABCE4')
RSA_MOD_2 = bytes.fromhex('7F58E8A39A4DA4E87357DDD650EAA16D3B5CE95B213D1030A662566444796A78A84AE9AC3DBFFDE7F41094896696835DAF13B89E6EC2B84963B1B1BAF7151DA245C3FBFAE2A6AE18B2684D03F9229DE2C91440F2A3A3BCDE1E5680C16722A88039C73560D5D43F4B6562C2EEA5B1D926D86B51108A2643C70FB74D6442CE3A08339B8FD8F660AE88129B7AB8C46F2FA58124485CCCB1E987B05A6DA65A01858ED3F89905449AE42BB07290FCB9994BF22E26610BCABB9804783A3B9587917F3D97316EDDA15C5E13F79066407B55A93B291B68A4AC42A98D6E35FED84B14A792D154E62028DDAD20FC301951E5924BE9AD62FB719DD94CC30CAB871BEC4377A8')

SIMPLE1_DECRYPT_KEY = 121
SIMPLE2_DECRYPT_KEY = bytes.fromhex('E55B4ED1')
SIMPLE2_BLOCK_SIZE = 16

SM4_SECRET_4 = 'eb691efea914241317a8'
SM4_SECRET_2 = 'Q0hVTKey$as*1ZFlQCiA'
SM4_SECRET_NEW = [
    'xG2qW5lP7lV2iN5fN5pG',
    'xT1cJ6dL5wC0kK1rB4dK',
    'qC4jS5bZ6fL5xE6nD4zA',
    'gD4jQ2aL3bS3lC3xT0iW',
    'xU1yQ8wE9zY3gZ3bT5aE',
    'uQ3cO2dX7xY4xU7gH7iS',
    'gW1fR0jK6wQ4oN0oK1kZ',
    'aJ4pV7iZ7pU4wP2aC2cZ',
    'cX6jT3cM2oT3vK0kJ1qN',
    'iT2vS0cS6yT6cZ1sE1lO',
    'hM1pH9iY8wM9hT4lN5uJ',
    'kG6bC8jK0fL0dE4sH4mL',
    'dB6lB3vE0eZ8wM8rI0aC',
    'tP7sP7nI9rA2vQ4cV5yQ',
    'aT0cL1yN4pT3sZ7eM2vY',
    'uV6fU8fC9zN3mP5dH8mN'
]

EM_SIMPLE1 = 1
EM_SIMPLE2 = 16
EM_SM4_2 = 2
EM_SM4_4 = 4
EM_SM4_NEW_BASE = 31
EM_SM4_NEW_MASK = ~EM_SM4_NEW_BASE
EM_UNKNOWN_17 = 17

# Tencent/UE entry metadata uses these methods.  Rejecting an unknown method
# during a rebuild is safer than silently writing plaintext with an encrypted
# flag, which produces an unreadable entry in an offline test project.
SUPPORTED_ENCRYPTION_METHODS = {
    EM_SIMPLE1,
    EM_SIMPLE2,
    EM_SM4_2,
    EM_SM4_4,
    EM_UNKNOWN_17,
}

CM_NONE = 0
CM_ZLIB = 1
CM_OODLE = 3
CM_ZSTD = 6
CM_ZSTD_DICT = 8
CM_MASK = 15
SUPPORTED_COMPRESSION_METHODS = {CM_NONE, CM_ZLIB, CM_OODLE, CM_ZSTD, CM_ZSTD_DICT}

# Oodle's public compressor enum uses Kraken (8) as the broadly compatible
# default codec. The DLL is optional and must be supplied by the user; PakForge
# never downloads or bundles this proprietary runtime.
OODLE_CODEC_KRAKEN = 8
OODLE_LEVEL_NORMAL = 4


def normalize_pak_path(path: str | PurePath) -> str:
    """Return a canonical, relative PAK path without changing its case.

    PAK directory indexes use forward slashes even on Windows.  Keeping the
    relative path separate from the mount point is important: the mount point
    is serialized exactly as stored in the source index, while entry hashes are
    calculated from the normalized asset path only.
    """
    value = str(path).replace('\\', '/')
    while value.startswith('./'):
        value = value[2:]
    return value.lstrip('/')


def calculate_tencent_hashes(raw_data: bytes, full_path: str | PurePath, version: int) -> dict[str, object]:
    """Calculate the deterministic hashes used by Tencent-style entries.

    ``content_hash`` is per-entry and covers the uncompressed bytes.  The
    20-byte ``unk2`` field in this parser is the per-entry path hash.  Some
    Tencent variants also expose a footer ``content_org_hash``; it is returned
    here for callers that have a format-specific rule for that whole-PAK
    field, but it must not be confused with the per-entry field.
    """
    normalized = normalize_pak_path(full_path)
    lower_path = normalized.lower()
    stem = PurePath(normalized).stem.lower()
    return {
        'content_hash': SHA1.new(raw_data).digest(),
        'content_org_hash': SHA1.new(raw_data).digest() if version >= 12 else None,
        'stem_hash': zlib.crc32(stem.encode('utf-32le')) & 0xFFFFFFFF,
        'unk2': SHA1.new(lower_path.encode('utf-8')).digest(),
    }


def validate_encryption_metadata(encrypted: bool, encryption_method: int, version: int) -> None:
    """Validate the entry encryption flag/method pair before serialization."""
    if not encrypted:
        return
    # Versions before 12 do not serialize an encryption-method field.  Keep
    # their legacy flag readable, but validate explicit v12+ methods strictly.
    if version >= 12 and encryption_method not in SUPPORTED_ENCRYPTION_METHODS:
        raise ValueError(
            f'Unsupported encrypted-entry method {encryption_method}; '
            f'expected one of {sorted(SUPPORTED_ENCRYPTION_METHODS)}'
        )


class SM4:
    _S_BOX = bytes([
        52, 102, 37, 116, 137, 120, 228, 169, 90, 65, 188, 122, 214, 22, 33, 35,
        77, 97, 218, 148, 155, 223, 19, 60, 105, 58, 49, 10, 95, 215, 153, 149,
        241, 174, 114, 61, 7, 96, 36, 182, 152, 238, 196, 162, 45, 136, 221, 141,
        4, 234, 187, 17, 202, 62, 93, 161, 246, 63, 176, 151, 128, 71, 43, 166,
        230, 247, 217, 177, 89, 192, 124, 190, 84, 40, 183, 126, 79, 248, 67, 110,
        160, 80, 14, 245, 144, 184, 251, 163, 123, 98, 25, 70, 3, 42, 185, 143,
        159, 119, 180, 91, 131, 135, 8, 235, 226, 30, 66, 240, 15, 232, 113, 106,
        117, 173, 85, 31, 181, 171, 51, 250, 127, 21, 189, 133, 216, 6, 104, 179,
        82, 48, 72, 11, 0, 237, 239, 178, 87, 142, 231, 108, 213, 229, 46, 83,
        130, 5, 249, 129, 244, 86, 191, 140, 75, 227, 219, 74, 145, 76, 44, 211,
        64, 41, 78, 32, 20, 54, 121, 9, 111, 209, 55, 224, 57, 12, 138, 146,
        56, 18, 53, 109, 225, 253, 147, 154, 23, 212, 201, 156, 107, 132, 38, 157,
        175, 118, 193, 158, 208, 150, 197, 203, 233, 115, 73, 210, 205, 100, 195, 199,
        1, 125, 243, 172, 252, 222, 164, 68, 50, 27, 194, 186, 28, 2, 198, 39,
        69, 139, 242, 24, 167, 16, 81, 29, 200, 207, 99, 255, 47, 13, 88, 206,
        101, 165, 220, 26, 59, 134, 254, 34, 92, 168, 94, 103, 170, 236, 112, 204
    ])
    _FK = [1184304796, 1270900830, 1493524870, 3164752158]
    _CK = [964907, 973793155, 2654690407, 2916866751, 2071233739, 1226140771, 3348805095, 2045549823, 388349611, 800627875, 612403927, 3721562911, 1195432523, 3150178931, 612053223, 2445162591, 67183755, 1174197155, 1393249511, 3331183455, 3822152747, 1332317203, 1804781383, 1990130463, 1282653851, 3376591251, 2910902311, 925872959, 332098219, 735840931, 396665415, 3588844719]
    
    @staticmethod
    def ROL32(x, n):
        return (x << n) & 0xFFFFFFFF | (x >> (32 - n))
    
    @staticmethod
    def _BS(X):
        return (SM4._S_BOX[X >> 24 & 255] << 24 | 
                SM4._S_BOX[X >> 16 & 255] << 16 | 
                SM4._S_BOX[X >> 8 & 255] << 8 | 
                SM4._S_BOX[X & 255])
    
    @staticmethod
    def _T0(X):
        X = SM4._BS(X)
        return X ^ SM4.ROL32(X, 2) ^ SM4.ROL32(X, 10) ^ SM4.ROL32(X, 18) ^ SM4.ROL32(X, 24)
    
    @staticmethod
    def _T1(X):
        X = SM4._BS(X)
        return X ^ SM4.ROL32(X, 13) ^ SM4.ROL32(X, 23)
    
    @staticmethod
    def _key_expand(key: bytes, rkey: list):
        K0 = int.from_bytes(key[0:4], 'big') ^ SM4._FK[0]
        K1 = int.from_bytes(key[4:8], 'big') ^ SM4._FK[1]
        K2 = int.from_bytes(key[8:12], 'big') ^ SM4._FK[2]
        K3 = int.from_bytes(key[12:16], 'big') ^ SM4._FK[3]
        for i in range(0, 32, 4):
            K0 = K0 ^ SM4._T1(K1 ^ K2 ^ K3 ^ SM4._CK[i])
            rkey[i] = K0
            K1 = K1 ^ SM4._T1(K2 ^ K3 ^ K0 ^ SM4._CK[i + 1])
            rkey[i + 1] = K1
            K2 = K2 ^ SM4._T1(K3 ^ K0 ^ K1 ^ SM4._CK[i + 2])
            rkey[i + 2] = K2
            K3 = K3 ^ SM4._T1(K0 ^ K1 ^ K2 ^ SM4._CK[i + 3])
            rkey[i + 3] = K3
    
    @classmethod
    def key_length(cls):
        return 16
    
    @classmethod
    def block_length(cls):
        return 16
    
    def __init__(self, key: bytes):
        if len(key) != self.key_length():
            raise ValueError(f'Key must be {self.key_length()} bytes')
        else:
            self._key = key
            self._rkey = [0] * 32
            SM4._key_expand(self._key, self._rkey)
            self._block_buffer = bytearray()
    
    def encrypt(self, block: bytes) -> bytes:
        if len(block) != self.block_length():
            raise ValueError(f'Block must be {self.block_length()} bytes')
        else:
            RK = self._rkey
            X0 = int.from_bytes(block[0:4], 'big')
            X1 = int.from_bytes(block[4:8], 'big')
            X2 = int.from_bytes(block[8:12], 'big')
            X3 = int.from_bytes(block[12:16], 'big')
            for i in range(0, 32, 4):
                X0 = X0 ^ SM4._T0(X1 ^ X2 ^ X3 ^ RK[i])
                X1 = X1 ^ SM4._T0(X2 ^ X3 ^ X0 ^ RK[i + 1])
                X2 = X2 ^ SM4._T0(X3 ^ X0 ^ X1 ^ RK[i + 2])
                X3 = X3 ^ SM4._T0(X0 ^ X1 ^ X2 ^ RK[i + 3])
            BUFFER = self._block_buffer
            BUFFER.clear()
            BUFFER.extend(X3.to_bytes(4, 'big'))
            BUFFER.extend(X2.to_bytes(4, 'big'))
            BUFFER.extend(X1.to_bytes(4, 'big'))
            BUFFER.extend(X0.to_bytes(4, 'big'))
            return bytes(BUFFER)
    
    def decrypt(self, block: bytes) -> bytes:
        if len(block) != self.block_length():
            raise ValueError(f'Block must be {self.block_length()} bytes')
        else:
            RK = self._rkey
            X0 = int.from_bytes(block[0:4], 'big')
            X1 = int.from_bytes(block[4:8], 'big')
            X2 = int.from_bytes(block[8:12], 'big')
            X3 = int.from_bytes(block[12:16], 'big')
            for i in range(0, 32, 4):
                X0 = X0 ^ SM4._T0(X1 ^ X2 ^ X3 ^ RK[31 - i])
                X1 = X1 ^ SM4._T0(X2 ^ X3 ^ X0 ^ RK[30 - i])
                X2 = X2 ^ SM4._T0(X3 ^ X0 ^ X1 ^ RK[29 - i])
                X3 = X3 ^ SM4._T0(X0 ^ X1 ^ X2 ^ RK[28 - i])
            BUFFER = self._block_buffer
            BUFFER.clear()
            BUFFER.extend(X3.to_bytes(4, 'big'))
            BUFFER.extend(X2.to_bytes(4, 'big'))
            BUFFER.extend(X1.to_bytes(4, 'big'))
            BUFFER.extend(X0.to_bytes(4, 'big'))
            return bytes(BUFFER)

class Misc:
    @staticmethod
    def pad_to_n(data: bytes, n: int) -> bytes:
        assert n > 0
        padding = n - len(data) % n
        if padding == n:
            return data
        else:
            return data + b'\x00' * padding
    @staticmethod
    def align_up(x: int, n: int) -> int:
        return (x + n - 1) // n * n

class Reader:
    def __init__(self, buffer, cursor=0):
        self._buffer = buffer
        self._cursor = cursor
    def u1(self, move_cursor=True) -> int:
        return self.unpack('B', move_cursor=move_cursor)[0]
    def u4(self, move_cursor=True) -> int:
        return self.unpack('<I', move_cursor=move_cursor)[0]
    def u8(self, move_cursor=True) -> int:
        return self.unpack('<Q', move_cursor=move_cursor)[0]
    def i1(self, move_cursor=True) -> int:
        return self.unpack('b', move_cursor=move_cursor)[0]
    def i4(self, move_cursor=True) -> int:
        return self.unpack('<i', move_cursor=move_cursor)[0]
    def i8(self, move_cursor=True) -> int:
        return self.unpack('<q', move_cursor=move_cursor)[0]
    def s(self, n: int, move_cursor=True) -> bytes:
        return self.unpack(f'{n}s', move_cursor=move_cursor)[0]
    def unpack(self, f: str, offset=0, move_cursor=True):
        x = struct.unpack_from(f, self._buffer, self._cursor + offset)
        if move_cursor:
            self._cursor += struct.calcsize(f)
        return x
    def string(self, move_cursor=True) -> str:
        length = self.i4(move_cursor=move_cursor)
        if length == 0:
            return str()
        else:
            assert length > 0
            offset = 0 if move_cursor else 4
            return self.unpack(f'{length}s', offset=offset, move_cursor=move_cursor)[0].rstrip(b'\x00').decode()

class PakInfo:
    def __init__(self, buffer, keystream: List[int]):
        def decrypt_index_encrypted(x: int) -> int:
            MASK_8 = 255
            return (x ^ keystream[3]) & MASK_8
        def decrypt_magic(x: int) -> int:
            return x ^ keystream[2]
        def decrypt_index_hash(x: bytes) -> bytes:
            key = struct.pack('<5I', *keystream[4:][:5])
            assert len(x) == len(key)
            return bytes((a ^ b for a, b in zip(x, key)))
        def decrypt_index_size(x: int) -> int:
            return x ^ (keystream[10] << 32 | keystream[11])
        def decrypt_index_offset(x: int) -> int:
            return x ^ (keystream[0] << 32 | keystream[1])
        reader = Reader(buffer[-PakInfo._mem_size((-1)):])
        self.index_encrypted = decrypt_index_encrypted(reader.u1()) == 1
        self.magic = decrypt_magic(reader.u4())
        self.version = reader.u4()
        self.index_hash = decrypt_index_hash(reader.s(20)) if self.version >= 6 else bytes()
        self.index_size = decrypt_index_size(reader.u8())
        self.index_offset = decrypt_index_offset(reader.u8())
        if self.version <= 3:
            self.index_encrypted = False
    @staticmethod
    def _mem_size(_: int) -> int:
        return 45

class TencentPakInfo(PakInfo):
    def __init__(self, buffer, keystream: List[int]):
        def decrypt_unk(x: bytes) -> bytes:
            key = struct.pack('<8I', *keystream[7:][:8])
            assert len(x) == len(key)
            return bytes((a ^ b for a, b in zip(x, key)))
        def decrypt_stem_hash(x: int) -> int:
            return x ^ keystream[8]
        def decrypt_unk_hash(x: int) -> int:
            return x ^ keystream[9]
        super().__init__(buffer, keystream)
        reader = Reader(buffer[-TencentPakInfo._mem_size(self.version):])
        self.unk1 = decrypt_unk(reader.s(32)) if self.version >= 7 else bytes()
        self.packed_key = reader.s(256) if self.version >= 8 else bytes()
        self.packed_iv = reader.s(256) if self.version >= 8 else bytes()
        self.packed_index_hash = reader.s(256) if self.version >= 8 else bytes()
        self.stem_hash = decrypt_stem_hash(reader.u4()) if self.version >= 9 else 0
        self.unk2 = decrypt_unk_hash(reader.u4()) if self.version >= 9 else 0
        self.content_org_hash = reader.s(20) if self.version >= 12 else bytes()
    @staticmethod
    def _mem_size(version: int) -> int:
        size_for_7 = 32 if version >= 7 else 0
        size_for_8 = 768 if version >= 8 else 0
        size_for_9 = 8 if version >= 9 else 0
        size_for_12 = 20 if version >= 12 else 0
        return PakInfo._mem_size(version) + size_for_7 + size_for_8 + size_for_9 + size_for_12

class PakCompressedBlock:
    def __init__(self, reader: Reader):
        self.start = reader.u8()
        self.end = reader.u8()

@dataclass
class TencentPakEntry:
    def __init__(self, reader: Reader, version: int):
        self.content_hash = reader.s(20)
        if version <= 1:
            _ = reader.u8()
        self.offset = reader.u8()
        self.uncompressed_size = reader.u8()
        self.compression_method = reader.u4() & CM_MASK
        self.size = reader.u8()
        self.unk1 = reader.u1() if version >= 5 else 0
        self.unk2 = reader.s(20) if version >= 5 else bytes()
        if self.compression_method != 0 and version >= 3:
            self.compressed_blocks = [PakCompressedBlock(reader) for _ in range(reader.u4())]
        else:
            self.compressed_blocks = []
        self.compression_block_size = reader.u4() if version >= 4 else 0
        self.encrypted = reader.u1() == 1 if version >= 4 else False
        self.encryption_method = reader.u4() if version >= 12 else 0
        self.index_new_sep = reader.u4() if version >= 12 else 0

class PakCrypto:
    class _LCG:
        def __init__(self, seed: int):
            self.state = seed
        def next(self) -> int:
            MASK_32 = 4294967295
            MSB_1 = 2147483648
            def wrap(x: int) -> int:
                x &= MASK_32
                if not x & MSB_1:
                    return x
                else:
                    return (x + MSB_1 & MASK_32) - MSB_1
            x1 = wrap(1103515245 * self.state)
            self.state = wrap(x1 + 12345)
            x2 = wrap(x1 + 77880) if self.state < 0 else self.state
            return (x2 >> 16 & MASK_32) % 32767
    @staticmethod
    def zuc_keystream() -> List[int]:
        zuc = gmalg.ZUC(ZUC_KEY, ZUC_IV)
        return [struct.unpack('>I', zuc.generate())[0] for _ in range(16)]
    @staticmethod
    def _xorxor(buffer, x) -> bytes:
        return bytes((buffer[i] ^ x[i % len(x)] for i in range(len(buffer))))
    @staticmethod
    def _hashhash(buffer, n: int) -> bytes:
        result = bytes()
        for i in range(math.ceil(n / SHA1.digest_size)):
            result += SHA1.new(buffer).digest()
        if len(result) >= n:
            result = result[:n]
            return result
        else:
            result += b'\x00' * (n - len(result))
            return result
    @staticmethod
    def _meowmeow(buffer) -> bytes:
        def unpad(x):
            skip = 1 + next((i for i in range(len(x)) if x[i]!= 0))
            return x[skip:]
        if len(buffer) < 43:
            return bytes()
        else:
            x1 = buffer[1:][:SHA1.digest_size]
            x2 = buffer[SHA1.digest_size + 1:]
            x1 = PakCrypto._xorxor(x1, PakCrypto._hashhash(x2, len(x1)))
            x2 = PakCrypto._xorxor(x2, PakCrypto._hashhash(x1, len(x2)))
            part1, m = (x2[:SHA1.digest_size], x2[SHA1.digest_size:])
            if part1!= SHA1.new(b'\x00' * SHA1.digest_size).digest():
                return bytes()
            else:
                return unpad(m)
    @staticmethod
    def rsa_extract(signature: bytes, modulus: bytes) -> bytes:
        c = int.from_bytes(signature, 'little')
        n = int.from_bytes(modulus, 'little')
        e = 65537
        m = pow(c, e, n).to_bytes(256, 'little').rstrip(b'\x00')
        return PakCrypto._meowmeow(Misc.pad_to_n(m, 4))
    @staticmethod
    def _decrypt_simple1(ciphertext) -> bytes:
        return bytes((x ^ SIMPLE1_DECRYPT_KEY for x in ciphertext))
    @staticmethod
    def _decrypt_simple2(ciphertext) -> bytes:
        class RollingKey:
            def __init__(self, initial_value: int):
                self._value = initial_value
            def update(self, x: int) -> int:
                self._value ^= x
                return self._value
        assert len(ciphertext) % SIMPLE2_BLOCK_SIZE == 0
        initial_key, = struct.unpack('<I', SIMPLE2_DECRYPT_KEY)
        rolling_key = RollingKey(initial_key)
        plaintext = (struct.pack('<I', rolling_key.update(x)) for x in struct.unpack(f'<{len(ciphertext) // 4}I', ciphertext))
        return bytes(it.chain.from_iterable(plaintext))
    @staticmethod
    @lru_cache(maxsize=1)
    def _derive_sm4_key(file_path: PurePath, encryption_method: int) -> bytes:
        part1 = file_path.stem.lower()
        if encryption_method == EM_SM4_2:
            secret = SM4_SECRET_2
        else:
            if encryption_method == EM_SM4_4:
                secret = SM4_SECRET_4
            else:
                index = (encryption_method - EM_SM4_NEW_BASE) % len(SM4_SECRET_NEW)
                secret = f'{SM4_SECRET_NEW[index]}{encryption_method}'
        return SHA1.new(str(part1 + secret).encode()).digest()[:SM4.key_length()]
    @staticmethod
    @lru_cache(maxsize=1)
    def _sm4_context_for_key(key: bytes) -> SM4:
        return SM4(key)
    @staticmethod
    def _decrypt_sm4(ciphertext, file_path: PurePath, encryption_method: int) -> bytes:
        assert len(ciphertext) % SM4.block_length() == 0
        key = PakCrypto._derive_sm4_key(file_path, encryption_method)
        sm4 = PakCrypto._sm4_context_for_key(key)
        return bytes(it.chain.from_iterable((sm4.decrypt(x) for x in it.batched(ciphertext, SM4.block_length()))))
    @staticmethod
    def decrypt_index(ciphertext, pak_info: TencentPakInfo) -> bytes:
        if pak_info.version > 7:
            key = PakCrypto.rsa_extract(pak_info.packed_key, RSA_MOD_1)
            iv = PakCrypto.rsa_extract(pak_info.packed_iv, RSA_MOD_1)
            assert len(key) == 32 and len(iv) == 32
            aes = AES.new(key, MODE_CBC, iv[:16])
            return unpad(aes.decrypt(ciphertext), AES.block_size)
        else:
            return bytes(PakCrypto._decrypt_simple1(ciphertext))
    @staticmethod
    def _is_simple1_method(encryption_method: int) -> bool:
        return encryption_method == EM_SIMPLE1
    @staticmethod
    def _is_simple2_method(encryption_method: int) -> bool:
        return encryption_method == EM_SIMPLE2 or encryption_method == 17
    @staticmethod
    def _is_sm4_method(encryption_method: int) -> bool:
        return encryption_method == EM_SM4_2 or encryption_method == EM_SM4_4 or encryption_method & EM_SM4_NEW_MASK!= 0
    @staticmethod
    def align_encrypted_content_size(n: int, encryption_method: int) -> int:
        if PakCrypto._is_simple2_method(encryption_method):
            return Misc.align_up(n, SIMPLE2_BLOCK_SIZE)
        else:
            if PakCrypto._is_sm4_method(encryption_method):
                return Misc.align_up(n, SM4.block_length())
            else:
                return n
    @staticmethod
    def decrypt_block(ciphertext, file: PurePath, encryption_method: int) -> bytes:
        if PakCrypto._is_simple1_method(encryption_method):
            return PakCrypto._decrypt_simple1(ciphertext)
        else:
            if PakCrypto._is_simple2_method(encryption_method):
                return PakCrypto._decrypt_simple2(ciphertext)
            else:
                if PakCrypto._is_sm4_method(encryption_method):
                    return PakCrypto._decrypt_sm4(ciphertext, file, encryption_method)
                else:
                    raise ValueError(f'Unknown encryption method: {encryption_method}')
    @staticmethod
    @lru_cache(maxsize=33)
    def generate_block_indices(n: int, encryption_method: int) -> List[int]:
        if not PakCrypto._is_sm4_method(encryption_method):
            return list(range(n))
        else:
            permutation = []
            lcg = PakCrypto._LCG(n)
            while len(permutation)!= n:
                x = lcg.next() % n
                if x not in permutation:
                    permutation.append(x)
            inverse = [0] * len(permutation)
            for i, x in enumerate(permutation):
                inverse[x] = i
            return inverse

class OodleCodec:
    """Optional adapter for a user-provided Oodle2 runtime.

    Oodle is proprietary software, so PakForge only loads a DLL that the user
    already owns or has installed. No runtime is downloaded or bundled. The
    public C ABI is configured lazily so normal ZLIB/ZSTD workflows do not
    require Oodle or Windows-specific libraries.
    """

    _runtime = None
    _load_error = None

    @classmethod
    def _candidate_paths(cls) -> list[str]:
        candidates = []
        configured = os.environ.get("PAKFORGE_OODLE_DLL")
        if configured:
            candidates.append(configured)
        module_dir = Path(__file__).resolve().parent
        candidates.extend([
            str(module_dir / "SOURCE" / "oodle2.dll"),
            str(module_dir / "oodle2.dll"),
        ])
        found = ctypes.util.find_library("oodle2")
        if found:
            candidates.append(found)
        # Preserve order while removing duplicates.
        return list(dict.fromkeys(candidates))

    @classmethod
    def _load(cls):
        if cls._runtime is not None or cls._load_error is not None:
            return cls._runtime
        last_error = None
        for candidate in cls._candidate_paths():
            try:
                loader = getattr(ctypes, "WinDLL", ctypes.CDLL)
                lib = loader(candidate)
                decompress = lib.OodleLZ_Decompress
                compress = lib.OodleLZ_Compress
                # Oodle's public ABI uses pointer-sized signed integers for
                # buffer lengths and returns the number of bytes written, or
                # a negative/zero value on failure.
                decompress.argtypes = [
                    ctypes.c_void_p, ctypes.c_int64,
                    ctypes.c_void_p, ctypes.c_int64,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    ctypes.c_void_p, ctypes.c_int64,
                    ctypes.c_void_p, ctypes.c_void_p,
                    ctypes.c_void_p, ctypes.c_int64, ctypes.c_int,
                ]
                decompress.restype = ctypes.c_int64
                compress.argtypes = [
                    ctypes.c_int, ctypes.c_void_p, ctypes.c_int64,
                    ctypes.c_void_p, ctypes.c_int,
                    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                    ctypes.c_void_p, ctypes.c_int64,
                ]
                compress.restype = ctypes.c_int64
                cls._runtime = (lib, decompress, compress, candidate)
                return cls._runtime
            except (AttributeError, OSError, TypeError) as exc:
                last_error = exc
        cls._load_error = last_error or FileNotFoundError("oodle2.dll not found")
        return None

    @classmethod
    def available(cls) -> bool:
        return cls._load() is not None

    @classmethod
    def description(cls) -> str:
        runtime = cls._load()
        if runtime:
            return f"available ({runtime[3]})"
        return f"unavailable ({cls._load_error})"

    @classmethod
    def decompress(cls, block: bytes, raw_size: int) -> bytes:
        runtime = cls._load()
        if runtime is None:
            raise RuntimeError(
                "CM_OODLE entry requires a user-provided oodle2.dll; "
                "set PAKFORGE_OODLE_DLL or place it in SOURCE/"
            )
        if raw_size <= 0:
            raise ValueError("Oodle decompression requires a positive raw block size")
        _lib, decompress, _compress, _path = runtime
        compressed = ctypes.create_string_buffer(block)
        raw = ctypes.create_string_buffer(raw_size)
        written = decompress(
            ctypes.cast(compressed, ctypes.c_void_p), len(block),
            ctypes.cast(raw, ctypes.c_void_p), raw_size,
            1, 1, 0, None, 0, None, None, None, 0, 0,
        )
        if written <= 0 or written > raw_size:
            raise RuntimeError(f"OodleLZ_Decompress failed with result {written}")
        return raw.raw[:written]

    @classmethod
    def compress(cls, raw_data: bytes) -> bytes:
        runtime = cls._load()
        if runtime is None:
            raise RuntimeError(
                "CM_OODLE compression requested but oodle2.dll is unavailable"
            )
        _lib, _decompress, compress, _path = runtime
        raw = ctypes.create_string_buffer(raw_data)
        # Oodle compressed output can be marginally larger than its input.
        capacity = len(raw_data) + max(65536, len(raw_data) // 16) + 64
        output = ctypes.create_string_buffer(capacity)
        written = compress(
            OODLE_CODEC_KRAKEN,
            ctypes.cast(raw, ctypes.c_void_p), len(raw_data),
            ctypes.cast(output, ctypes.c_void_p), OODLE_LEVEL_NORMAL,
            None, None, None, None, capacity,
        )
        if written <= 0 or written > capacity:
            raise RuntimeError(f"OodleLZ_Compress failed with result {written}")
        return output.raw[:written]


def effective_repack_compression_method(method: int) -> int:
    """Use ZSTD for newly encoded data when the optional Oodle DLL is absent.

    Existing Oodle payloads are copied byte-for-byte unless an edited entry is
    being rebuilt. An edited Oodle entry can therefore remain interoperable in
    an offline test PAK by switching its newly encoded blocks to ZSTD.
    """
    if method == CM_OODLE and not OodleCodec.available():
        console.print(
            "[bold yellow]Oodle unavailable; encoding edited blocks as ZSTD instead.[/bold yellow]"
        )
        return CM_ZSTD
    return method


class PakCompression:
    @staticmethod
    @lru_cache(maxsize=33)
    def _zstd_decompressor(dict: ZstdCompressionDict) -> ZstdDecompressor:
        return ZstdDecompressor(dict)
    @staticmethod
    def zstd_dictionary(dict_data) -> ZstdCompressionDict:
        return ZstdCompressionDict(dict_data, DICT_TYPE_AUTO)
    @staticmethod
    def decompress_block(
        block,
        dict: Optional[ZstdCompressionDict],
        compression_method: int,
        uncompressed_size: Optional[int] = None,
    ) -> bytes:
        if compression_method == CM_ZLIB:
            try:
                return zlib.decompress(block)
            except zlib.error:
                return block
        if compression_method == CM_OODLE:
            return OodleCodec.decompress(block, int(uncompressed_size or 0))
        else:
            if compression_method == CM_ZSTD or compression_method == CM_ZSTD_DICT:
                if compression_method!= CM_ZSTD_DICT:
                    dict = None
                return PakCompression._zstd_decompressor(dict).decompress(block)
            else:
                raise ValueError(f'Unknown compression method: {compression_method}')

class TencentPakFile:
    def __init__(self, file_path: PurePath, is_od=False):
        self._file_path = file_path
        with open(file_path, 'rb') as file:
            self._file_content = memoryview(file.read())
        self._is_od = is_od
        self._mount_point = PurePath()
        self._is_zstd_with_dict = 'zsdic' in str(self._file_path)
        self._zstd_dict = None
        self._files = []
        self._index = {}
        self._pak_info = TencentPakInfo(self._file_content, PakCrypto.zuc_keystream())
        self._verify_stem_hash()
        self._tencent_load_index()
    
    def _get_method_str(self, method_int, is_encryption):
        if is_encryption:
            if PakCrypto._is_simple1_method(method_int): return "SIMPLE1"
            if PakCrypto._is_simple2_method(method_int): return "SIMPLE2"
            if PakCrypto._is_sm4_method(method_int): return f"SM4 (Type {method_int})"
            return "NONE" if method_int == 0 else "UNKNOWN"
        else:
            if method_int == CM_NONE: return "NONE"
            if method_int == CM_ZLIB: return "ZLIB"
            if method_int == CM_OODLE: return "OODLE"
            if method_int == CM_ZSTD: return "ZSTD"
            if method_int == CM_ZSTD_DICT: return "ZSTD_DICT"
            return "UNKNOWN"
    
    def _verify_stem_hash(self) -> None:
        if not self._is_od and self._pak_info.version >= 9:
            expected = zlib.crc32(self._file_path.stem.lower().encode('utf-32le')) & 0xFFFFFFFF
            if self._pak_info.stem_hash != expected:
                raise ValueError(
                    f'PAK stem hash mismatch: stored={self._pak_info.stem_hash:#x}, '
                    f'expected={expected:#x}'
                )
    def _tencent_load_index(self) -> None:
        index_data = self._file_content[self._pak_info.index_offset:][:self._pak_info.index_size]
        if self._pak_info.index_encrypted:
            index_data = PakCrypto.decrypt_index(index_data, self._pak_info)
        else:
            index_data = index_data
        self._verify_index_hash(index_data)
        self._load_index(index_data)
    def _verify_index_hash(self, index_data) -> None:
        expected_hash = self._pak_info.index_hash
        if not self._is_od and self._pak_info.version >= 8:
                assert expected_hash == PakCrypto.rsa_extract(self._pak_info.packed_index_hash, RSA_MOD_2)
        assert expected_hash == SHA1.new(index_data).digest()
    @staticmethod
    def _construct_mount_point(mount_point: str) -> PurePath:
        """Preserve the source mount point while preventing path traversal.

        The previous implementation dropped every ``..`` component and then
        rebuilt a ``PurePath``.  That silently changed valid UE mount strings
        such as ``../../../Content/``.  We retain the exact relative suffix in
        a normalized forward-slash form.  Absolute roots are rejected; output
        extraction separately removes parent components to stay inside its
        destination directory.
        """
        raw = str(mount_point).replace('\\', '/')
        if raw.startswith('/') or (len(raw) > 1 and raw[1] == ':'):
            raise ValueError(f'Absolute PAK mount point is not supported: {mount_point!r}')
        parts = []
        for part in raw.split('/'):
            if not part or part == '.':
                continue
            if part == '..':
                parts.append(part)
            else:
                parts.append(part)
        if not parts:
            return PurePath()
        return PurePath('/'.join(parts))

    @staticmethod
    def _safe_mount_point_for_output(mount_point: PurePath) -> PurePath:
        """Map a preserved mount point to a filesystem-safe output suffix."""
        safe = [part for part in str(mount_point).replace('\\', '/').split('/')
                if part not in ('', '.', '..')]
        return PurePath('/'.join(safe)) if safe else PurePath()

    def _peek_content(self, offset: int, size: int, encryption_method: int) -> memoryview:
        size = PakCrypto.align_encrypted_content_size(size, encryption_method)
        return self._file_content[offset:][:size]
    def _peek_block_content(self, block: PakCompressedBlock, encryption_method: int) -> memoryview:
        size = PakCrypto.align_encrypted_content_size(block.end - block.start, encryption_method)
        return self._file_content[block.start:][:size]
    def _construct_zstd_dict(self, dict_entry: TencentPakEntry) -> None:
        assert not self._zstd_dict
        assert not dict_entry.encrypted
        assert dict_entry.compression_method == CM_NONE
        reader = Reader(self._peek_content(dict_entry.offset, dict_entry.size, 0))
        dict_size = reader.u8()
        _ = reader.u4()
        assert dict_size == reader.u4()
        dict_data = reader.s(dict_size)
        self._zstd_dict = PakCompression.zstd_dictionary(dict_data)
    def _load_index(self, index_data) -> None:
        if self._pak_info.version <= 10:
            raise ValueError(f'Unsupported version: {self._pak_info.version}')
        else:
            reader = Reader(index_data)
            self._mount_point = self._construct_mount_point(reader.string())
            self._files = [TencentPakEntry(reader, self._pak_info.version) for _ in range(reader.u4())]
            for _ in range(reader.u8()):
                dir_path = PurePath(reader.string())
                e = {reader.string(): self._files[~reader.i4()] for _ in range(reader.u8())}
                if self._is_zstd_with_dict and dir_path.name == 'zstddic':
                    assert len(e) == 1
                    self._construct_zstd_dict(e[[*e.keys()][0]])
                else:
                    self._index.update({PurePath(dir_path): e})
    
    def _write_to_disk(
        self,
        file_path: Path,
        entry: TencentPakEntry,
        announce: bool = True,
    ) -> None:
        """Extract one entry and atomically replace its destination.

        The temporary file is created in the destination directory so
        ``os.replace`` remains atomic on Termux filesystems. Decryption uses
        the final logical path because Tencent SM4 derivation is path-based.
        """
        encryption_method = entry.encryption_method
        compression_method = entry.compression_method
        if announce:
            enc_str = self._get_method_str(encryption_method, True)
            comp_str = self._get_method_str(compression_method, False)
            console.print(
                f"[bold cyan]->[/] Unpack: [bold green]{file_path.name}[/] "
                f"[[bold yellow]{comp_str}[/]/[bold magenta]{enc_str}[/]]"
            )

        file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = file_path.with_name(
            f".{file_path.name}.pakforge-{uuid.uuid4().hex}.tmp"
        )
        try:
            with open(temporary_path, 'wb') as file:
                if compression_method == CM_NONE:
                    data = self._peek_content(entry.offset, entry.size, encryption_method)
                    if entry.encrypted:
                        data = PakCrypto.decrypt_block(data, file_path, encryption_method)
                    file.write(data)
                else:
                    for block_number, x in enumerate(PakCrypto.generate_block_indices(
                        len(entry.compressed_blocks), encryption_method
                    )):
                        data = self._peek_block_content(entry.compressed_blocks[x], encryption_method)
                        if entry.encrypted:
                            data = PakCrypto.decrypt_block(data, file_path, encryption_method)
                        expected_raw_size = None
                        if compression_method == CM_OODLE:
                            block_size = int(entry.compression_block_size or 0)
                            expected_raw_size = min(
                                block_size,
                                max(0, entry.uncompressed_size - block_number * block_size),
                            )
                        data = PakCompression.decompress_block(
                            data, self._zstd_dict, compression_method, expected_raw_size
                        )
                        file.write(data)
            os.replace(temporary_path, file_path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def dump(self, out_path: Path, workers: int = 4) -> None:
        # Preserve the mount string in the PAK/index, but never allow its
        # leading ``..`` components to escape the chosen extraction directory.
        out_path = out_path / self._safe_mount_point_for_output(self._mount_point)
        out_path.mkdir(parents=True, exist_ok=True)
        jobs = []
        for dir_path, dir_content in self._index.items():
            current_out_path = out_path / dir_path
            current_out_path.mkdir(parents=True, exist_ok=True)
            for file_name, entry in dir_content.items():
                jobs.append((current_out_path / file_name, entry))

        total_files = len(jobs)
        try:
            worker_count = max(1, int(workers))
        except (TypeError, ValueError):
            worker_count = 4

        def extract_one(job):
            file_path, entry = job
            self._write_to_disk(file_path, entry, announce=False)
            return file_path

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan][UNPACK][/] {task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Extracting files...", total=total_files)
            if worker_count == 1 or total_files <= 1:
                for job in jobs:
                    extract_one(job)
                    progress.update(task, advance=1)
                return

            try:
                executor = ThreadPoolExecutor(max_workers=worker_count)
            except (OSError, RuntimeError) as exc:
                console.print(
                    f"[bold yellow]Parallel extraction unavailable; using single-threaded mode: {exc}[/bold yellow]"
                )
                for job in jobs:
                    extract_one(job)
            else:
                with executor:
                    futures = [executor.submit(extract_one, job) for job in jobs]
                    for future in as_completed(futures):
                        future.result()
                        progress.update(task, advance=1)

def dump_unpacking_log(pak_file, output_log_path: Path):
    with open(output_log_path, 'w', encoding='utf-8') as log_file:
        log_file.write('================================================================================\n')
        log_file.write('PAK UNPACKING DEBUG LOG\n')
        log_file.write('================================================================================\n\n')
        log_file.write(f'PAK File: {pak_file._file_path}\n')
        log_file.write(f'PAK Info Version: {pak_file._pak_info.version}\n')
        log_file.write(f'Mount Point: {pak_file._mount_point}\n')
        log_file.write('--------------------------------------------------------------------------------\n\n')
        file_count = 0
        for dir_path, files in pak_file._index.items():
            for file_name, entry in files.items():
                file_count += 1
                full_path = str(PurePath(dir_path) / file_name).replace('\\', '/')
                log_file.write(f'\n[{file_count}] {full_path}\n')
                log_file.write(f'  Uncompressed Size: {entry.uncompressed_size:,} bytes\n')
                log_file.write(f'  Compressed Size: {entry.size:,} bytes\n')
                log_file.write(f'  Compression Method: {entry.compression_method}\n')
                log_file.write(f'  Encryption Method: {entry.encryption_method}\n')
                log_file.write(f'  Compressed Blocks: {len(entry.compressed_blocks)}\n')
                if entry.compressed_blocks:
                    for i, blk in enumerate(entry.compressed_blocks):
                        block_size = blk.end - blk.start
                        log_file.write(f'    Block {i}: Offset={blk.start:,} Size={block_size:,} bytes\n')
        log_file.write('\n================================================================================\n')
        log_file.write('END OF LOG\n')
        log_file.write('================================================================================\n')
    console.print(f'[bold #00FF88]✅ Debug log saved to: {output_log_path}[/bold #00FF88]')

def _zstd_add_skippable_padding(data: bytes, pad_len: int) -> bytes:
    if pad_len <= 0:
        return data
    else:
        out = bytearray(data)
        while pad_len > 0:
            frame_len = min(max(pad_len - 8, 0), 1048576)
            out += b'P*M\x18'
            out += struct.pack('<I', frame_len)
            out += b'\x00' * frame_len
            pad_len -= 8 + frame_len
        return bytes(out)

def _encrypt_plaintext(plaintext: bytes, pak_relative_path: PurePath, encryption_method: int) -> bytes:
    if PakCrypto._is_simple1_method(encryption_method):
        return bytes((b ^ SIMPLE1_DECRYPT_KEY for b in plaintext))
    else:
        if PakCrypto._is_simple2_method(encryption_method):
            pad = -len(plaintext) % SIMPLE2_BLOCK_SIZE
            plaintext += b'\x00' * pad
            key, = struct.unpack('<I', SIMPLE2_DECRYPT_KEY)
            rolling = key
            out = []
            for x, in struct.iter_unpack('<I', plaintext):
                c = rolling ^ x
                out.append(c)
                rolling ^= c
            return struct.pack(f'<{len(out)}I', *out)
        else:
            if PakCrypto._is_sm4_method(encryption_method):
                key = PakCrypto._derive_sm4_key(pak_relative_path, encryption_method)
                sm4 = PakCrypto._sm4_context_for_key(key)
                pad_len = -len(plaintext) % 16
                if pad_len > 0:
                    plaintext = plaintext + b'\x00' * pad_len
                out = bytearray()
                for i in range(0, len(plaintext), 16):
                    block = plaintext[i:i + 16]
                    if len(block) < 16:
                        block = block.ljust(16, b'\x00')
                    out.extend(sm4.encrypt(block))
                return bytes(out)
            else:
                if encryption_method == 0:
                    return plaintext
                raise ValueError(f'Unsupported encryption method: {encryption_method}')

# ==================== WORKING REPACK FUNCTIONS ====================


def _encode_entry_payload(plain_data: bytes, pak_relative_path: PurePath, encrypted: bool, encryption_method: int) -> tuple[bytes, int]:
    """Encode one stored payload and return ``(physical_bytes, logical_size)``.

    PAK block end offsets describe the logical compressed length.  SIMPLE2 and
    SM4 require aligned ciphertext on disk, so the physical write can be
    larger than that logical length.  Keeping both values prevents the next
    block offset and the entry ``size`` field from drifting when an edited file
    changes size.
    """
    if not encrypted:
        return plain_data, len(plain_data)
    validate_encryption_metadata(True, encryption_method, 12)
    physical_size = PakCrypto.align_encrypted_content_size(len(plain_data), encryption_method)
    padded = plain_data.ljust(physical_size, b'\x00')
    return _encrypt_plaintext(padded, pak_relative_path, encryption_method), len(plain_data)


def _repack_uncompressed(outfh, pak_file, entry, pak_relative_path: PurePath, new_data: bytes):
    enc_method = entry.encryption_method
    target_size = entry.size
    enc_region = PakCrypto.align_encrypted_content_size(target_size, enc_method) if entry.encrypted else target_size
    plaintext = new_data[:enc_region]
    if entry.encrypted:
        a = PakCrypto.align_encrypted_content_size(len(plaintext), enc_method)
        plaintext += b'\x00' * (a - len(plaintext))
        cipher = _encrypt_plaintext(plaintext, pak_relative_path, enc_method)
        outfh.seek(entry.offset)
        outfh.write(cipher)
        with open(pak_file._file_path, 'rb') as src:
            src.seek(entry.offset + len(cipher))
            outfh.write(src.read(enc_region - len(cipher)))
    else:
        outfh.seek(entry.offset)
        outfh.write(plaintext)
        with open(pak_file._file_path, 'rb') as src:
            src.seek(entry.offset + len(plaintext))
            outfh.write(src.read(target_size - len(plaintext)))

def _best_compress(chunk, cm, zstd_dict=None):
    """Compress one chunk using the selected native method."""
    if cm == CM_OODLE:
        return OodleCodec.compress(chunk)
    if cm == CM_ZLIB:
        return zlib.compress(chunk, 9)
    if cm in (CM_ZSTD, CM_ZSTD_DICT):
        zd = zstd_dict if cm == CM_ZSTD_DICT else None
        for lvl in [22, 19, 16, 13, 10, 7, 4, 1]:
            try:
                return ZstdCompressor(level=lvl, dict_data=zd, threads=1).compress(chunk)
            except Exception:
                continue
    return chunk  # fallback: store raw

def _pw_string(s):
    """PAK string serialiser: i4(len_with_null) + bytes + null."""
    if not s: return struct.pack('<i', 0)
    b = s.encode('utf-8') + b'\x00'
    return struct.pack('<i', len(b)) + b

def _pw_entry(e, v):
    """Serialise one TencentPakEntry back to bytes."""
    if e.compression_method not in SUPPORTED_COMPRESSION_METHODS:
        raise ValueError(f'Unsupported compression method: {e.compression_method}')
    validate_encryption_metadata(e.encrypted, e.encryption_method, v)
    if e.compression_method != CM_NONE and e.compression_block_size <= 0:
        raise ValueError('Compressed entries must have a positive block size')
    w = bytearray(e.content_hash)
    w += struct.pack('<Q', e.offset)
    w += struct.pack('<Q', e.uncompressed_size)
    w += struct.pack('<I', e.compression_method)
    w += struct.pack('<Q', e.size)
    if v >= 5:
        w += bytes([e.unk1])
        w += e.unk2  # 20 bytes
    if e.compression_method != CM_NONE and v >= 3:
        w += struct.pack('<I', len(e.compressed_blocks))
        for b in e.compressed_blocks:
            w += struct.pack('<QQ', b.start, b.end)
    if v >= 4:
        w += struct.pack('<I', e.compression_block_size)
        w += bytes([1 if e.encrypted else 0])
    if v >= 12:
        w += struct.pack('<II', e.encryption_method, e.index_new_sep)
    return bytes(w)

def _get_all_dirs_and_mp(pak_file):
    """Re-parse raw (possibly encrypted) index → (mount_point_str, ordered dirs dict)."""
    raw = bytes(pak_file._file_content[
        pak_file._pak_info.index_offset:][:pak_file._pak_info.index_size])
    if pak_file._pak_info.index_encrypted:
        raw = PakCrypto.decrypt_index(raw, pak_file._pak_info)
    r = Reader(raw)
    mp = r.string()
    num_files = r.u4()
    for _ in range(num_files):
        TencentPakEntry(r, pak_file._pak_info.version)
    dirs = {}
    for _ in range(r.u8()):
        dp = r.string()
        cnt = r.u8()
        dirs[dp] = {r.string(): pak_file._files[~r.i4()] for _ in range(cnt)}
    return mp, dirs

def _stage_repack_inputs(edited: dict, workers: int = 4) -> dict[str, bytes]:
    """Read edited files concurrently without changing repack serialization order."""
    items = list(edited.items())
    if not items:
        return {}
    try:
        worker_count = max(1, int(workers))
    except (TypeError, ValueError):
        worker_count = 4

    def read_one(item):
        relative_path, (source_path, _template) = item
        return relative_path, source_path.read_bytes()

    if worker_count == 1 or len(items) <= 1:
        return dict(read_one(item) for item in items)

    try:
        executor = ThreadPoolExecutor(max_workers=worker_count)
    except (OSError, RuntimeError) as exc:
        console.print(
            f"[bold yellow]Parallel repack staging unavailable; using single-threaded mode: {exc}[/bold yellow]"
        )
        return dict(read_one(item) for item in items)

    staged = {}
    with executor:
        futures = [executor.submit(read_one, item) for item in items]
        for future in as_completed(futures):
            relative_path, data = future.result()
            staged[relative_path] = data
    # Rebuild insertion order exactly as the original edited mapping. The
    # serializer remains single-threaded, so offsets and index order are stable.
    return {relative_path: staged[relative_path] for relative_path, _ in items}


def repack_pak_file_full(pak_file, edited_root, output_path, target_path=None, force_add=False, workers=4):
    """
    FULL REBUILD REPACK - FIXED FOR NEW FILES (OPTION 4)
    """
    import copy as _cp

    console.print(f'[bold cyan]📦 Full PAK Rebuild mode (Option 3 & 4 logic)[/bold cyan]')
    if target_path:
        console.print(f'[bold cyan]🎯 Target path: {target_path}[/bold cyan]')
    
    # Get all files from edit folder. Relative paths are retained so an
    # auto-pipeline edit such as ``Mods/UI.lua`` becomes
    # ``<target-prefix>/Mods/UI.luac`` instead of being flattened by name.
    edit_root_path = Path(edited_root).resolve()
    edit_files = []
    for p in edit_root_path.rglob('*'):
        if p.is_file():
            edit_files.append(p)
    
    if not edit_files:
        console.print('[bold red]❌ No files found in EDIT folder![/bold red]')
        return 0
    
    console.print(f'[bold cyan]📁 Found {len(edit_files)} files in EDIT folder[/bold cyan]')

    version = pak_file._pak_info.version
    keystream = PakCrypto.zuc_keystream()
    orig_fc = pak_file._file_content

    # Get existing directory structure
    mp_str, all_dirs = _get_all_dirs_and_mp(pak_file)

    # FIX 1: Normalize target_path to match exact case and slashes of existing dirs
    if target_path and force_add:
        target_path = target_path.replace('\\', '/')
        matched_dir = None
        for existing_dir in all_dirs.keys():
            if existing_dir.strip('/').lower() == target_path.strip('/').lower():
                matched_dir = existing_dir
                break
        if matched_dir:
            target_path = matched_dir # Use the exact string from the PAK
        else:
            target_path = target_path.strip('/') + '/' # Ensure standard trailing slash
    
    # Build both basename and full-path maps. Basename matching preserves
    # legacy behavior; exact paths make target-prefix additions deterministic.
    pak_name_map = {}
    pak_path_map = {}
    for dir_path, files in pak_file._index.items():
        for name, entry in files.items():
            full_path = str(PurePath(dir_path)/name).replace('\\', '/')
            pak_name_map.setdefault(name.lower(), []).append((full_path, entry))
            pak_path_map[full_path.lower()] = (full_path, entry)

    # Find matching files
    edited = {}
    
    for p in edit_files:
        fl = p.name.lower()
        relative_edit = p.resolve().relative_to(edit_root_path).as_posix()
        target_candidate = (
            f"{target_path.rstrip('/')}/{relative_edit}"
            if target_path else None
        )
        found_match = False

        if target_candidate and target_candidate.lower() in pak_path_map:
            full_path, ent = pak_path_map[target_candidate.lower()]
            edited[full_path] = (p, ent)
            found_match = True

        if not found_match and fl in pak_name_map:
            cands = pak_name_map[fl]
            if target_path:
                target_candidates = [(fp, e) for fp, e in cands if target_path.strip('/') in fp]
                if target_candidates:
                    sz = p.stat().st_size
                    sm = [(fp, e) for fp, e in target_candidates if e.uncompressed_size == sz]
                    fp, ent = sm[0] if sm else target_candidates[0]
                    edited[fp] = (p, ent)
                    found_match = True
            
            if not found_match:
                sz = p.stat().st_size
                sm = [(fp, e) for fp, e in cands if e.uncompressed_size == sz]
                fp, ent = sm[0] if sm else cands[0]
                if target_path:
                    new_fp = target_candidate or f"{target_path.rstrip('/')}/{p.name}"
                    edited[new_fp] = (p, ent)
                else:
                    edited[fp] = (p, ent)
                found_match = True
        
        if not found_match:
            stem = p.stem.lower()
            ext = p.suffix.lower()
            for dir_path, files in pak_file._index.items():
                for name, entry in files.items():
                    if Path(name).stem.lower() == stem and Path(name).suffix.lower() == ext:
                        full_path = str(PurePath(dir_path)/name).replace('\\', '/')
                        if target_path:
                            new_fp = target_candidate or f"{target_path.rstrip('/')}/{p.name}"
                            edited[new_fp] = (p, entry)
                        else:
                            edited[full_path] = (p, entry)
                        found_match = True
                        break
                if found_match:
                    break
        
        if not found_match and force_add and target_path:
            template_entry = None
            for dir_path, files in pak_file._index.items():
                for name, entry in files.items():
                    if Path(name).suffix.lower() == p.suffix.lower():
                        template_entry = entry
                        break
                if template_entry: break
            
            if not template_entry:
                for dir_path, files in pak_file._index.items():
                    for name, entry in files.items():
                        template_entry = entry
                        break
                    if template_entry: break
            
            if template_entry:
                new_fp = target_candidate or f"{target_path.rstrip('/')}/{p.name}"
                edited[new_fp] = (p, template_entry)

    if not edited:
        console.print('[bold red]❌ No files to repack![/bold red]')
        return 0

    console.print(f'  [bold bright_cyan]📁 Files to repack: {len(edited)}[/bold bright_cyan]')
    staged_inputs = _stage_repack_inputs(edited, workers=workers)

    new_files = []
    for e in pak_file._files:
        ne = _cp.copy(e)
        ne.compressed_blocks = [_cp.copy(b) for b in e.compressed_blocks]
        new_files.append(ne)

    old_to_new = {id(pak_file._files[i]): new_files[i] for i in range(len(pak_file._files))}
    edited_paths = {fp: p for fp, (p, _) in edited.items()}

    out_buf = bytearray()

    for dp_str, dir_files in list(all_dirs.items()):
        for name, old_entry in list(dir_files.items()):
            full_path = str(PurePath(dp_str)/name).replace('\\', '/')
            ne = old_to_new.get(id(old_entry), None)
            
            if ne is None:
                ne = _cp.copy(old_entry)
                ne.compressed_blocks = [_cp.copy(b) for b in old_entry.compressed_blocks]
                new_files.append(ne)
                old_to_new[id(old_entry)] = ne

            em = old_entry.encryption_method
            cm = old_entry.compression_method

            if full_path in edited_paths:
                p, template = edited[full_path]
                new_raw = staged_inputs[full_path]
                pak_rel = PurePath(full_path)

                requested_compression = template.compression_method if template else cm
                ne.compression_method = effective_repack_compression_method(requested_compression)
                ne.encryption_method = template.encryption_method if template else em
                ne.encrypted = template.encrypted if template else old_entry.encrypted
                ne.unk1 = template.unk1 if template else old_entry.unk1
                ne.index_new_sep = template.index_new_sep if template else old_entry.index_new_sep
                validate_encryption_metadata(ne.encrypted, ne.encryption_method, version)
                if ne.compression_method not in SUPPORTED_COMPRESSION_METHODS:
                    raise ValueError(f'Unsupported compression method: {ne.compression_method}')

                # Hashes cover the uncompressed bytes and the canonical relative
                # asset path.  Do not include the mount point in the entry path
                # hash: the mount point is a separate index field.
                hashes = calculate_tencent_hashes(new_raw, full_path, version)
                ne.content_hash = hashes['content_hash']
                ne.unk2 = hashes['unk2'] if version >= 5 else bytes()
                ne.uncompressed_size = len(new_raw)

                if ne.compression_method == CM_NONE:
                    cipher, _ = _encode_entry_payload(new_raw, pak_rel, ne.encrypted, ne.encryption_method)
                    ne.offset = len(out_buf)
                    ne.size = len(new_raw)
                    ne.compressed_blocks = []
                    ne.compression_block_size = 0
                    out_buf += cipher
                else:
                    cs = (template.compression_block_size if template and template.compression_block_size > 0
                          else old_entry.compression_block_size if old_entry.compression_block_size > 0
                          else 65536)
                    cs = max(1, int(cs))
                    chunks = [new_raw[i:i + cs] for i in range(0, len(new_raw), cs)] or [b'']
                    new_blks = []
                    for chunk in chunks:
                        compressed = _best_compress(chunk, ne.compression_method, pak_file._zstd_dict)
                        cipher, logical_size = _encode_entry_payload(
                            compressed, pak_rel, ne.encrypted, ne.encryption_method
                        )
                        blk = PakCompressedBlock.__new__(PakCompressedBlock)
                        blk.start = len(out_buf)
                        blk.end = blk.start + logical_size
                        out_buf += cipher
                        new_blks.append(blk)

                    # This field is the uncompressed chunk size used to rebuild
                    # the block table; it must follow the new edited payload.
                    ne.compression_block_size = cs
                    ne.compressed_blocks = new_blks
                    ne.offset = new_blks[0].start if new_blks else len(out_buf)
                    ne.size = sum(b.end - b.start for b in new_blks)
                    ne.uncompressed_size = len(new_raw)

                console.print(f'[green]✓ Processed: {full_path}[/green]')

            else:
                if cm == CM_NONE:
                    read_sz = (PakCrypto.align_encrypted_content_size(old_entry.size, em)
                               if old_entry.encrypted else old_entry.size)
                    ne.offset = len(out_buf)
                    out_buf += bytes(orig_fc[old_entry.offset: old_entry.offset + read_sz])

                elif old_entry.compressed_blocks:
                    new_blks = []
                    for ob in old_entry.compressed_blocks:
                        unc = ob.end - ob.start
                        enc = (PakCrypto.align_encrypted_content_size(unc, em)
                               if old_entry.encrypted else unc)
                        nb = PakCompressedBlock.__new__(PakCompressedBlock)
                        nb.start = len(out_buf)
                        nb.end = nb.start + unc
                        out_buf += bytes(orig_fc[ob.start: ob.start + enc])
                        new_blks.append(nb)
                    ne.compressed_blocks = new_blks
                    ne.offset = new_blks[0].start

    if target_path and force_add:
        for fp, (p, template) in edited.items():
            already_processed = False
            for dp_str, dir_files in all_dirs.items():
                for name, entry in dir_files.items():
                    if str(PurePath(dp_str)/name).replace('\\', '/') == fp:
                        already_processed = True
                        break
                if already_processed:
                    break
            
            if not already_processed:
                ne = _cp.copy(template)
                new_raw = staged_inputs[fp]
                pak_rel = PurePath(fp)
                
                ne.compression_method = effective_repack_compression_method(template.compression_method)
                ne.encryption_method = template.encryption_method
                ne.encrypted = template.encrypted
                ne.unk1 = template.unk1
                ne.index_new_sep = template.index_new_sep
                validate_encryption_metadata(ne.encrypted, ne.encryption_method, version)
                if ne.compression_method not in SUPPORTED_COMPRESSION_METHODS:
                    raise ValueError(f'Unsupported compression method: {ne.compression_method}')

                hashes = calculate_tencent_hashes(new_raw, fp, version)
                ne.content_hash = hashes['content_hash']
                ne.unk2 = hashes['unk2'] if version >= 5 else bytes()
                ne.uncompressed_size = len(new_raw)

                if ne.compression_method == CM_NONE:
                    cipher, _ = _encode_entry_payload(new_raw, pak_rel, ne.encrypted, ne.encryption_method)
                    ne.offset = len(out_buf)
                    ne.size = len(new_raw)
                    ne.compressed_blocks = []
                    ne.compression_block_size = 0
                    out_buf += cipher
                else:
                    cs = template.compression_block_size if template.compression_block_size > 0 else 65536
                    cs = max(1, int(cs))
                    chunks = [new_raw[i:i + cs] for i in range(0, len(new_raw), cs)] or [b'']
                    new_blks = []
                    for chunk in chunks:
                        compressed = _best_compress(chunk, ne.compression_method, pak_file._zstd_dict)
                        cipher, logical_size = _encode_entry_payload(
                            compressed, pak_rel, ne.encrypted, ne.encryption_method
                        )
                        blk = PakCompressedBlock.__new__(PakCompressedBlock)
                        blk.start = len(out_buf)
                        blk.end = blk.start + logical_size
                        out_buf += cipher
                        new_blks.append(blk)

                    ne.compression_block_size = cs
                    ne.compressed_blocks = new_blks
                    ne.offset = new_blks[0].start if new_blks else len(out_buf)
                    ne.size = sum(b.end - b.start for b in new_blks)
                    ne.uncompressed_size = len(new_raw)

                new_files.append(ne)
                
                # FIX 4: Add to all_dirs mapping using the exact validated target_path
                if target_path not in all_dirs:
                    all_dirs[target_path] = {}
                all_dirs[target_path][p.name] = ne
                console.print(f'[green]✓ Added new: {fp}[/green]')

    eidx = {id(new_files[i]): i for i in range(len(new_files))}

    idx = bytearray(_pw_string(mp_str))
    idx += struct.pack('<I', len(new_files))
    for ne in new_files:
        idx += _pw_entry(ne, version)
    idx += struct.pack('<Q', len(all_dirs))
    for dp_str, dir_files in all_dirs.items():
        idx += _pw_string(dp_str)
        idx += struct.pack('<Q', len(dir_files))
        for name, old_e in dir_files.items():
            idx += _pw_string(name)
            found_idx = None
            for i, e in enumerate(new_files):
                if id(e) == id(old_e):
                    found_idx = i
                    break
            if found_idx is None:
                for i, e in enumerate(new_files):
                    if e.offset == old_e.offset and e.size == old_e.size:
                        found_idx = i
                        break
            if found_idx is not None:
                idx += struct.pack('<i', ~found_idx)
            else:
                idx += struct.pack('<i', -1)

    index_plain = bytes(idx)
    new_sha1 = SHA1.new(index_plain).digest()

    if pak_file._pak_info.index_encrypted:
        key = PakCrypto.rsa_extract(pak_file._pak_info.packed_key, RSA_MOD_1)
        iv = PakCrypto.rsa_extract(pak_file._pak_info.packed_iv, RSA_MOD_1)
        aes = AES.new(key, MODE_CBC, iv[:16])
        pad = (-len(index_plain)) % AES.block_size or AES.block_size
        index_bytes = aes.encrypt(index_plain + bytes([pad] * pad))
    else:
        index_bytes = index_plain

    new_idx_offset = len(out_buf)
    new_idx_size = len(index_bytes)
    out_buf += index_bytes

    footer_sz = TencentPakInfo._mem_size(version)
    new_footer = bytearray(orig_fc[-footer_sz:])

    # Tencent extensions precede the fixed 45-byte PakInfo footer.  The fixed
    # fields therefore use offsets relative to ``base_offset``; this is the
    # same ordering used by the parser and avoids corrupting v12 extensions.
    h_key = struct.pack('<5I', *keystream[4:9])
    base_offset = footer_sz - PakInfo._mem_size(version)
    index_hash_offset = base_offset + 1 + 4 + 4
    index_size_offset = index_hash_offset + 20
    index_offset_offset = index_size_offset + 8
    new_footer[index_hash_offset:index_hash_offset + 20] = bytes(
        a ^ b for a, b in zip(new_sha1, h_key)
    )
    new_footer[index_size_offset:index_size_offset + 8] = (
        (new_idx_size ^ (keystream[10] << 32 | keystream[11])).to_bytes(8, 'little')
    )
    new_footer[index_offset_offset:index_offset_offset + 8] = (
        (new_idx_offset ^ (keystream[0] << 32 | keystream[1])).to_bytes(8, 'little')
    )

    if not pak_file._is_od and version >= 9:
        stem_offset = 0
        if version >= 7:
            stem_offset += 32
        if version >= 8:
            stem_offset += 768
        output_stem_hash = zlib.crc32(
            Path(output_path).stem.lower().encode('utf-32le')
        ) & 0xFFFFFFFF
        new_footer[stem_offset:stem_offset + 4] = (
            (output_stem_hash ^ keystream[8]).to_bytes(4, 'little')
        )

    # In this Tencent layout ``content_org_hash`` is a single footer-wide
    # vendor field, not a per-entry field.  The parser cannot derive a
    # trustworthy replacement from one edited file, so preserve the source
    # value instead of writing a misleading SHA1 into the footer.  Per-entry
    # raw-data hashes are recalculated above in ``calculate_tencent_hashes``.

    out_buf += new_footer

    with open(output_path, 'wb') as f:
        f.write(out_buf)

    return len(edited)


# ==================== ORIGINAL REPACK (For Option 2) ====================

def _repack_compressed_with_display(outfh, pak_file, entry, pak_relative_path, new_data, repack_dir, display):
    """Original compressed repack with display - Working fine"""
    blocks = entry.compressed_blocks
    enc_method = entry.encryption_method
    comp_method = entry.compression_method
    order = PakCrypto.generate_block_indices(len(blocks), enc_method)
    
    if len(new_data) != entry.uncompressed_size:
        if len(new_data) < entry.uncompressed_size:
            new_data = new_data.ljust(entry.uncompressed_size, b'\x00')
        else:
            new_data = new_data[:entry.uncompressed_size]

    if len(blocks) > 1:
        if entry.compression_block_size > 0:
            chunk_size = entry.compression_block_size
        else:
            block_sizes = [blk.end - blk.start for blk in blocks]
            total_block_size = sum(block_sizes)
            avg_block_size = total_block_size / len(blocks)
            avg_compression_ratio = total_block_size / entry.uncompressed_size if entry.uncompressed_size > 0 else 1
            chunk_size = int(avg_block_size / avg_compression_ratio) if avg_compression_ratio > 0 else 65536
        
        ptr = 0
        for logical_i, phys_i in enumerate(order):
            blk = blocks[phys_i]
            target_size = blk.end - blk.start
            chunk_len = min(chunk_size, len(new_data) - ptr)
            if chunk_len <= 0: break
            chunk = new_data[ptr:ptr + chunk_len]
            ptr += chunk_len
            
            with open(pak_file._file_path, 'rb') as src:
                src.seek(blk.start)
                original_compressed = src.read(target_size)
            
            compressed_ok = False
            new_compressed = None
            zstd_dict = pak_file._zstd_dict if comp_method == CM_ZSTD_DICT else None
            
            if comp_method in (CM_ZSTD, CM_ZSTD_DICT):
                for level in [22, 19, 16, 13, 10, 7, 4, 1]:
                    c = ZstdCompressor(level=level, dict_data=zstd_dict, threads=1)
                    new_compressed = c.compress(chunk)
                    if len(new_compressed) <= target_size:
                        compressed_ok = True
                        break
            elif comp_method == CM_ZLIB:
                new_compressed = zlib.compress(chunk, zlib.Z_BEST_COMPRESSION)
                if len(new_compressed) <= target_size:
                    compressed_ok = True
            
            if not compressed_ok:
                outfh.seek(blk.start)
                outfh.write(original_compressed)
                display.add_block(logical_i, target_size, False)
                continue
            
            if entry.encrypted:
                if PakCrypto._is_sm4_method(enc_method):
                    pad_len = -len(new_compressed) % 16
                    if pad_len > 0: new_compressed += b'\x00' * pad_len
                new_compressed = _encrypt_plaintext(new_compressed, pak_relative_path, enc_method)
            
            if len(new_compressed) > target_size:
                outfh.seek(blk.start)
                outfh.write(original_compressed)
                display.add_block(logical_i, target_size, False)
            else:
                outfh.seek(blk.start)
                outfh.write(new_compressed)
                if len(new_compressed) < target_size:
                    outfh.write(b'\x00' * (target_size - len(new_compressed)))
                ratio = len(new_compressed) / len(chunk) if len(chunk) > 0 else 1
                display.add_block(logical_i, target_size, True, ratio)
    else:
        if not blocks: return
        blk = blocks[0]
        target_size = blk.end - blk.start
        
        with open(pak_file._file_path, 'rb') as src:
            src.seek(blk.start)
            original_compressed = src.read(target_size)
        
        compressed_ok = False
        new_compressed = None
        zstd_dict = pak_file._zstd_dict if comp_method == CM_ZSTD_DICT else None
        
        if comp_method in (CM_ZSTD, CM_ZSTD_DICT):
            for level in [22, 19, 16, 13, 10, 7, 4, 1]:
                c = ZstdCompressor(level=level, dict_data=zstd_dict, threads=1)
                new_compressed = c.compress(new_data)
                if len(new_compressed) <= target_size:
                    compressed_ok = True
                    break
        elif comp_method == CM_ZLIB:
            new_compressed = zlib.compress(new_data, zlib.Z_BEST_COMPRESSION)
            if len(new_compressed) <= target_size:
                compressed_ok = True
        
        if not compressed_ok:
            outfh.seek(blk.start)
            outfh.write(original_compressed)
            display.add_block(0, target_size, False)
            return
        
        if entry.encrypted:
            if PakCrypto._is_sm4_method(enc_method):
                pad_len = -len(new_compressed) % 16
                if pad_len > 0: new_compressed += b'\x00' * pad_len
            new_compressed = _encrypt_plaintext(new_compressed, pak_relative_path, enc_method)
        
        if len(new_compressed) > target_size:
            outfh.seek(blk.start)
            outfh.write(original_compressed)
            display.add_block(0, target_size, False)
        else:
            outfh.seek(blk.start)
            outfh.write(new_compressed)
            if len(new_compressed) < target_size:
                outfh.write(b'\x00' * (target_size - len(new_compressed)))
            ratio = len(new_compressed) / len(new_data) if len(new_data) > 0 else 1
            display.add_block(0, target_size, True, ratio)

def smart_resolve_by_fingerprint(filename: str, repack_file: Path, candidates: list):
    repack_size = repack_file.stat().st_size
    size_matches = [(path, entry) for path, entry in candidates if entry.uncompressed_size == repack_size]
    if len(size_matches) == 1:
        return size_matches[0]
    if not size_matches:
        return None
    def fingerprint(e):
        return (e.uncompressed_size, e.size, e.compression_method, len(e.compressed_blocks), e.compression_block_size)
    base_fp = fingerprint(size_matches[0][1])
    final_matches = [(path, entry) for path, entry in size_matches if fingerprint(entry) == base_fp]
    if len(final_matches) == 1:
        return final_matches[0]
    return None

def _patch_entry_map(pak_file) -> dict[str, TencentPakEntry]:
    """Return exact normalized PAK-relative paths for strict patch matching."""
    result = {}
    for dir_path, files in pak_file._index.items():
        for name, entry in files.items():
            full_path = normalize_pak_path(PurePath(dir_path) / name)
            if full_path in result:
                raise ValueError(f"Duplicate PAK path cannot be patched safely: {full_path}")
            result[full_path] = entry
    return result


def _patch_compressed_payload(pak_file, entry, pak_relative_path: PurePath, new_data: bytes) -> list[tuple[PakCompressedBlock, bytes]]:
    """Encode changed compressed blocks without changing their count or slots."""
    if len(new_data) != entry.uncompressed_size:
        raise ValueError(
            f"Patch requires unchanged uncompressed size for {pak_relative_path}: "
            f"old={entry.uncompressed_size}, new={len(new_data)}"
        )
    if not entry.compressed_blocks or entry.compression_block_size <= 0:
        raise ValueError(f"Patch requires a valid original block table for {pak_relative_path}")

    block_size = int(entry.compression_block_size)
    chunks = [new_data[i:i + block_size] for i in range(0, len(new_data), block_size)] or [b""]
    if len(chunks) != len(entry.compressed_blocks):
        raise ValueError(
            f"Patch would change the block count for {pak_relative_path}: "
            f"old={len(entry.compressed_blocks)}, new={len(chunks)}"
        )

    encoded = []
    order = PakCrypto.generate_block_indices(len(entry.compressed_blocks), entry.encryption_method)
    for logical_index, physical_index in enumerate(order):
        block = entry.compressed_blocks[physical_index]
        logical_capacity = block.end - block.start
        compressed = _best_compress(chunks[logical_index], entry.compression_method, pak_file._zstd_dict)
        cipher, logical_size = _encode_entry_payload(
            compressed, pak_relative_path, entry.encrypted, entry.encryption_method
        )
        if logical_size > logical_capacity:
            raise ValueError(
                f"Patch payload does not fit original block for {pak_relative_path}: "
                f"block={logical_index}, old_capacity={logical_capacity}, new={logical_size}"
            )
        physical_capacity = PakCrypto.align_encrypted_content_size(
            logical_capacity, entry.encryption_method
        ) if entry.encrypted else logical_capacity
        if len(cipher) > physical_capacity:
            raise ValueError(
                f"Patch ciphertext does not fit original block for {pak_relative_path}: "
                f"block={logical_index}, old_capacity={physical_capacity}, new={len(cipher)}"
            )
        encoded.append((block, cipher.ljust(physical_capacity, b"\x00")))
    return encoded


def repack_pak_file_patch(
    pak_file,
    edited_root: Path,
    output_path: Path,
    target_path: str | None = None,
    workers: int = 4,
) -> int:
    """Patch changed payload slots in place while preserving the original index and offsets.

    Patch mode is deliberately strict. It changes only bytes in existing payload slots;
    it never adds entries, changes compression methods, changes block tables, or rewrites
    the index. Files whose uncompressed size or compressed block payload cannot fit are
    rejected instead of being truncated or silently left unchanged.
    """
    edited_root = Path(edited_root)
    source_path = Path(pak_file._file_path)
    output_path = Path(output_path)
    if source_path.resolve() == output_path.resolve():
        raise ValueError("Patch output must be different from the source PAK")
    entry_map = _patch_entry_map(pak_file)
    prefix = normalize_pak_path(target_path) if target_path else ""

    candidates = {}
    for source in sorted(edited_root.rglob("*")):
        if not source.is_file():
            continue
        relative = normalize_pak_path(source.relative_to(edited_root))
        pak_path = normalize_pak_path(PurePath(prefix) / relative) if prefix else relative
        if pak_path not in entry_map:
            raise ValueError(
                f"Patch file has no exact existing PAK entry: {pak_path}. "
                "Patch mode cannot add or rename files."
            )
        if pak_path in candidates:
            raise ValueError(f"Duplicate patch input: {pak_path}")
        candidates[pak_path] = (source, entry_map[pak_path])

    staged = _stage_repack_inputs(candidates, workers=workers)
    changed = {}
    for pak_path, (source, entry) in candidates.items():
        raw = staged[pak_path]
        # The per-entry SHA1 is the cheapest safe changed-file test. If a legacy
        # PAK has a nonstandard hash, the file is conservatively treated as changed.
        if entry.content_hash == SHA1.new(raw).digest():
            continue
        if entry.compression_method == CM_OODLE and not OodleCodec.available():
            raise RuntimeError(
                f"Oodle runtime unavailable for changed entry {pak_path}; "
                "patch mode cannot switch codecs without changing the index."
            )
        if entry.compression_method == CM_NONE:
            if len(raw) != entry.uncompressed_size:
                raise ValueError(
                    f"Patch requires unchanged uncompressed size for {pak_path}: "
                    f"old={entry.uncompressed_size}, new={len(raw)}"
                )
            payload, _ = _encode_entry_payload(
                raw, PurePath(pak_path), entry.encrypted, entry.encryption_method
            )
            capacity = PakCrypto.align_encrypted_content_size(
                entry.size, entry.encryption_method
            ) if entry.encrypted else entry.size
            if len(payload) > capacity:
                raise ValueError(f"Patch payload does not fit original slot for {pak_path}")
            changed[pak_path] = [(entry.offset, payload.ljust(capacity, b"\x00"))]
        elif entry.compression_method in SUPPORTED_COMPRESSION_METHODS:
            changed[pak_path] = [
                (block.start, payload) for block, payload in
                _patch_compressed_payload(pak_file, entry, PurePath(pak_path), raw)
            ]
        else:
            raise ValueError(
                f"Unsupported compression method {entry.compression_method} for patch entry {pak_path}"
            )

    if not changed:
        console.print("[bold yellow]No changed files found; patch output was not created.[/bold yellow]")
        return 0

    temporary = output_path.with_name(f".{output_path.name}.pakforge-patch-{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(source_path, temporary)
        with open(temporary, "r+b") as outfh:
            for pak_path, writes in changed.items():
                for offset, payload in writes:
                    outfh.seek(offset)
                    outfh.write(payload)
        if temporary.stat().st_size != source_path.stat().st_size:
            raise RuntimeError("Patch changed the PAK file size; refusing to replace output")
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)

    console.print(
        f"[bold green]Patch complete: {len(changed)} changed file(s); "
        "all original offsets, index bytes, and file size preserved.[/bold green]"
    )
    return len(changed)


def repack_pak_file_with_block_display(pak_file, edited_root: Path, output_path: Path, workers: int = 4):
    """Original repack with simple block display - WORKING"""
    shutil.copy2(pak_file._file_path, output_path)
    
    pak_name_map = {}
    for dir_path, files in pak_file._index.items():
        for name, entry in files.items():
            full_path = str(PurePath(dir_path) / name).replace('\\', '/')
            key = name.lower()
            pak_name_map.setdefault(key, []).append((full_path, entry))
    
    edited = {}
    for p in edited_root.rglob('*'):
        if not p.is_file():
            continue
        fname_lower = p.name.lower()
        if fname_lower in pak_name_map:
            candidates = pak_name_map[fname_lower]
            if len(candidates) == 1:
                full_path, entry = candidates[0]
                edited[full_path] = (p, entry)
            else:
                resolved = smart_resolve_by_fingerprint(filename=p.name, repack_file=p, candidates=candidates)
                if resolved:
                    full_path, entry = resolved
                    edited[full_path] = (p, entry)
        else:
            stem = p.stem.lower()
            ext = p.suffix.lower()
            for dir_path, files in pak_file._index.items():
                for name, entry in files.items():
                    if Path(name).stem.lower() == stem and Path(name).suffix.lower() == ext:
                        full_path = str(PurePath(dir_path) / name).replace('\\', '/')
                        edited[full_path] = (p, entry)
                        break
    
    if not edited:
        console.print('[bold #FF0055]❌ No files to repack![/bold #FF0055]')
        return
    
    total_files = len(edited)
    staged_inputs = _stage_repack_inputs(edited, workers=workers)
    display = SimpleBlockDisplay(total_files, pak_file._file_path.name)
    
    with open(output_path, 'r+b') as outfh:
        for full_path, (p, entry) in edited.items():
            file_name = p.name
            total_blocks = len(entry.compressed_blocks) if entry.compressed_blocks else 1
            
            display.start_file(file_name, total_blocks)
            new_data = staged_inputs[full_path]
            pak_rel = PurePath(full_path)
            
            if entry.compression_method == CM_NONE:
                _repack_uncompressed(outfh, pak_file, entry, pak_rel, new_data)
                display.add_block(0, len(new_data), True)
            else:
                _repack_compressed_with_display(outfh, pak_file, entry, pak_rel, new_data, edited_root, display)
            
            display.finish_file()
    
    display.final_summary()

def detect_repack_mode(pak_path: Path) -> str:
    name = pak_path.name.lower()
    if name == 'mini_obb.pak':
        return 'MINI_OBB'
    if 'zsdic' in name:
        return 'OBBZSDIC'
    if 'game' in name or 'patch' in name:
        return 'GAMEPATCH'
    return 'OBBZSDIC'

def repack_mini_obb(pak, repack_dir, output_pak):
    console.print('[bold #00FFFF]🧩 Repack Mode: MINI_OBB[/bold #00FFFF]')
    pak._is_zstd_with_dict = False
    pak._zstd_dict = None
    repack_pak_file_with_block_display(pak_file=pak, edited_root=repack_dir, output_path=output_pak)

def repack_obbzsdic(pak, repack_dir, output_pak):
    console.print('[bold #00FFFF]🧩 Repack Mode: OBBZSDIC[/bold #00FFFF]')
    repack_pak_file_with_block_display(pak_file=pak, edited_root=repack_dir, output_path=output_pak)

def repack_gamepatch(pak, repack_dir, output_pak):
    console.print('[bold #00FFFF]🧩 Repack Mode: GAMEPATCH[/bold #00FFFF]')
    pak._is_zstd_with_dict = False
    pak._zstd_dict = None
    repack_pak_file_with_block_display(pak_file=pak, edited_root=repack_dir, output_path=output_pak)

SDCARD_DOWNLOAD_DIR = Path("/sdcard/Download")
SDCARD_EDIT_DIR = SDCARD_DOWNLOAD_DIR / "EDIT"
SDCARD_UNPACKED_DIR = SDCARD_DOWNLOAD_DIR / "UNPACKED"


def ensure_sdcard_directories() -> bool:
    """Create the only folders used by the interactive SD-card workflow."""
    try:
        SDCARD_EDIT_DIR.mkdir(parents=True, exist_ok=True)
        SDCARD_UNPACKED_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except OSError as exc:
        console.print(
            f"[bold {NEON['red']}]Cannot access {SDCARD_DOWNLOAD_DIR}: {escape(str(exc))}[/bold {NEON['red']}]"
        )
        console.print(
            f"[bold {NEON['cyan']}]Run Termux storage setup first, then retry.[/bold {NEON['cyan']}]"
        )
        return False


def get_pak_files_from_sdcard() -> list[Path]:
    """Return top-level .pak files from /sdcard/Download in stable order."""
    if not SDCARD_DOWNLOAD_DIR.is_dir():
        return []
    return sorted(
        (item for item in SDCARD_DOWNLOAD_DIR.iterdir() if item.is_file() and item.suffix.lower() == ".pak"),
        key=lambda item: item.name.casefold(),
    )


def select_pak_from_sdcard(prompt: str = "Select file") -> Path | None:
    """Show a numbered PAK list and return the selected file."""
    pak_files = get_pak_files_from_sdcard()
    if not pak_files:
        console.print(
            f"[bold {NEON['yellow']}]No .pak files found in /sdcard/Download/. Please copy your PAK file there.[/bold {NEON['yellow']}]"
        )
        return None

    console.print(f"[bold {NEON['yellow']}]📁 PAK files in /sdcard/Download/:[/bold {NEON['yellow']}]")
    for index, pak_file in enumerate(pak_files, 1):
        size = human_size(pak_file.stat().st_size)
        console.print(
            f"[bold {NEON['green']}][{index}][/bold {NEON['green']}] {pak_file.name} "
            f"[dim]({size})[/dim]"
        )

    while True:
        choice = safe_input(
            f"[bold {NEON['cyan']}]{prompt}:[/bold {NEON['cyan']}] "
        ).strip()
        try:
            selected = int(choice)
        except ValueError:
            console.print(f"[bold {NEON['red']}]Please enter a valid number.[/bold {NEON['red']}]")
            continue
        if 1 <= selected <= len(pak_files):
            return pak_files[selected - 1]
        console.print(
            f"[bold {NEON['red']}]Please choose a number from 1 to {len(pak_files)}.[/bold {NEON['red']}]"
        )


def print_ultimate_banner() -> None:
    """Render the compact purple-bordered beginner menu banner."""
    os.system("cls" if os.name == "nt" else "clear")
    console.print(
        f"[bold {NEON['purple']}]═══════════════════════════════════════[/bold {NEON['purple']}]\n"
        f"[bold {NEON['purple']}]          PAKFORGE ULTIMATE[/bold {NEON['purple']}]\n"
        f"[bold {NEON['purple']}]═══════════════════════════════════════[/bold {NEON['purple']}]"
    )


def print_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    logo = Text()
    logo.append('ＰＡＫＦＯＲＧＥ', style=f"bold {NEON['purple']}")
    logo.append('\nＮＥＯＮ  ＴＥＲＭＩＮＡＬ  ＳＵＩＴＥ', style=f"bold {NEON['blue']}")
    logo.append('\nPAK INSPECT  •  UNPACK  •  REPACK', style=f"bold {NEON['green']}")
    panel = Panel(
        Align.center(logo),
        box=DOUBLE_EDGE,
        border_style=NEON['purple'],
        padding=(1, 4),
        title=f"[bold {NEON['cyan']}]BOOT SCRIPT 1.1[/bold {NEON['cyan']}]",
        subtitle=f"[bold {NEON['pink']}]TERMUX POWER MODE[/bold {NEON['pink']}]",
        expand=False,
    )
    console.print(Align.center(panel))
    console.print()
    console.print(f"[bold {NEON['blue']}]┌─[/bold {NEON['blue']}][bold white]pakforge@termux[/bold white][bold {NEON['blue']}]─[/bold {NEON['blue']}][dim]interactive workspace[/dim]")
    console.print(f"[bold {NEON['pink']}]└──➤[/bold {NEON['pink']}] [bold {NEON['green']}]SYSTEM READY[/bold {NEON['green']}]  [dim]safe local PAK workflow[/dim]")
    console.print()

def get_indian_time():
    tz = pytz.timezone("Asia/Kolkata")
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

def safe_input(prompt: str='') -> str:
    rendered = themed_prompt(prompt)
    try:
        if '[' in rendered and ']' in rendered:
            console.print(rendered, end='')
            return input()
        return input(rendered)
    except (EOFError, RuntimeError):
        try:
            if sys.platform != 'win32':
                with open('/dev/tty', 'r') as tty:
                    sys.stderr.write(prompt)
                    sys.stderr.flush()
                    return tty.readline().rstrip('\n')
            else:
                with open('CON', 'r') as con:
                    sys.stderr.write(prompt)
                    sys.stderr.flush()
                    return con.readline().rstrip('\r\n')
        except Exception:
            return ''
    except Exception:
        return ''

def human_size(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f'{size:.2f} {unit}'
        size /= 1024.0
    return f'{size:.2f} PB'

def delete_folder(data_path: Path) -> None:
    folders = []
    for item in data_path.iterdir():
        if item.is_dir() and item.name not in ['PAK', 'UNPACK', 'REPACK', 'RESULT', 'PAK TOOL']:
            folders.append(item)
    if not folders:
        console.print('[bold #FFAA00]⚠ No folders found to delete![/bold #FFAA00]')
        return
    folder_table = Table(title=f"[bold {NEON['pink']}]✦ AVAILABLE FOLDERS[/bold {NEON['pink']}]", border_style=NEON['cyan'], box=DOUBLE_EDGE)
    folder_table.add_column('#', justify='center', style=f"bold {NEON['yellow']}", width=4)
    folder_table.add_column('Folder Name', justify='left', style=f"bold {NEON['green']}")
    folder_table.add_column('Size', justify='right', style=f"bold {NEON['blue']}")
    for i, folder in enumerate(folders, 1):
        folder_size = 0
        for root, dirs, files in os.walk(folder):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    folder_size += os.path.getsize(file_path)
        folder_table.add_row(str(i), folder.name, human_size(folder_size))
    console.print(folder_table)
    try:
        choice = int(console.input(f"\n[bold {NEON['cyan']}]Select folder number (1-{len(folders)}): [/bold {NEON['cyan']}]") )
        if 1 <= choice <= len(folders):
            selected_folder = folders[choice - 1]
            confirm = safe_input(f"[bold {NEON['yellow']}]Delete {selected_folder.name}? (yes/no): [/bold {NEON['yellow']}]").strip().lower()
            if confirm == 'yes':
                shutil.rmtree(selected_folder)
                console.print(f'[bold #00FF88]✅ Deleted: {selected_folder.name}[/bold #00FF88]')
            else:
                console.print('[bold #FFAA00]⚠ Cancelled[/bold #FFAA00]')
        else:
            console.print('[bold #FF0055]❌ Invalid selection[/bold #FF0055]')
    except ValueError:
        console.print('[bold #FF0055]❌ Invalid input[/bold #FF0055]')

def display_file_selector(title, folder_path, file_pattern="*.pak"):
    files = list(folder_path.glob(file_pattern))
    if not files:
        console.print(f"[bold red][ERROR] No {file_pattern} files in {folder_path}[/]")
        return None, None
    selection_table = Table(title=f"[bold {NEON['pink']}]✦ {title}[/]", expand=True, box=ROUNDED, border_style=NEON['purple'])
    selection_table.add_column(f"[bold {NEON['yellow']}]#[/]", justify='center', style=f"bold {NEON['yellow']}", width=4)
    selection_table.add_column(f"[bold {NEON['green']}]File Name[/]", justify='left', style=f"bold {NEON['green']}")
    selection_table.add_column(f"[bold {NEON['blue']}]Size[/]", justify='right', style=f"bold {NEON['blue']}")
    for i, f in enumerate(files, 1):
        size_mb = f.stat().st_size / (1024 * 1024)
        selection_table.add_row(str(i), f.name, f"{size_mb:.2f} MB")
    console.print(selection_table)
    try:
        idx = int(console.input(f"\n[bold {NEON['cyan']}]Select file number (1-{len(files)}): [/]")) - 1
        if idx < 0 or idx >= len(files):
            console.print("[bold red][ERROR] Invalid selection[/]")
            return None, None
        return files[idx], files
    except ValueError:
        console.print("[bold red][ERROR] Please enter a valid number[/]")
        return None, None

def _directory_has_files(directory: Path) -> bool:
    return directory.is_dir() and any(path.is_file() for path in directory.rglob("*"))


def unpack_selected_sdcard_pak() -> None:
    pak_file = select_pak_from_sdcard()
    if pak_file is None:
        return

    output_dir = SDCARD_UNPACKED_DIR / pak_file.stem
    try:
        console.print(
            f"[bold {NEON['green']}]✅ Extracting to {output_dir}/[/bold {NEON['green']}]"
        )
        pak = TencentPakFile(pak_file)
        pak.dump(output_dir, workers=4)
        dump_unpacking_log(pak, output_dir / f"Debug_{pak_file.stem}.log")
        console.print(
            f"[bold {NEON['green']}]✅ Done! Edit files in {SDCARD_EDIT_DIR}/[/bold {NEON['green']}]"
        )
    except Exception as exc:
        console.print(f"[bold {NEON['red']}]Unpack failed: {escape(str(exc))}[/bold {NEON['red']}]")


def lua_inject_selected_sdcard_pak() -> None:
    """Inject only Lua source/bytecode files from the SD-card EDIT folder."""
    SDCARD_EDIT_DIR.mkdir(parents=True, exist_ok=True)

    pak_file = select_pak_from_sdcard("Source PAK")
    if pak_file is None:
        return

    default_target = "Content/Lua/Mods"
    console.print(f"[bold {NEON['cyan']}]📁 Source PAK: {pak_file.name}[/bold {NEON['cyan']}]")
    target_path = safe_input(
        f"[bold {NEON['cyan']}]📁 Target path (inside PAK) [default: {default_target}]:[/bold {NEON['cyan']}] "
    ).strip()
    target_path = (target_path or default_target).replace('\\', '/').strip('/')

    lua_files = sorted(
        (
            path for path in SDCARD_EDIT_DIR.rglob('*')
            if path.is_file() and path.suffix.lower() in {'.lua', '.luac'}
        ),
        key=lambda path: path.as_posix().casefold(),
    )
    if not lua_files:
        console.print(
            f"[bold {NEON['yellow']}]No .lua or .luac files found in {SDCARD_EDIT_DIR}/.[/bold {NEON['yellow']}]"
        )
        return

    output_pak = SDCARD_DOWNLOAD_DIR / f"MODDED_{pak_file.name}"
    try:
        # Stage only Lua files so images, configs, and other EDIT content cannot
        # accidentally enter this Lua-only injection workflow.
        with tempfile.TemporaryDirectory(prefix='pakforge-lua-inject-') as staging:
            staging_root = Path(staging)
            for source in lua_files:
                relative = source.relative_to(SDCARD_EDIT_DIR)
                destination = staging_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            pak = TencentPakFile(pak_file)
            count = repack_pak_file_full(
                pak,
                staging_root,
                output_pak,
                target_path=target_path,
                force_add=True,
                workers=4,
            )

        if count <= 0:
            console.print(f"[bold {NEON['red']}]No Lua files were repacked.[/bold {NEON['red']}]")
            return

        TencentPakFile(output_pak)
        console.print(
            f"[bold {NEON['green']}]✅ Lua-injected {count} files to: {output_pak}[/bold {NEON['green']}]"
        )
        console.print(f"[bold {NEON['green']}]✅ Verification passed![/bold {NEON['green']}]")
    except Exception as exc:
        console.print(f"[bold {NEON['red']}]Lua inject failed: {escape(str(exc))}[/bold {NEON['red']}]")


def repack_selected_sdcard_pak() -> None:
    SDCARD_EDIT_DIR.mkdir(parents=True, exist_ok=True)
    if not _directory_has_files(SDCARD_EDIT_DIR):
        console.print(
            f"[bold {NEON['yellow']}]EDIT folder is empty. Place your modified files in /sdcard/Download/EDIT/ first.[/bold {NEON['yellow']}]"
        )
        return

    pak_file = select_pak_from_sdcard("Source PAK")
    if pak_file is None:
        return

    default_target = "Content/Lua/Mods"
    console.print(f"[bold {NEON['cyan']}]📁 Source PAK: {pak_file.name}[/bold {NEON['cyan']}]")
    console.print(
        f"[bold {NEON['cyan']}]📁 Using files from: {SDCARD_EDIT_DIR}/[/bold {NEON['cyan']}]"
    )
    target_path = safe_input(
        f"[bold {NEON['cyan']}]📁 Target path (inside PAK) [default: {default_target}]:[/bold {NEON['cyan']}] "
    ).strip()
    target_path = (target_path or default_target).replace('\\', '/').strip('/')

    output_pak = SDCARD_DOWNLOAD_DIR / f"MODDED_{pak_file.name}"
    try:
        pak = TencentPakFile(pak_file)
        count = repack_pak_file_full(
            pak,
            SDCARD_EDIT_DIR,
            output_pak,
            target_path=target_path,
            force_add=True,
            workers=4,
        )
        if count <= 0:
            console.print(f"[bold {NEON['red']}]No files were repacked.[/bold {NEON['red']}]")
            return

        # Re-opening the generated PAK exercises the native index/hash parser.
        TencentPakFile(output_pak)
        console.print(
            f"[bold {NEON['green']}]✅ Repacked {count} files to: {output_pak}[/bold {NEON['green']}]"
        )
        console.print(f"[bold {NEON['green']}]✅ Verification passed![/bold {NEON['green']}]")
    except Exception as exc:
        console.print(f"[bold {NEON['red']}]Repack failed: {escape(str(exc))}[/bold {NEON['red']}]")


def main_menu():
    """Compact beginner menu for the fixed Termux SD-card workflow."""
    if not ensure_sdcard_directories():
        return

    while True:
        print_ultimate_banner()
        console.print(f"[bold {NEON['green']}]1. UNPACK PAK[/bold {NEON['green']}]")
        console.print(f"[bold {NEON['green']}]2. REPACK PAK (Full)[/bold {NEON['green']}]")
        console.print(f"[bold {NEON['green']}]3. LUA INJECT (Only Lua files, no full rebuild)[/bold {NEON['green']}]")
        console.print(f"[bold {NEON['green']}]4. EXIT[/bold {NEON['green']}]")
        choice = safe_input(
            f"[bold {NEON['cyan']}]SELECT (1-4):[/bold {NEON['cyan']}] "
        ).strip()

        if choice == "1":
            unpack_selected_sdcard_pak()
        elif choice == "2":
            repack_selected_sdcard_pak()
        elif choice == "3":
            lua_inject_selected_sdcard_pak()
        elif choice == "4":
            return
        else:
            console.print(f"[bold {NEON['red']}]Please select 1, 2, 3, or 4.[/bold {NEON['red']}]")
            safe_input(f"[bold {NEON['cyan']}]Press Enter to continue...[/bold {NEON['cyan']}] ")

if __name__ == '__main__':
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print('\n[bold #FFFF00]⚠ Interrupted. Exiting...[/bold #FFFF00]')
        sys.exit(0)
    except Exception as e:
        console.print(f'[bold #FF0055]💥 ERROR:[/bold #FF0055] {escape(str(e))}')
        import traceback
        traceback.print_exc()
        safe_input('\nPress Enter to exit...')
        sys.exit(1)
        
